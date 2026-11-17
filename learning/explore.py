import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from db import WORK, fetch

data = fetch("SELECT * FROM modeling_daily_sales ORDER BY sale_date, stock_code")
data["sale_date"] = pd.to_datetime(data["sale_date"])
for column in ["units_sold", "revenue", "weighted_unit_price",
               "median_line_price", "identified_customer_price"]:
    data[column] = data[column].astype(float)

assert not data.duplicated(["stock_code", "country", "sale_date"]).any()
assert data.units_sold.gt(0).all()
data.to_csv(WORK / "reports/daily.csv", index=False)

transactions = fetch("SELECT * FROM pricing_transactions ORDER BY invoice_date")
transactions["invoice_date"] = pd.to_datetime(transactions["invoice_date"])
transactions["unit_price"] = transactions["unit_price"].astype(float)

for code, product in data.groupby("stock_code"):
    product = product.set_index("sale_date")
    weekly = product[["units_sold", "revenue", "invoice_count"]].resample("W-SUN").sum()
    figure, axes = plt.subplots(3, 1, figsize=(10, 8), constrained_layout=True)
    for axis, column in zip(axes, weekly.columns):
        axis.plot(weekly.index, weekly[column])
        axis.set_ylabel(column)
    figure.suptitle(f"{code}: observed weekly sales")
    figure.savefig(WORK / f"reports/{code}_weekly.png", dpi=120)
    plt.close(figure)

    prices = product[["weighted_unit_price", "median_line_price",
                      "identified_customer_price"]]
    axis = prices.plot(figsize=(10, 4), title=f"{code}: daily transaction prices")
    axis.set_ylabel("Price in workbook units")
    axis.figure.tight_layout()
    axis.figure.savefig(WORK / f"reports/{code}_prices.png", dpi=120)
    plt.close(axis.figure)

    lines = transactions[transactions.stock_code == code]
    figure, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    axes[0].hist(lines.unit_price, bins=30)
    axes[0].set(xlabel="Transaction price", ylabel="Line count")
    axes[1].scatter(lines.unit_price, lines.quantity, alpha=0.25, s=8)
    axes[1].set_yscale("log")
    axes[1].set(xlabel="Transaction price", ylabel="Quantity per line (log scale)")
    figure.suptitle(code)
    figure.savefig(WORK / f"reports/{code}_purchase_mix.png", dpi=120)
    plt.close(figure)

print(data.groupby("stock_code").agg(
    observed_days=("sale_date", "size"), units=("units_sold", "sum")
))
lines = transactions[transactions.stock_code == "20725"]
identified = lines[lines.customer_id.notna()]
for name, group in [("all", lines), ("identified", identified)]:
    weighted = (group.quantity * group.unit_price).sum() / group.quantity.sum()
    print(name, weighted)