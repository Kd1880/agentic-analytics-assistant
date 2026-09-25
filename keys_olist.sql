-- Olist: primary keys, foreign keys, indexes, and timestamp casts.
-- Run AFTER load_csv_to_postgres.py (with --strip-prefix olist_ --strip-suffix _dataset).
-- Tables expected: customers, orders, order_items, order_payments,
--                  order_reviews, products, sellers, geolocation,
--                  product_category_name_translation
-- NOTE: Olist is real, slightly messy data. If any FOREIGN KEY line errors with
--       "violates foreign key" it means orphan rows exist — comment that one line
--       out (or clean the orphans) and continue. PKs/indexes below are always safe.

-- ---- cast timestamp columns (loaded as text) ----
ALTER TABLE orders
  ALTER COLUMN order_purchase_timestamp        TYPE timestamp USING NULLIF(order_purchase_timestamp,'')::timestamp,
  ALTER COLUMN order_approved_at               TYPE timestamp USING NULLIF(order_approved_at,'')::timestamp,
  ALTER COLUMN order_delivered_carrier_date    TYPE timestamp USING NULLIF(order_delivered_carrier_date,'')::timestamp,
  ALTER COLUMN order_delivered_customer_date   TYPE timestamp USING NULLIF(order_delivered_customer_date,'')::timestamp,
  ALTER COLUMN order_estimated_delivery_date   TYPE timestamp USING NULLIF(order_estimated_delivery_date,'')::timestamp;

ALTER TABLE order_reviews
  ALTER COLUMN review_creation_date   TYPE timestamp USING NULLIF(review_creation_date,'')::timestamp,
  ALTER COLUMN review_answer_timestamp TYPE timestamp USING NULLIF(review_answer_timestamp,'')::timestamp;

-- ---- primary keys (dimension tables) ----
ALTER TABLE customers  ADD PRIMARY KEY (customer_id);
ALTER TABLE orders     ADD PRIMARY KEY (order_id);
ALTER TABLE products   ADD PRIMARY KEY (product_id);
ALTER TABLE sellers    ADD PRIMARY KEY (seller_id);
ALTER TABLE product_category_name_translation ADD PRIMARY KEY (product_category_name);

-- ---- foreign keys (comment out any that error on orphan rows) ----
ALTER TABLE orders        ADD FOREIGN KEY (customer_id) REFERENCES customers(customer_id);
ALTER TABLE order_items   ADD FOREIGN KEY (order_id)   REFERENCES orders(order_id);
ALTER TABLE order_items   ADD FOREIGN KEY (product_id) REFERENCES products(product_id);
ALTER TABLE order_items   ADD FOREIGN KEY (seller_id)  REFERENCES sellers(seller_id);
ALTER TABLE order_payments ADD FOREIGN KEY (order_id)  REFERENCES orders(order_id);
ALTER TABLE order_reviews  ADD FOREIGN KEY (order_id)  REFERENCES orders(order_id);
ALTER TABLE products       ADD FOREIGN KEY (product_category_name) REFERENCES product_category_name_translation(product_category_name);

-- ---- indexes on join keys ----
CREATE INDEX IF NOT EXISTS idx_items_order    ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_items_product  ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_items_seller   ON order_items(seller_id);
CREATE INDEX IF NOT EXISTS idx_pay_order      ON order_payments(order_id);
CREATE INDEX IF NOT EXISTS idx_rev_order      ON order_reviews(order_id);
CREATE INDEX IF NOT EXISTS idx_orders_cust    ON orders(customer_id);
