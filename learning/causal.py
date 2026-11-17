import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from db import WORK

TRUE_BETA = -1.5


def generate(seed, n=730, noise_sd=0.25):
    rng = np.random.default_rng(seed)
    day = np.arange(n)
    driver = rng.normal(size=n)
    price_noise = rng.normal(size=n)
    randomized_noise = rng.normal(size=n)
    noise = rng.normal(scale=noise_sd, size=n)
    weekday = day % 7 + 1
    trend = day / 365
    base = 4.5 + 0.8*driver + 0.15*(weekday >= 6) + 0.1*trend + noise
    observed_price = np.log(2) + 0.25*driver + 0.15*price_noise
    assigned_price = np.log(2) + np.sqrt(0.25**2+0.15**2)*randomized_noise

    def frame(log_price):
        return pd.DataFrame({"log_price": log_price,
            "log_units": base + TRUE_BETA*log_price,
            "demand_driver": driver, "weekday": weekday, "trend": trend})
    return frame(observed_price), frame(assigned_price)


def estimate(data, adjusted=False):
    formula = "log_units ~ log_price + C(weekday) + trend"
    if adjusted:
        formula += " + demand_driver"
    model = smf.ols(formula, data).fit(cov_type="HC3", use_t=False)
    low, high = model.conf_int().loc["log_price"]
    return {"estimate": float(model.params["log_price"]),
            "low": float(low), "high": float(high),
            "covered": bool(low <= TRUE_BETA <= high)}


if __name__ == "__main__":
    results = []
    for seed in range(20261030, 20261030+200):
        observed, randomized = generate(seed)
        for name, sample, adjusted in [
            ("naive", observed, False),
            ("adjusted", observed, True),
            ("randomized", randomized, False),
        ]:
            results.append({"seed": seed, "method": name,
                            **estimate(sample, adjusted)})
    results = pd.DataFrame(results)
    results.to_csv(WORK / "reports/causal_estimates.csv", index=False)
    summary = []
    for method, group in results.groupby("method"):
        error = group.estimate - TRUE_BETA
        summary.append({"method": method, "mean_estimate": group.estimate.mean(),
            "bias": error.mean(), "rmse": np.sqrt((error**2).mean()),
            "coverage": group.covered.mean()})
    summary = pd.DataFrame(summary)
    summary.to_csv(WORK / "reports/causal_summary.csv", index=False)
    print(summary)