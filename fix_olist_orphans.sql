-- Olist data fix: 2 categories in `products` have no English translation,
-- which blocks the products -> product_category_name_translation foreign key.
-- Run AFTER keys_olist.sql. Adds the 2 missing translations, then adds the FK.
-- Safe to re-run: the INSERT skips existing rows, and the FK is dropped/re-added by name.

INSERT INTO product_category_name_translation (product_category_name, product_category_name_english)
VALUES ('pc_gamer', 'pc_gamer'),
       ('portateis_cozinha_e_preparadores_de_alimentos', 'portable_kitchen_food_processors')
ON CONFLICT (product_category_name) DO NOTHING;

ALTER TABLE products DROP CONSTRAINT IF EXISTS products_product_category_name_fkey;
ALTER TABLE products ADD CONSTRAINT products_product_category_name_fkey
    FOREIGN KEY (product_category_name)
    REFERENCES product_category_name_translation(product_category_name);
