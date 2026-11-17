CREATE OR REPLACE VIEW pricing_transactions AS
SELECT * FROM retail_transactions
WHERE country = 'United Kingdom'
  AND invoice_date >= DATE '2010-12-01'
  AND invoice_date < DATE '2011-12-01'
  AND quantity > 0 AND unit_price > 0
  AND invoice_no NOT ILIKE 'C%'
  AND stock_code IN ('85099B','85123A','22197','21212','20725','47566');

CREATE OR REPLACE VIEW modeling_daily_sales AS
SELECT stock_code, country, invoice_date::date AS sale_date,
       EXTRACT(ISODOW FROM invoice_date::date)::integer AS weekday,
       invoice_date::date - DATE '2010-12-01' AS time_index,
       SUM(quantity) AS units_sold,
       SUM(quantity * unit_price) AS revenue,
       SUM(quantity * unit_price) / SUM(quantity) AS weighted_unit_price,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY unit_price) AS median_line_price,
       COUNT(DISTINCT unit_price) AS distinct_prices,
       COUNT(*) AS sales_lines,
       COUNT(DISTINCT invoice_no) AS invoice_count,
       COUNT(*) FILTER (WHERE customer_id IS NULL) AS missing_customer_lines,
       SUM(quantity * unit_price) FILTER (WHERE customer_id IS NOT NULL)
         / NULLIF(SUM(quantity) FILTER (WHERE customer_id IS NOT NULL), 0)
         AS identified_customer_price,
       MAX(quantity) AS max_line_quantity
FROM pricing_transactions
GROUP BY stock_code, country, invoice_date::date;