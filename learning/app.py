from datetime import date
from pathlib import Path
import sys
import pandas as pd
import streamlit as st
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import WORK
from scenarios import load_run, daily_data, make_scenario

st.set_page_config(page_title="My Retail Pricing Explorer", layout="wide")
st.title("My Retail Pricing Explorer")
st.write("Historical sales analysis and conditional price scenarios")
model, metadata, metrics = load_run()
data = daily_data()
code = st.sidebar.selectbox("Product", sorted(data.stock_code.unique()))
product = data[data.stock_code == code].set_index("sale_date")
st.caption(f"Model {metadata['run_id']}; fitted through {metadata['training_end']}")
st.warning("Observed associations do not prove causal price effects. No validated revenue gain is claimed.")

history, evaluation, pricing, causal = st.tabs(["History", "Evaluation", "Scenarios", "Causal simulation"])
with history:
    st.subheader("Weekly observed units")
    st.line_chart(product[["units_sold"]].resample("W-SUN").sum())
    st.subheader("Daily transaction prices")
    st.line_chart(product[["weighted_unit_price", "median_line_price"]])
    st.caption("Missing product-days have unknown availability, not proven zero demand. Boundary weeks may be partial.")
with evaluation:
    st.write("Validation winner:", metadata["winner"])
    st.write("Elasticity and 95% interval:", metadata["elasticity"])
    st.dataframe(pd.DataFrame(metrics))
    st.caption("WAPE is a fraction. Evaluation is conditional on observed selling days and transaction prices.")
with pricing:
    day = st.date_input("Historical scenario date",
        value=date.fromisoformat(metadata["training_end"]),
        min_value=date.fromisoformat(metadata["training_start"]),
        max_value=date.fromisoformat(metadata["training_end"]))
    change = st.slider("Maximum price change (%)", 0, 10, 10)
    result = make_scenario(model, metadata, data, code, day, change/100)
    st.write("Status:", result["status"])
    st.write("Reasons:", result["reasons"])
    st.write("Recommended price: unavailable")
    if result["grid"]:
        st.write("Reference price/date:", result["reference_price"], result["reference_date"])
        curve = pd.DataFrame(result["grid"])
        st.line_chart(curve.set_index("price")[["revenue"]])
        st.write("Exploratory grid maximum:", result["best"])
        st.caption("Slope-only ranges are not full prediction intervals. Boundary maxima reflect the model assumptions.")
with causal:
    st.write("Synthetic experiment only; true elasticity = -1.5")
    path = WORK / "reports/causal_summary.csv"
    if path.exists():
        st.dataframe(pd.read_csv(path))
    else:
        st.info("Run learning/causal.py first")