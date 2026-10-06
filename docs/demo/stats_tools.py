# Hand-written statistics helpers (standard library only: no NumPy / SciPy)
import math


# ---------- Descriptive statistics ----------

def mean(values):
    return sum(values) / len(values)


def median(values):
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 == 1 else (s[n // 2 - 1] + s[n // 2]) / 2


def sample_variance(values):
    m = mean(values)
    return sum((x - m) ** 2 for x in values) / (len(values) - 1)


def sample_std(values):
    return math.sqrt(sample_variance(values))


def percentile(sorted_values, p):
    # Linear interpolation between closest ranks (same as statistics.quantiles(method="inclusive"))
    n = len(sorted_values)
    k = (n - 1) * p
    f = int(k)
    c = min(f + 1, n - 1)
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


# ---------- Normal distribution ----------

def normal_cdf(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


# ---------- Student's t distribution ----------

def _beta_continued_fraction(a, b, x):
    # Continued fraction for the incomplete beta function (modified Lentz's method)
    tiny = 1e-300
    c, d = 1.0, 1.0 - (a + b) * x / (a + 1)
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        for numerator in (m * (b - m) * x / ((a + m2 - 1) * (a + m2)),
                          -(a + m) * (a + b + m) * x / ((a + m2) * (a + m2 + 1))):
            d = 1.0 + numerator * d
            d = 1.0 / (d if abs(d) > tiny else tiny)
            c = 1.0 + numerator / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1.0) < 1e-15:
            break
    return h


def regularized_incomplete_beta(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    log_front = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                 + a * math.log(x) + b * math.log(1 - x))
    # Use the symmetry relation where the continued fraction converges fastest
    if x < (a + 1) / (a + b + 2):
        return math.exp(log_front) * _beta_continued_fraction(a, b, x) / a
    return 1.0 - math.exp(log_front) * _beta_continued_fraction(b, a, 1 - x) / b


def t_cdf(t, df):
    x = df / (df + t * t)
    tail = 0.5 * regularized_incomplete_beta(df / 2, 0.5, x)
    return 1 - tail if t >= 0 else tail


# ---------- Critical values and p-values ----------

def _bisect(cdf, target, lo, hi):
    for _ in range(200):
        mid = (lo + hi) / 2
        if cdf(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def z_critical(confidence=0.95):
    return _bisect(normal_cdf, 1 - (1 - confidence) / 2, 0.0, 40.0)


def t_critical(df, confidence=0.95):
    return _bisect(lambda t: t_cdf(t, df), 1 - (1 - confidence) / 2, 0.0, 1e6)


def z_two_tailed_p(z):
    return 2 * (1 - normal_cdf(abs(z)))


def t_two_tailed_p(t, df):
    return 2 * (1 - t_cdf(abs(t), df))
