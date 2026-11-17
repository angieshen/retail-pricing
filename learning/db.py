from pathlib import Path
import os

import pandas as pd
import psycopg

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "learning"


def connect():
    config = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            config[key.strip()] = value.strip()
    config.update(os.environ)
    return psycopg.connect(
        host="127.0.0.1",
        port=config.get("POSTGRES_PORT", "5434"),
        dbname="retail_learning",
        user="retail",
        password=config["POSTGRES_PASSWORD"],
    )


def fetch(sql):
    with connect() as connection:
        cursor = connection.execute(sql)
        return pd.DataFrame(
            cursor.fetchall(),
            columns=[column.name for column in cursor.description],
        )


if __name__ == "__main__":
    print(fetch("SELECT current_database() AS database"))