from datetime import date
from decimal import Decimal
import json
import uuid
import numpy as np
import pandas as pd
import statsmodels.api as sm
from psycopg.types.json import Jsonb
from db import WORK, connect, fetch


def load_run():
    runs = fetch("SELECT * FROM learning_model_runs ORDER BY created_at DESC LIMIT 1")
    if runs.empty:
        raise ValueError("Train a model first")
    run = runs.iloc[0]
    directory = WORK / run.model_directory
    metadata = json.loads((directory / "metadata.json").read_text())
    model = sm.load(str(directory / "regression.pickle"))
    return model, metadata, run.metrics


def daily_data():
    data = fetch("SELECT * FROM modeling_daily_sales ORDER BY sale_date, stock_code")
    data["sale_date"] = pd.to_datetime(data.sale_date)
    for column in ["units_sold", "revenue", "weighted_unit_price", "median_line_price"]:
        data[column] = data[column].astype(float)
    return data


def make_scenario(model, metadata, data, code, day, change=0.10):
    if not 0 <= change <= 0.10:
        raise ValueError("Maximum price change must be between 0 and 0.10")
    result = {"product": code, "date": str(day), "status": "unsupported",
              "recommended_price": None, "reasons": [], "grid": []}
    if code not in metadata["price_support"]:
        result["reasons"].append("Unknown product")
        return result
    if not date.fromisoformat(metadata["training_start"]) <= day <= date.fromisoformat(metadata["training_end"]):
        result["reasons"].append("Date outside training window")
        return result
    if day.isoweekday() not in metadata["weekdays"]:
        result["reasons"].append("Weekday not observed during fitting")
        return result
    history = data[(data.stock_code == code) & (data.sale_date.dt.date <= day)]
    if history.empty:
        result["reasons"].append("No reference price yet")
        return result
    reference = history.iloc[-1]
    price = float(reference[metadata["price"]])
    support = metadata["price_support"][code]
    if not support["min"] <= price <= support["max"]:
        result["reasons"].append("Reference price outside development support")
        return result
    lower = max(support["min"], price*(1-change))
    upper = min(support["max"], price*(1+change))
    prices = sorted(set(np.linspace(lower, upper, 101).tolist() + [price]))

    def project(candidate):
        inputs = pd.DataFrame({"stock_code": [code], "weekday": [day.isoweekday()],
            "trend_years": [(day-date(2010, 12, 1)).days/365],
            "log_price": [np.log(candidate)]})
        units = float(np.exp(model.predict(inputs).iloc[0])*metadata["smear"])
        return units, candidate*units

    reference_units, reference_revenue = project(price)
    beta = metadata["elasticity"]
    for candidate in prices:
        units, revenue = project(candidate)
        interval = [(candidate/price)**(1+b)-1 for b in [beta["low"], beta["high"]]]
        result["grid"].append({"price": candidate, "units": units, "revenue": revenue,
            "relative_change": revenue/reference_revenue-1,
            "slope_only_low": min(interval), "slope_only_high": max(interval)})
    if metadata["winner"] == "baseline":
        result["reasons"].append("Regression did not win validation")
    if beta["high"] >= 0:
        result["reasons"].append("Negative price association not established")
    result["status"] = "unsupported" if result["reasons"] else "scenario_only"
    result["reasons"].append("Observational association is not causal")
    result.update(reference_price=price, reference_date=str(reference.sale_date.date()),
        reference_units=reference_units, reference_revenue=reference_revenue,
        lower=lower, upper=upper, max_change=change,
        best=max(result["grid"], key=lambda row: row["revenue"]))
    assert all(lower <= row["price"] <= upper for row in result["grid"])
    return result


def save_scenario(metadata, result):
    scenario_id = str(uuid.uuid4())
    with connect() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS learning_price_scenarios (
                scenario_id UUID PRIMARY KEY,
                model_run_id UUID NOT NULL REFERENCES learning_model_runs(run_id),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                product TEXT NOT NULL,
                scenario_date DATE NOT NULL,
                reference_price NUMERIC,
                status TEXT NOT NULL,
                recommended_price NUMERIC CHECK (recommended_price IS NULL),
                results JSONB NOT NULL
            )
        """)
        reference = result.get("reference_price")
        connection.execute("""
            INSERT INTO learning_price_scenarios
            (scenario_id, model_run_id, product, scenario_date, reference_price,
             status, recommended_price, results)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (scenario_id, metadata["run_id"], result["product"], result["date"],
              None if reference is None else Decimal(str(reference)),
              result["status"], None, Jsonb(result)))


if __name__ == "__main__":
    model, metadata, _ = load_run()
    data = daily_data()
    day = date.fromisoformat(metadata["training_end"])
    for code in metadata["price_support"]:
        result = make_scenario(model, metadata, data, code, day)
        save_scenario(metadata, result)
        print(code, result["status"], result.get("best"), result["reasons"])