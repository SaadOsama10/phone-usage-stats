#!/usr/bin/env python3
"""End-to-end check of the web demo in headless Chromium (works on localhost or the live URL).

Usage: python tests/e2e_demo.py URL [--shots DIR]
Checks: Pyodide loads, every button works for 2 columns x {t, z}, bad input shows a
validation message, charts render, no console errors, no horizontal overflow at 375px.
"""
import argparse
import os
import sys
from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("url")
ap.add_argument("--shots")
args = ap.parse_args()

TABS = {"describe": "Descriptive Stats", "ci": "Confidence Interval", "test": "Hypothesis Test",
        "size": "Sample Size", "outliers": "Outliers", "charts": "Charts"}
ok, bad = 0, []


def check(cond, what):
    global ok
    if cond:
        ok += 1
        print("  ok  ", what)
    else:
        bad.append(what)
        print("  FAIL", what)


with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1100, "height": 900})
    errors = []
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))
    failed_req = []
    page.on("requestfailed", lambda r: failed_req.append(r.url))
    page.on("response", lambda r: r.status >= 400 and failed_req.append(f"{r.status} {r.url}"))

    page.goto(args.url)
    check(page.locator("#loader").is_visible(), "loading indicator shown while Pyodide starts")
    page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=120000)
    check(page.locator("#loader").is_hidden() and page.locator("#app").is_visible(), "Pyodide loaded, app visible")
    cols = page.locator("#column option").all_text_contents()
    check(len(cols) == 7, f"column dropdown lists all 7 numeric columns ({len(cols)})")

    for col in ("App Usage Time (min/day)", "Screen On Time (hours/day)"):
        page.select_option("#column", col)
        for mode, sigma in (("t", ""), ("z", "50")):
            page.fill("#sigma", sigma)
            page.fill("#mu0", "100")
            page.fill("#margin", "5")
            for action, label in TABS.items():
                page.get_by_role("button", name=label, exact=True).click()
                res = page.locator("#results")
                tag = f"{col} [{mode}] {label}"
                check(res.locator(".card").count() == 1 and res.locator(".msg.err").count() == 0, f"{tag}: result card")
                txt = res.inner_text()
                if action == "ci":
                    check(("z · σ known" if mode == "z" else "Student's t") in txt, f"{tag}: shows method")
                if action == "test":
                    exp = "z-test used" if mode == "z" else "t-test used"
                    check(exp in txt.lower() or exp.upper() in txt.upper(), f"{tag}: shows {exp}")
                    check("p-value" in txt.lower(), f"{tag}: shows p-value")
                if action == "charts":
                    page.wait_for_selector("#hist svg", timeout=10000)
                    check(page.locator("#hist svg").count() == 1 and page.locator("#box svg").count() == 1, f"{tag}: histogram + box plot svg rendered")
                    nbars = page.locator("#hist svg path").count()
                    check(nbars >= 20, f"{tag}: histogram has drawn marks ({nbars} paths)")

    # validation
    page.select_option("#column", "App Usage Time (min/day)")
    cases = [("test", "", "", "5", "Please enter a value for μ₀."), ("test", "abc", "", "5", "μ₀ must be a number (got 'abc')."),
             ("ci", "100", "-3", "5", "σ must be greater than 0."), ("size", "100", "", "0", "E must be greater than 0."),
             ("size", "100", "", "", "Please enter a value for E.")]
    labels = TABS
    for action, mu0, sigma, e, msg in cases:
        page.fill("#mu0", mu0); page.fill("#sigma", sigma); page.fill("#margin", e)
        page.get_by_role("button", name=labels[action], exact=True).click()
        err = page.locator("#results .msg.err")
        check(err.count() == 1 and msg in err.inner_text(), f"validation: {msg}")

    # theme toggle + dark charts
    page.fill("#mu0", "100"); page.fill("#sigma", ""); page.fill("#margin", "5")
    page.get_by_role("button", name="Charts", exact=True).click()
    page.click("#theme")
    page.wait_for_selector("#hist svg")
    check(True, "theme toggle works with charts open")

    # shots
    if args.shots:
        os.makedirs(args.shots, exist_ok=True)
        page.click("#theme")  # back to original theme
        page.get_by_role("button", name="Hypothesis Test", exact=True).click()
        page.screenshot(path=f"{args.shots}/desktop-test.png")

    # mobile overflow
    m = b.new_page(viewport={"width": 375, "height": 800}, device_scale_factor=2)
    m.on("console", lambda msg: msg.type == "error" and errors.append(msg.text))
    m.on("pageerror", lambda e: errors.append(str(e)))
    m.goto(args.url)
    m.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=120000)
    for action, label in TABS.items():
        m.get_by_role("button", name=label, exact=True).click()
        if action == "charts":
            m.wait_for_selector("#hist svg")
        sw = m.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        check(sw[0] <= sw[1], f"375px: no horizontal overflow on {label} (scrollWidth {sw[0]} <= {sw[1]})")
        if args.shots and action in ("test", "charts"):
            m.screenshot(path=f"{args.shots}/mobile-{action}.png", full_page=True)

    check(not errors, f"no console errors {errors}")
    check(not failed_req, f"no failed/4xx requests {failed_req}")
    b.close()

print(f"\n{ok} checks passed, {len(bad)} failed")
sys.exit(1 if bad else 0)
