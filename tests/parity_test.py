#!/usr/bin/env python3
"""Parity test: browser (Pyodide) results vs desktop/Python results.

For every numeric column, in t-mode (σ blank) and z-mode (σ given), and for every
analysis, three implementations are compared:

  1. DESKTOP   - the real PyQt5 MainWindow (gui_main.py), driven off-screen; its
                 text output is the ground truth for printed values.
  2. PYTHON    - docs/demo/web_core.py run in CPython on the repo-root stats_tools.py;
                 gives full-precision raw floats.
  3. BROWSER   - the demo page in headless Chromium (Pyodide, stats_tools.py unchanged).

Checks: browser text == desktop text (exact), browser raw floats == CPython raw floats
(exact, or reported in ulps), chart data == numpy/matplotlib's histogram and boxplot
statistics, and the served stats_tools.py / CSV are byte-identical to the repo-root files.

Usage:  python tests/parity_test.py [--url https://.../demo/index.html]
Needs:  PyQt5, matplotlib, numpy, playwright (+ chromium).
"""
import argparse
import functools
import hashlib
import http.server
import json
import os
import socketserver
import struct
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "docs", "demo")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.chdir(ROOT)
sys.path.insert(0, DEMO)
sys.path.insert(0, ROOT)          # repo-root stats_tools.py wins over the served copy

import stats_tools as st          # noqa: E402  (the repo-root file)
import web_core                   # noqa: E402

ACTIONS = ["describe", "ci", "test", "size", "outliers", "charts"]
BUTTON = {"describe": "analyze_button", "ci": "ci_button", "test": "hypothesis_button",
          "size": "sample_size_button", "outliers": "outlier_button", "charts": "visuals_button"}

failures = []
ulp_fields = {}   # field -> (count, max ulp) where browser and CPython differ in the last bits
counts = {"text": 0, "raw_exact": 0, "raw_floats": 0, "raw_ulp_diff": 0, "max_ulp": 0, "cases": 0, "chart": 0}


def fail(msg):
    failures.append(msg)
    print("FAIL:", msg)


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def ulps(a, b):
    ia, ib = (struct.unpack("<q", struct.pack("<d", x))[0] for x in (a, b))
    ia = ia if ia >= 0 else -(1 << 63) - ia
    ib = ib if ib >= 0 else -(1 << 63) - ib
    return abs(ia - ib)


def compare_raw(a, b, where):
    """Recursively compare two JSON-like structures; floats must be exactly equal."""
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return fail(f"{where}: keys differ {a.keys() ^ b.keys()}")
        for k in a:
            compare_raw(a[k], b[k], f"{where}.{k}")
    elif isinstance(a, list):
        if len(a) != len(b):
            return fail(f"{where}: length {len(a)} != {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            compare_raw(x, y, f"{where}[{i}]")
    elif isinstance(a, float) and isinstance(b, float):
        counts["raw_floats"] += 1
        if a == b or (a != a and b != b):
            counts["raw_exact"] += 1
        else:
            counts["raw_ulp_diff"] += 1
            u = ulps(a, b)
            counts["max_ulp"] = max(counts["max_ulp"], u)
            field = where.rsplit("/", 1)[1]
            n, m = ulp_fields.get(field, (0, 0))
            ulp_fields[field] = (n + 1, max(m, u))
    elif a != b:
        fail(f"{where}: {a!r} != {b!r}")


# ---------------- cases ----------------
def make_cases(columns, values_by_col):
    cases = []
    for col in columns:
        v = values_by_col[col]
        mean, sd = st.mean(v), st.sample_std(v)
        sigma = f"{round(sd, 1):g}"
        e_small = f"{max(round(sd / 10, 2), 0.01):g}"
        for mu0 in ("100", f"{round(mean):g}"):
            for sig in ("", sigma):
                for e in ("5", e_small):
                    cases.append((col, mu0, sig, e))
    bad = [("", "5", "x"), ("abc", "", "5"), ("100", "-1", "5"), ("100", "0", "5"),
           ("100", "x", "5"), ("100", "", ""), ("100", "", "0"), ("100", "", "-2"), ("100", "", "abc")]
    for mu0, sig, e in bad:
        cases.append((columns[0], mu0, sig, e))
    return cases


def desktop_runs(cases):
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    import gui_main
    win = gui_main.MainWindow()
    out = {}
    for case in cases:
        col, mu0, sig, e = case
        win.column_combo.setCurrentText(col)
        win.mu0_input.setText(mu0)
        win.sigma_input.setText(sig)
        win.margin_input.setText(e)
        for action in ACTIONS:
            win.result_box.clear()
            win.image_label.clear()
            getattr(win, BUTTON[action]).click()
            text = [ln for ln in win.result_box.toPlainText().split("\n") if ln.strip()]
            if action == "charts" and win.image_label.pixmap() is not None and not win.image_label.pixmap().isNull():
                text = ["<chart image rendered>"]
            out[(case, action)] = text
    return out


def python_runs(cases):
    with open(os.path.join(ROOT, "user_behavior_dataset.csv"), encoding="utf-8") as f:
        web_core.load_csv(f.read())
    return {(case, a): json.loads(web_core.run(a, *case)) for case in cases for a in ACTIONS}


def serve_docs():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=os.path.join(ROOT, "docs"))
    handler.log_message = lambda *a, **k: None
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    httpd = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=os.path.join(ROOT, "docs")))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/demo/index.html"


def browser_runs(url, cases):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        errors = []
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=120000)
        info = page.evaluate("({py: demoApi.pythonVersion, pyodide: demoApi.pyodideVersion, cols: demoApi.columns})")
        res = page.evaluate("""(cases) => cases.flatMap(c => ACTIONS.map(a => demoApi.run(a, ...c)))""".replace("ACTIONS", json.dumps(ACTIONS)), [list(c) for c in cases])
        b.close()
    keys = [(c, a) for c in cases for a in ACTIONS]
    return info, dict(zip(keys, res)), errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="demo page to test (default: serve docs/ locally)")
    args = ap.parse_args()

    # 0. served files are the repo's files, byte for byte
    for name in ("stats_tools.py", "user_behavior_dataset.csv"):
        if sha(os.path.join(ROOT, name)) != sha(os.path.join(DEMO, name)):
            fail(f"docs/demo/{name} differs from the repo-root file")
    if args.url:
        import urllib.request
        base = args.url.rsplit("/", 1)[0] if args.url.endswith(".html") else args.url.rstrip("/")
        for name in ("stats_tools.py", "user_behavior_dataset.csv", "web_core.py"):
            data = urllib.request.urlopen(f"{base}/{name}").read()
            ref = os.path.join(ROOT, name) if name != "web_core.py" else os.path.join(DEMO, name)
            if hashlib.sha256(data).hexdigest() != sha(ref):
                fail(f"served {name} differs from the repo file")

    httpd = None
    url = args.url
    if not url:
        httpd, url = serve_docs()

    import csv
    rows = list(csv.reader(open(os.path.join(ROOT, "user_behavior_dataset.csv"), newline="", encoding="utf-8")))
    header = rows[0]
    py_cols = json.loads(web_core.load_csv(open(os.path.join(ROOT, "user_behavior_dataset.csv"), encoding="utf-8").read()))
    values_by_col = {c: [float(r[header.index(c)]) for r in rows[1:]] for c in py_cols}
    cases = make_cases(py_cols, values_by_col)
    counts["cases"] = len(cases) * len(ACTIONS)
    print(f"{len(py_cols)} columns, {len(cases)} input combinations x {len(ACTIONS)} analyses = {counts['cases']} checks")

    desktop = desktop_runs(cases)
    python = python_runs(cases)
    info, browser, errors = browser_runs(url, cases)
    print(f"Browser: Python {info['py']} / Pyodide {info['pyodide']} at {url}")
    if info["cols"] != py_cols:
        fail(f"column lists differ: {info['cols']} vs {py_cols}")

    for case in cases:
        for action in ACTIONS:
            key = (case, action)
            where = f"{case}/{action}"
            br = browser[key]
            py = python[key]
            if br["ok"] != py["ok"]:
                fail(f"{where}: ok flag differs")
                continue
            # 1. printed text vs the real desktop app
            text = br["lines"] if br["ok"] else [br["error"]]
            if action == "charts" and br["ok"]:
                text = ["<chart image rendered>"]
            counts["text"] += 1
            if text != desktop[key]:
                fail(f"{where}: browser text != desktop text\n   browser: {text}\n   desktop: {desktop[key]}")
            if br["ok"] and action != "charts" and br["lines"] != py["lines"]:
                fail(f"{where}: browser lines != CPython lines")
            # 2. full-precision raw values vs CPython
            compare_raw(br, py, where)

    # 3. chart data vs numpy / matplotlib
    import numpy as np
    from matplotlib import cbook
    for col in py_cols:
        v = values_by_col[col]
        br = browser[((col, "100", "", "5"), "charts")]["data"]
        counts_np, edges_np = np.histogram(v, bins=20)
        bs = cbook.boxplot_stats(v)[0]
        counts["chart"] += 1
        if br["counts"] != counts_np.tolist():
            fail(f"{col}: histogram counts differ from numpy")
        if not np.allclose(br["edges"], edges_np, rtol=0, atol=1e-9):
            fail(f"{col}: histogram edges differ from numpy")
        for k_br, k_mpl in (("q1", "q1"), ("q3", "q3"), ("median", "med"), ("whisker_low", "whislo"), ("whisker_high", "whishi")):
            if abs(br[k_br] - bs[k_mpl]) > 1e-9:
                fail(f"{col}: {k_br} {br[k_br]} != matplotlib {bs[k_mpl]}")
        if sorted(br["fliers"]) != sorted(bs["fliers"].tolist()):
            fail(f"{col}: fliers differ from matplotlib")

    if errors:
        fail(f"console errors: {errors}")
    if httpd:
        httpd.shutdown()

    print("\n=== PARITY RESULT ===")
    print(f"printed-text checks (browser vs desktop GUI): {counts['text']}")
    print(f"raw floats compared (browser vs CPython):     {counts['raw_floats']}  exact: {counts['raw_exact']}  "
          f"differing: {counts['raw_ulp_diff']} (max {counts['max_ulp']} ulp)")
    print(f"chart data checks vs numpy/matplotlib:        {counts['chart']} columns")
    for field, (n, m) in sorted(ulp_fields.items()):
        print(f"  last-bit differences in {field}: {n} values, max {m} ulp (libm erf in WebAssembly vs native)")
    print("PASS" if not failures else f"FAILED ({len(failures)} problems)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
