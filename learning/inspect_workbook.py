from itertools import islice
import openpyxl
from db import ROOT

book = openpyxl.load_workbook(
    ROOT / "Online Retail.xlsx", read_only=True, data_only=True
)
try:
    sheet = book.active
    for row in islice(sheet.iter_rows(values_only=True), 6):
        print(row)
finally:
    book.close()