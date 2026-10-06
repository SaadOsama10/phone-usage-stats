"""Browser glue for the Phone Usage Statistics demo (runs in Pyodide, also in CPython).

It does what gui_main.py does for each button -- read the inputs, validate them,
call the hand-written functions in stats_tools.py, format the numbers -- but
returns JSON instead of writing into a Qt text box. No statistics are computed
here that are not computed by the desktop app; stats_tools.py is used unchanged.
"""
import csv
import io
import json
import math
from bisect import bisect_right

import stats_tools as st

CONFIDENCE = 0.95
ALPHA = 1 - CONFIDENCE
BINS = 20

_headers = []
_data = []
_numeric_columns = []


def load_csv(text):
    """Parse the dataset and return its numeric columns (same rule as gui_main.py)."""
    global _headers, _data, _numeric_columns
    reader = csv.reader(io.StringIO(text, newline=''))
    _headers = next(reader)
    _data = list(reader)
    _numeric_columns = []
    for index, name in enumerate(_headers):
        if name == "User ID":
            continue
        try:
            for row in _data:
                float(row[index])
            _numeric_columns.append(name)
        except (ValueError, IndexError):
            continue
    return json.dumps(_numeric_columns)


class _Message(Exception):
    """A user-facing message shown instead of a result."""


def _get_values(column):
    if column not in _headers:
        raise _Message(f"Column '{column}' not found in the dataset.")
    index = _headers.index(column)
    values = []
    for row in _data:
        try:
            values.append(float(row[index]))
        except ValueError:
            continue
    if len(values) < 2:
        raise _Message("Not enough numeric data in the selected column.")
    return values


def _read_number(text, name, optional=False, positive=False):
    text = (text or "").strip()
    if not text:
        if optional:
            return None
        raise ValueError(f"Please enter a value for {name}.")
    try:
        value = float(text)
    except ValueError:
        raise ValueError(f"{name} must be a number (got '{text}').")
    if positive and value <= 0:
        raise ValueError(f"{name} must be greater than 0.")
    return value


def _describe(column, mu0, sigma, margin):
    values = _get_values(column)
    count = len(values)
    mean = st.mean(values)
    median = st.median(values)
    variance = st.sample_variance(values)
    std_dev = math.sqrt(variance)
    std_err = std_dev / math.sqrt(count)
    lines = [f"Column: {column}", f"Count: {count}", f"Mean: {mean:.2f}",
             f"Median: {median:.2f}", f"Variance: {variance:.2f}",
             f"Standard Deviation: {std_dev:.2f}", f"Standard Error: {std_err:.2f}"]
    data = dict(count=count, mean=mean, median=median, variance=variance,
                std_dev=std_dev, std_err=std_err)
    return lines, data


def _confidence_interval(column, mu0, sigma_text, margin):
    values = _get_values(column)
    sigma = _read_number(sigma_text, "σ", optional=True, positive=True)
    n = len(values)
    mean = st.mean(values)
    if sigma is not None:
        method, mode = "z (σ known)", "z"
        critical = st.z_critical(CONFIDENCE)
        std_err = sigma / math.sqrt(n)
    else:
        method, mode = f"Student's t (σ unknown, df = {n - 1})", "t"
        critical = st.t_critical(n - 1, CONFIDENCE)
        std_err = st.sample_std(values) / math.sqrt(n)
    margin_of_error = critical * std_err
    lower = mean - margin_of_error
    upper = mean + margin_of_error
    lines = [f"{CONFIDENCE:.0%} Confidence Interval for '{column}':",
             f"[{lower:.2f} , {upper:.2f}]",
             f"Margin of Error: {margin_of_error:.2f}",
             f"Method: {method}, critical value = {critical:.4f}"]
    data = dict(mode=mode, n=n, df=(n - 1 if mode == "t" else None), mean=mean,
                std_err=std_err, critical=critical, margin=margin_of_error,
                lower=lower, upper=upper, method=method, confidence=CONFIDENCE)
    return lines, data


def _hypothesis_test(column, mu0_text, sigma_text, margin):
    values = _get_values(column)
    hypothesized_mean = _read_number(mu0_text, "μ₀")
    sigma = _read_number(sigma_text, "σ", optional=True, positive=True)
    n = len(values)
    mean = st.mean(values)
    if sigma is not None:
        mode = "z"
        test_name = "One-sample z-test (σ known)"
        statistic_name = "Z-Score"
        statistic = (mean - hypothesized_mean) / (sigma / math.sqrt(n))
        critical = st.z_critical(CONFIDENCE)
        p_value = st.z_two_tailed_p(statistic)
    else:
        mode = "t"
        test_name = f"One-sample t-test (σ unknown, df = {n - 1})"
        statistic_name = "T-Statistic"
        statistic = (mean - hypothesized_mean) / (st.sample_std(values) / math.sqrt(n))
        critical = st.t_critical(n - 1, CONFIDENCE)
        p_value = st.t_two_tailed_p(statistic, n - 1)
    reject = abs(statistic) > critical
    lines = [f"Hypothesis Test for '{column}':", test_name,
             f"Null Hypothesis: μ = {hypothesized_mean:g}",
             f"Sample Mean: {mean:.2f}", f"{statistic_name}: {statistic:.2f}",
             f"p-value: {p_value:.4g}", f"Significance level: {ALPHA:.2f}",
             f"Two-tailed test (|statistic| > {critical:.4f})",
             "Result: Reject the null hypothesis." if reject
             else "Result: Fail to reject the null hypothesis."]
    data = dict(mode=mode, n=n, df=(n - 1 if mode == "t" else None), mu0=hypothesized_mean,
                mean=mean, statistic=statistic, statistic_name=statistic_name,
                p_value=p_value, alpha=ALPHA, critical=critical, reject=reject,
                test_name=test_name)
    return lines, data


def _sample_size(column, mu0, sigma_text, margin_text):
    values = _get_values(column)
    margin_of_error = _read_number(margin_text, "E", positive=True)
    sigma = _read_number(sigma_text, "σ", optional=True, positive=True)
    if sigma is None:
        std_dev = st.sample_std(values)
        source, mode = "sample standard deviation of the selected column", "t"
    else:
        std_dev = sigma
        source, mode = "entered σ", "z"
    z = st.z_critical(CONFIDENCE)
    n = math.ceil(((z * std_dev) / margin_of_error) ** 2)
    lines = [f"Sample Size Estimation for '{column}':",
             f"Estimated sample size needed: {n}",
             f"(Using std dev = {std_dev:.2f} from the {source}, "
             f"margin of error = {margin_of_error:g}, confidence = {CONFIDENCE:.0%})"]
    data = dict(n=n, std_dev=std_dev, source=source, source_mode=mode, z=z,
                margin=margin_of_error, confidence=CONFIDENCE)
    return lines, data


def _quartiles(values):
    s = sorted(values)
    q1 = st.percentile(s, 0.25)
    q3 = st.percentile(s, 0.75)
    return s, q1, q3, q3 - q1


def _outliers(column, mu0, sigma, margin):
    values = _get_values(column)
    values.sort()
    q1 = st.percentile(values, 0.25)
    q3 = st.percentile(values, 0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    outliers = [x for x in values if x < lower or x > upper]
    lines = [f"Outlier Detection for '{column}':", f"Q1: {q1:.2f}", f"Q3: {q3:.2f}",
             f"IQR: {iqr:.2f}", f"Lower Bound: {lower:.2f}", f"Upper Bound: {upper:.2f}",
             f"Number of Outliers: {len(outliers)}"]
    if outliers:
        lines.append("Example Outliers: " + ", ".join(f"{x:.1f}" for x in outliers[:5]))
    data = dict(q1=q1, q3=q3, iqr=iqr, lower=lower, upper=upper,
                count=len(outliers), outliers=outliers)
    return lines, data


def _charts(column, mu0, sigma, margin):
    """Histogram (20 equal-width bins, numpy/matplotlib convention) and box-plot numbers."""
    values = _get_values(column)
    s, q1, q3, iqr = _quartiles(values)
    lo, hi = s[0], s[-1]
    if lo == hi:
        lo, hi = lo - 0.5, hi + 0.5
    step = (hi - lo) / BINS
    edges = [lo + i * step for i in range(BINS)] + [hi]
    counts = [0] * BINS
    for x in s:
        counts[min(bisect_right(edges, x) - 1, BINS - 1)] += 1
    lower_fence = q1 - 1.5 * iqr
    upper_fence = q3 + 1.5 * iqr
    inside = [x for x in s if lower_fence <= x <= upper_fence]
    whisker_low = inside[0] if inside else q1
    whisker_high = inside[-1] if inside else q3
    fliers = [x for x in s if x < lower_fence or x > upper_fence]
    lines = [f"Visual plots for '{column}' displayed below."]
    data = dict(edges=edges, counts=counts, median=st.median(values), q1=q1, q3=q3,
                whisker_low=whisker_low, whisker_high=whisker_high, fliers=fliers,
                count=len(values))
    return lines, data


_ACTIONS = {
    "describe": (_describe, "Descriptive Stats", "Error during analysis"),
    "ci": (_confidence_interval, "Confidence Interval", "Error calculating confidence interval"),
    "test": (_hypothesis_test, "Hypothesis Test", "Error performing hypothesis test"),
    "size": (_sample_size, "Sample Size", "Error calculating sample size"),
    "outliers": (_outliers, "Outliers", "Error detecting outliers"),
    "charts": (_charts, "Charts", "Error displaying image"),
}


def run(action, column, mu0_text="", sigma_text="", margin_text=""):
    """Run one analysis; always returns a JSON string (floats keep full precision)."""
    func, title, error_prefix = _ACTIONS[action]
    try:
        lines, data = func(column, mu0_text, sigma_text, margin_text)
        return json.dumps(dict(ok=True, action=action, title=title, column=column,
                               lines=lines, data=data))
    except _Message as e:
        return json.dumps(dict(ok=False, action=action, error=str(e)))
    except Exception as e:
        return json.dumps(dict(ok=False, action=action, error=f"{error_prefix}: {e}"))
