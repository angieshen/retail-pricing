import json
import uuid
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from psycopg.types.json import Jsonb
from db import WORK, connect, fetch

FORMULA = "log_units ~ log_price + C(stock_code) + C(weekday) + trend_years"


def features(data, price):
    result = data.copy()
    result["log_units"] = np.log(result.units_sold.astype(float))
    result["log_price"] = np.log(result[price].astype(float))
    result["trend_years"] = result.time_index / 365
    return result


def fit(data, price):
    transformed = features(data, price)
    model = smf.ols(FORMULA, data=transformed).fit()
    smear = float(np.exp(model.resid).mean())
    return model, smear


def predict(model, smear, data, price):
    return np.exp(model.predict(features(data, price))) * smear


def score(actual, predicted):
    errors = np.abs(np.asarray(actual) - np.asarray(predicted))
    return {"mae": float(errors.mean()),
            "wape": float(errors.sum() / np.asarray(actual).sum())}


data = fetch("SELECT * FROM modeling_daily_sales ORDER BY sale_date, stock_code")
data["sale_date"] = pd.to_datetime(data.sale_date)
for column in ["units_sold", "weighted_unit_price", "median_line_price"]:
    data[column] = data[column].astype(float)
dates = np.sort(data.sale_date.unique())
validation_start = dates[int(0.6 * len(dates))]
test_start = dates[int(0.8 * len(dates))]
train = data[data.sale_date < validation_start]
validation = data[(data.sale_date >= validation_start) & (data.sale_date < test_start)]
development = data[data.sale_date < test_start]
test = data[data.sale_date >= test_start]
assert train.sale_date.max() < validation.sale_date.min()
assert validation.sale_date.max() < test.sale_date.min()
for name, frame in [("train", train), ("validation", validation), ("test", test)]:
    print(name, len(frame), frame.sale_date.min(), frame.sale_date.max())

validation_scores = {}
means = train.groupby("stock_code").units_sold.mean()
validation_scores["baseline"] = score(validation.units_sold, validation.stock_code.map(means))
for price in ["weighted_unit_price", "median_line_price"]:
    model, smear = fit(train, price)
    validation_scores[price] = score(validation.units_sold, predict(model, smear, validation, price))
chosen_price = min(["weighted_unit_price", "median_line_price"],
                   key=lambda name: validation_scores[name]["mae"])
winner = min(validation_scores, key=lambda name: validation_scores[name]["mae"])
print("Validation:", validation_scores)
print("Chosen regression price:", chosen_price, "Overall winner:", winner)
model, smear = fit(development, chosen_price)
transformed = features(development, chosen_price)
robust = model.get_robustcov_results(
    cov_type="hac-groupsum",
    time=development.time_index.to_numpy(dtype=int),
    maxlags=7, use_correction="hac", df_correction=False, use_t=False,
)
beta_index = model.model.exog_names.index("log_price")
low, high = robust.conf_int()[beta_index]
elasticity = {"estimate": float(model.params["log_price"]),
              "low": float(low), "high": float(high)}
assert np.isfinite(robust.conf_int()).all()

predictions = test[["stock_code", "sale_date", "units_sold"]].copy()
development_means = development.groupby("stock_code").units_sold.mean()
predictions["baseline"] = test.stock_code.map(development_means)
predictions["regression"] = predict(model, smear, test, chosen_price)
rows = []
for name in ["baseline", "regression"]:
    rows.append({"product": "all", "model": name,
                 **score(predictions.units_sold, predictions[name])})
    for code, group in predictions.groupby("stock_code"):
        rows.append({"product": code, "model": name,
                     **score(group.units_sold, group[name])})
evaluation = pd.DataFrame(rows)
print(evaluation)
print("Elasticity:", elasticity, "Smearing:", smear)
predictions.to_csv(WORK / "reports/predictions.csv", index=False)
evaluation.to_csv(WORK / "reports/metrics.csv", index=False)

diagnostics = development[["stock_code", "sale_date", "units_sold"]].copy()
diagnostics["log_residual"] = model.resid
diagnostics["log_fitted"] = model.fittedvalues
diagnostics["cooks_distance"] = model.get_influence().cooks_distance[0]
diagnostics.to_csv(WORK / "reports/diagnostics.csv", index=False)

for price in ["weighted_unit_price", "median_line_price"]:
    alternative, _ = fit(development, price)
    print("Price sensitivity:", price, alternative.params["log_price"])
thresholds = development.groupby("stock_code").units_sold.quantile(0.99)
trimmed = development[development.units_sold <= development.stock_code.map(thresholds)]
alternative, _ = fit(trimmed, chosen_price)
print("Without top 1% daily-unit observations:", alternative.params["log_price"])
run_id = str(uuid.uuid4())
directory = WORK / "artifacts" / run_id
directory.mkdir(parents=True)
model.save(str(directory / "regression.pickle"))
metadata = {
    "run_id": run_id, "price": chosen_price, "winner": winner,
    "formula": FORMULA, "smear": smear, "elasticity": elasticity,
    "training_start": str(development.sale_date.min().date()),
    "training_end": str(development.sale_date.max().date()),
    "validation_start": str(pd.Timestamp(validation_start).date()),
    "test_start": str(pd.Timestamp(test_start).date()),
    "weekdays": sorted(map(int, development.weekday.unique())),
    "price_support": development.groupby("stock_code")[chosen_price].agg(["min", "max"]).to_dict("index"),
}
(directory / "metadata.json").write_text(json.dumps(metadata, indent=2))
with connect() as connection:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS learning_model_runs (
            run_id UUID PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            metadata JSONB NOT NULL,
            metrics JSONB NOT NULL,
            model_directory TEXT NOT NULL
        )
    """)
    connection.execute("""
        INSERT INTO learning_model_runs (run_id, metadata, metrics, model_directory)
        VALUES (%s, %s, %s, %s)
    """, (run_id, Jsonb(metadata), Jsonb(evaluation.to_dict("records")), str(directory.relative_to(WORK))))
print("Saved run", run_id)