SELECT country, COUNT(*) AS rows
FROM retail_transactions
GROUP BY country ORDER BY rows DESC LIMIT 10;

SELECT COUNT(*) AS raw_rows,
       COUNT(*) FILTER (WHERE customer_id IS NULL) AS missing_customer,
       COUNT(*) FILTER (WHERE invoice_no ILIKE 'C%') AS cancellations,
       COUNT(*) FILTER (WHERE quantity <= 0) AS nonpositive_quantity,
       COUNT(*) FILTER (WHERE unit_price <= 0) AS nonpositive_price
FROM retail_transactions;

SELECT
    COUNT(*) FILTER (WHERE quantity > 0 AND unit_price > 0
                    AND invoice_no NOT ILIKE 'C%') AS included,
    COUNT(*) FILTER (WHERE NOT (quantity > 0 AND unit_price > 0
                    AND invoice_no NOT ILIKE 'C%')) AS excluded
FROM retail_transactions;

SELECT invoice_no, stock_code, COUNT(*) AS lines,
       COUNT(DISTINCT unit_price) AS prices
FROM retail_transactions
GROUP BY invoice_no, stock_code
HAVING COUNT(*) > 1
ORDER BY lines DESC LIMIT 10;

SELECT stock_code, MIN(description) AS example_description, COUNT(*) AS rows
FROM retail_transactions
WHERE stock_code !~ '^[0-9]{5}[A-Za-z]*$'
GROUP BY stock_code ORDER BY rows DESC;

SELECT stock_code, description, quantity, unit_price, invoice_no
FROM retail_transactions
ORDER BY ABS(quantity) DESC LIMIT 10;