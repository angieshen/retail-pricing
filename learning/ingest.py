import openpyxl
from db import ROOT, WORK, connect

EXPECTED = (
    "InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate",
    "UnitPrice", "CustomerID", "Country",
)


def identifier(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def main():
    filename = "Online Retail.xlsx"
    book = openpyxl.load_workbook(
        ROOT / filename, read_only=True, data_only=True
    )
    try:
        rows = book.active.iter_rows(values_only=True)
        if tuple(next(rows)) != EXPECTED:
            raise ValueError("Unexpected workbook columns")

        with connect() as connection:
            connection.execute((WORK / "schema.sql").read_text())
            connection.execute(
                "DELETE FROM retail_transactions WHERE source_file = %s",
                (filename,),
            )
            count = 0
            with connection.cursor().copy(
                "COPY retail_transactions FROM STDIN"
            ) as copy:
                for row_number, row in enumerate(rows, start=2):
                    invoice, stock, description, quantity, when, price, customer, country = row
                    if any(value is None for value in (invoice, stock, quantity, when, price, country)):
                        raise ValueError(f"Missing required value on row {row_number}")
                    if int(quantity) != quantity:
                        raise ValueError(f"Noninteger quantity on row {row_number}")
                    copy.write_row((
                        filename, row_number, identifier(invoice), identifier(stock),
                        description, int(quantity), when, price,
                        None if customer is None else identifier(customer), country,
                    ))
                    count += 1
        print(f"Committed {count:,} rows")
    finally:
        book.close()


if __name__ == "__main__":
    main()