CREATE TABLE IF NOT EXISTS retail_transactions (
    source_file TEXT NOT NULL,
    source_row INTEGER NOT NULL,
    invoice_no TEXT NOT NULL,
    stock_code TEXT NOT NULL,
    description TEXT,
    quantity INTEGER NOT NULL,
    invoice_date TIMESTAMP NOT NULL,
    unit_price NUMERIC NOT NULL,
    customer_id TEXT,
    country TEXT NOT NULL,
    PRIMARY KEY (source_file, source_row)
);