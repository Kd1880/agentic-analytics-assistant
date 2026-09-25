"""
seed_memory.py — build the TRAINING POOL for example memory (Phase 6a).

DESIGN: the pool is DISJOINT from the 45 gold questions. None of these
questions appears in gold_questions.md; they are new questions that exercise
the SAME SQL TECHNIQUES the gold set tests, in the SAME database (retrieval is
scoped per-db). Train/test overlap is therefore structurally impossible, not
merely guarded against.

This replaces the Phase 4 seeding (gold questions + leave-one-out), where every
technique appeared exactly once and always on the question under test, so
leave-one-out removed the only useful example. That store is kept as
memory_store_goldseed_phase4.json for reproducing the Phase 4 results.

Every pair is EXECUTED before storage. A training example with wrong SQL
teaches the wrong thing.
"""

from db import DATABASES, get_engine, run_sql
from memory import Memory

# technique -> the gold questions it covers (documentation, not used at runtime)
TECHNIQUE_COVERAGE = {
    "movielens": {
        "simple-aggregate": "ml#1,2,3", "per-group-aggregate": "ml#4,8,10",
        "having-min-count": "ml#5,11", "unnest-multivalue": "ml#6,8",
        "argmax-top1": "ml#7", "year-from-title": "ml#9",
        "window-top1-per-group": "ml#12", "distribution-counts": "ml#13",
        "anti-join": "ml#14", "epoch-bucketing": "ml#15",
    },
    "olist": {
        "simple-aggregate": "ol#1,2", "revenue-topn": "ol#3,9",
        "per-group-aggregate": "ol#5,10,13", "distribution-counts": "ol#4,8",
        "date-diff-days": "ol#6", "conditional-percentage": "ol#7",
        "monthly-bucketing": "ol#11", "having-min-count": "ol#12",
        "nested-aggregate": "ol#14", "repeat-entity": "ol#15",
    },
    "soccer": {
        "simple-aggregate": "sc#1,2", "per-group-aggregate": "sc#3,4,10,12",
        "argmax-top1": "sc#5,8,13", "home-away-union": "sc#6,9",
        "case-wld-counting": "sc#7,11,14", "anti-join": "sc#15",
    },
}

# (id, db, technique, question, sql)
POOL = [
    # ================= MovieLens =================
    ("tp:ml-agg-1", "movielens", "simple-aggregate",
     "How many tags are in the database?",
     "SELECT COUNT(*) AS n_tags FROM tags"),
    ("tp:ml-agg-2", "movielens", "simple-aggregate",
     "What is the highest rating any movie has received?",
     "SELECT MAX(rating) AS highest_rating FROM ratings"),
    ("tp:ml-agg-3", "movielens", "simple-aggregate",
     "How many different users have rated at least one movie?",
     "SELECT COUNT(DISTINCT userid) AS n_users FROM ratings"),

    ("tp:ml-grp-1", "movielens", "per-group-aggregate",
     "Which 10 movies have the most tags?",
     "SELECT m.title, COUNT(*) AS n_tags FROM tags t "
     "JOIN movies m ON m.movieid = t.movieid "
     "GROUP BY m.movieid, m.title ORDER BY n_tags DESC LIMIT 10"),
    ("tp:ml-grp-2", "movielens", "per-group-aggregate",
     "What is the average rating of each movie whose title starts with 'Star'?",
     "SELECT m.title, AVG(r.rating) AS avg_rating, COUNT(*) AS n_ratings FROM ratings r "
     "JOIN movies m ON m.movieid = r.movieid WHERE m.title LIKE 'Star%' "
     "GROUP BY m.movieid, m.title ORDER BY avg_rating DESC"),
    ("tp:ml-grp-3", "movielens", "per-group-aggregate",
     "How many different movies has each user tagged? Show the top 10 users.",
     "SELECT t.userid, COUNT(DISTINCT t.movieid) AS n_movies FROM tags t "
     "GROUP BY t.userid ORDER BY n_movies DESC LIMIT 10"),

    ("tp:ml-hav-1", "movielens", "having-min-count",
     "Which movies have an average rating above 4.5 and at least 20 ratings?",
     "SELECT m.title, AVG(r.rating) AS avg_rating, COUNT(*) AS n_ratings FROM ratings r "
     "JOIN movies m ON m.movieid = r.movieid GROUP BY m.movieid, m.title "
     "HAVING COUNT(*) >= 20 AND AVG(r.rating) > 4.5 ORDER BY avg_rating DESC"),
    ("tp:ml-hav-2", "movielens", "having-min-count",
     "Which users have given more than 500 ratings?",
     "SELECT userid, COUNT(*) AS n_ratings FROM ratings GROUP BY userid "
     "HAVING COUNT(*) > 500 ORDER BY n_ratings DESC"),
    ("tp:ml-hav-3", "movielens", "having-min-count",
     "Which tags have been applied to at least 10 different movies?",
     "SELECT tag, COUNT(DISTINCT movieid) AS n_movies FROM tags GROUP BY tag "
     "HAVING COUNT(DISTINCT movieid) >= 10 ORDER BY n_movies DESC"),

    ("tp:ml-unn-1", "movielens", "unnest-multivalue",
     "List every distinct genre in the database.",
     "SELECT DISTINCT unnest(string_to_array(genres, '|')) AS genre FROM movies ORDER BY genre"),
    ("tp:ml-unn-2", "movielens", "unnest-multivalue",
     "How many movies are listed as Comedy?",
     "SELECT COUNT(*) AS n_comedy FROM movies "
     "WHERE 'Comedy' = ANY(string_to_array(genres, '|'))"),
    ("tp:ml-unn-3", "movielens", "unnest-multivalue",
     "How many distinct users have rated a movie in each genre? Top 5 genres.",
     "SELECT g AS genre, COUNT(DISTINCT r.userid) AS n_users FROM movies m "
     "JOIN ratings r ON r.movieid = m.movieid "
     "CROSS JOIN unnest(string_to_array(m.genres, '|')) AS g "
     "GROUP BY g ORDER BY n_users DESC LIMIT 5"),

    ("tp:ml-arg-1", "movielens", "argmax-top1",
     "Which user has written the most tags?",
     "SELECT userid, COUNT(*) AS n_tags FROM tags GROUP BY userid "
     "ORDER BY n_tags DESC LIMIT 1"),
    ("tp:ml-arg-2", "movielens", "argmax-top1",
     "Which movie has the most tags?",
     "SELECT m.title, COUNT(*) AS n_tags FROM tags t "
     "JOIN movies m ON m.movieid = t.movieid GROUP BY m.movieid, m.title "
     "ORDER BY n_tags DESC LIMIT 1"),
    ("tp:ml-arg-3", "movielens", "argmax-top1",
     "Which movie has the highest average rating among movies with at least 100 ratings?",
     "SELECT m.title, AVG(r.rating) AS avg_rating FROM ratings r "
     "JOIN movies m ON m.movieid = r.movieid GROUP BY m.movieid, m.title "
     "HAVING COUNT(*) >= 100 ORDER BY avg_rating DESC LIMIT 1"),

    ("tp:ml-yr-1", "movielens", "year-from-title",
     "How many movies were released in 1995?",
     r"SELECT COUNT(*) AS n_movies FROM movies "
     r"WHERE substring(title FROM '\((\d{4})\)\s*$')::int = 1995"),
    ("tp:ml-yr-2", "movielens", "year-from-title",
     "List the 10 oldest movies by release year.",
     r"SELECT title, substring(title FROM '\((\d{4})\)\s*$')::int AS release_year "
     r"FROM movies WHERE substring(title FROM '\((\d{4})\)\s*$') IS NOT NULL "
     r"ORDER BY release_year ASC LIMIT 10"),
    ("tp:ml-yr-3", "movielens", "year-from-title",
     "How many movies were released in each decade?",
     r"SELECT (substring(title FROM '\((\d{4})\)\s*$')::int / 10) * 10 AS decade, "
     r"COUNT(*) AS n_movies FROM movies "
     r"WHERE substring(title FROM '\((\d{4})\)\s*$') IS NOT NULL "
     r"GROUP BY decade ORDER BY decade"),

    ("tp:ml-win-1", "movielens", "window-top1-per-group",
     "For each user, which movie did they rate first? Show 10 users.",
     "SELECT userid, movieid, ts FROM (SELECT userid, movieid, timestamp AS ts, "
     "ROW_NUMBER() OVER (PARTITION BY userid ORDER BY timestamp) AS rn FROM ratings) x "
     "WHERE rn = 1 ORDER BY userid LIMIT 10"),
    ("tp:ml-win-2", "movielens", "window-top1-per-group",
     "For each user, what are their two highest-rated movies? Show 10 rows.",
     "SELECT userid, movieid, rating FROM (SELECT userid, movieid, rating, "
     "ROW_NUMBER() OVER (PARTITION BY userid ORDER BY rating DESC, movieid) AS rn "
     "FROM ratings) x WHERE rn <= 2 ORDER BY userid, rating DESC LIMIT 10"),
    ("tp:ml-win-3", "movielens", "window-top1-per-group",
     "For each rating value, which movie received that rating most often?",
     "SELECT rating, title, n FROM (SELECT r.rating, m.title, COUNT(*) AS n, "
     "ROW_NUMBER() OVER (PARTITION BY r.rating ORDER BY COUNT(*) DESC, m.title) AS rn "
     "FROM ratings r JOIN movies m ON m.movieid = r.movieid "
     "GROUP BY r.rating, m.movieid, m.title) x WHERE rn = 1 ORDER BY rating"),

    ("tp:ml-dist-1", "movielens", "distribution-counts",
     "How many movies have each number of ratings? Show the first 20 buckets.",
     "SELECT n_ratings, COUNT(*) AS n_movies FROM "
     "(SELECT movieid, COUNT(*) AS n_ratings FROM ratings GROUP BY movieid) x "
     "GROUP BY n_ratings ORDER BY n_ratings LIMIT 20"),
    ("tp:ml-dist-2", "movielens", "distribution-counts",
     "How many users wrote each number of tags? Show the first 20 buckets.",
     "SELECT n_tags, COUNT(*) AS n_users FROM "
     "(SELECT userid, COUNT(*) AS n_tags FROM tags GROUP BY userid) x "
     "GROUP BY n_tags ORDER BY n_tags LIMIT 20"),
    ("tp:ml-dist-3", "movielens", "distribution-counts",
     "How many movies have one genre, two genres, three genres and so on?",
     "SELECT array_length(string_to_array(genres, '|'), 1) AS n_genres, "
     "COUNT(*) AS n_movies FROM movies GROUP BY n_genres ORDER BY n_genres"),

    ("tp:ml-anti-1", "movielens", "anti-join",
     "Which movies have never been rated by anyone?",
     "SELECT m.movieid, m.title FROM movies m "
     "WHERE NOT EXISTS (SELECT 1 FROM ratings r WHERE r.movieid = m.movieid) "
     "ORDER BY m.title"),
    ("tp:ml-anti-2", "movielens", "anti-join",
     "Which users have rated movies but never written a tag?",
     "SELECT DISTINCT r.userid FROM ratings r "
     "WHERE NOT EXISTS (SELECT 1 FROM tags t WHERE t.userid = r.userid) "
     "ORDER BY r.userid LIMIT 20"),
    ("tp:ml-anti-3", "movielens", "anti-join",
     "Which movies have never been given a rating of 5?",
     "SELECT m.movieid, m.title FROM movies m WHERE NOT EXISTS "
     "(SELECT 1 FROM ratings r WHERE r.movieid = m.movieid AND r.rating = 5) "
     "ORDER BY m.title LIMIT 20"),

    ("tp:ml-epo-1", "movielens", "epoch-bucketing",
     "How many tags were created in each year?",
     "SELECT EXTRACT(YEAR FROM to_timestamp(timestamp)) AS year, COUNT(*) AS n_tags "
     "FROM tags GROUP BY year ORDER BY year"),
    ("tp:ml-epo-2", "movielens", "epoch-bucketing",
     "In which month of the year are ratings most often given?",
     "SELECT EXTRACT(MONTH FROM to_timestamp(timestamp)) AS month, COUNT(*) AS n_ratings "
     "FROM ratings GROUP BY month ORDER BY n_ratings DESC"),
    ("tp:ml-epo-3", "movielens", "epoch-bucketing",
     "What are the dates of the earliest and latest rating?",
     "SELECT to_timestamp(MIN(timestamp)) AS first_rating, "
     "to_timestamp(MAX(timestamp)) AS last_rating FROM ratings"),

    # ================= Olist =================
    ("tp:ol-agg-1", "olist", "simple-aggregate",
     "How many sellers are in the database?",
     "SELECT COUNT(*) AS n_sellers FROM sellers"),
    ("tp:ol-agg-2", "olist", "simple-aggregate",
     "What is the total freight value paid across all order items?",
     "SELECT SUM(freight_value) AS total_freight FROM order_items"),
    ("tp:ol-agg-3", "olist", "simple-aggregate",
     "How many customer reviews are there?",
     "SELECT COUNT(*) AS n_reviews FROM order_reviews"),

    ("tp:ol-rev-1", "olist", "revenue-topn",
     "Which 10 products generated the most revenue?",
     "SELECT product_id, SUM(price) AS revenue FROM order_items "
     "GROUP BY product_id ORDER BY revenue DESC LIMIT 10"),
    ("tp:ol-rev-2", "olist", "revenue-topn",
     "Which 10 seller states generated the most revenue?",
     "SELECT s.seller_state, SUM(oi.price) AS revenue FROM order_items oi "
     "JOIN sellers s ON s.seller_id = oi.seller_id "
     "GROUP BY s.seller_state ORDER BY revenue DESC LIMIT 10"),
    ("tp:ol-rev-3", "olist", "revenue-topn",
     "Which 5 customer states generated the most revenue?",
     "SELECT c.customer_state, SUM(oi.price) AS revenue FROM order_items oi "
     "JOIN orders o ON o.order_id = oi.order_id "
     "JOIN customers c ON c.customer_id = o.customer_id "
     "GROUP BY c.customer_state ORDER BY revenue DESC LIMIT 5"),

    ("tp:ol-grp-1", "olist", "per-group-aggregate",
     "What is the average review score for each order status?",
     "SELECT o.order_status, AVG(rv.review_score) AS avg_score, COUNT(*) AS n_reviews "
     "FROM order_reviews rv JOIN orders o ON o.order_id = rv.order_id "
     "GROUP BY o.order_status ORDER BY avg_score DESC"),
    ("tp:ol-grp-2", "olist", "per-group-aggregate",
     "What is the average item price per product category in English? Top 10 by average.",
     "SELECT t.product_category_name_english AS category, AVG(oi.price) AS avg_price "
     "FROM order_items oi JOIN products p ON p.product_id = oi.product_id "
     "JOIN product_category_name_translation t "
     "ON t.product_category_name = p.product_category_name "
     "GROUP BY category ORDER BY avg_price DESC LIMIT 10"),
    ("tp:ol-grp-3", "olist", "per-group-aggregate",
     "How many distinct orders did each seller receive? Show the top 10 sellers.",
     "SELECT seller_id, COUNT(DISTINCT order_id) AS n_orders FROM order_items "
     "GROUP BY seller_id ORDER BY n_orders DESC LIMIT 10"),

    ("tp:ol-dist-1", "olist", "distribution-counts",
     "How many orders used each number of payment installments?",
     "SELECT payment_installments, COUNT(*) AS n FROM order_payments "
     "GROUP BY payment_installments ORDER BY payment_installments"),
    ("tp:ol-dist-2", "olist", "distribution-counts",
     "What is the distribution of review scores from 1 to 5?",
     "SELECT review_score, COUNT(*) AS n FROM order_reviews "
     "GROUP BY review_score ORDER BY review_score"),
    ("tp:ol-dist-3", "olist", "distribution-counts",
     "How many orders contain one item, two items, three items and so on?",
     "SELECT item_count, COUNT(*) AS n_orders FROM "
     "(SELECT order_id, COUNT(*) AS item_count FROM order_items GROUP BY order_id) x "
     "GROUP BY item_count ORDER BY item_count"),

    ("tp:ol-dd-1", "olist", "date-diff-days",
     "What is the average number of days between purchase and carrier handover?",
     "SELECT AVG(EXTRACT(EPOCH FROM (order_delivered_carrier_date - order_purchase_timestamp)) "
     "/ 86400.0) AS avg_days FROM orders "
     "WHERE order_delivered_carrier_date IS NOT NULL"),
    ("tp:ol-dd-2", "olist", "date-diff-days",
     "Which 10 delivered orders took the longest number of days to reach the customer?",
     "SELECT order_id, EXTRACT(EPOCH FROM "
     "(order_delivered_customer_date - order_purchase_timestamp)) / 86400.0 AS days "
     "FROM orders WHERE order_delivered_customer_date IS NOT NULL "
     "ORDER BY days DESC LIMIT 10"),
    ("tp:ol-dd-3", "olist", "date-diff-days",
     "What is the average number of days between order approval and delivery to the customer?",
     "SELECT AVG(EXTRACT(EPOCH FROM "
     "(order_delivered_customer_date - order_approved_at)) / 86400.0) AS avg_days "
     "FROM orders WHERE order_delivered_customer_date IS NOT NULL "
     "AND order_approved_at IS NOT NULL"),

    ("tp:ol-pct-1", "olist", "conditional-percentage",
     "What percentage of orders were cancelled?",
     "SELECT 100.0 * SUM(CASE WHEN order_status = 'canceled' THEN 1 ELSE 0 END) "
     "/ COUNT(*) AS pct_cancelled FROM orders"),
    ("tp:ol-pct-2", "olist", "conditional-percentage",
     "What percentage of reviews gave the top score of 5?",
     "SELECT 100.0 * SUM(CASE WHEN review_score = 5 THEN 1 ELSE 0 END) "
     "/ COUNT(*) AS pct_five_star FROM order_reviews"),
    ("tp:ol-pct-3", "olist", "conditional-percentage",
     "What percentage of delivered orders arrived before the estimated delivery date?",
     "SELECT 100.0 * SUM(CASE WHEN order_delivered_customer_date "
     "< order_estimated_delivery_date THEN 1 ELSE 0 END) / COUNT(*) AS pct_early "
     "FROM orders WHERE order_delivered_customer_date IS NOT NULL"),

    ("tp:ol-mon-1", "olist", "monthly-bucketing",
     "How much revenue was earned in each month?",
     "SELECT date_trunc('month', o.order_purchase_timestamp) AS month, "
     "SUM(oi.price) AS revenue FROM order_items oi "
     "JOIN orders o ON o.order_id = oi.order_id GROUP BY month ORDER BY month"),
    ("tp:ol-mon-2", "olist", "monthly-bucketing",
     "How many reviews were created in each month?",
     "SELECT date_trunc('month', review_creation_date) AS month, COUNT(*) AS n_reviews "
     "FROM order_reviews GROUP BY month ORDER BY month"),
    ("tp:ol-mon-3", "olist", "monthly-bucketing",
     "How many orders were placed in each year?",
     "SELECT date_trunc('year', order_purchase_timestamp) AS year, COUNT(*) AS n_orders "
     "FROM orders GROUP BY year ORDER BY year"),

    ("tp:ol-hav-1", "olist", "having-min-count",
     "Which product categories in English have more than 1000 items sold?",
     "SELECT t.product_category_name_english AS category, COUNT(*) AS n_items "
     "FROM order_items oi JOIN products p ON p.product_id = oi.product_id "
     "JOIN product_category_name_translation t "
     "ON t.product_category_name = p.product_category_name "
     "GROUP BY category HAVING COUNT(*) > 1000 ORDER BY n_items DESC"),
    ("tp:ol-hav-2", "olist", "having-min-count",
     "Which sellers have sold at least 100 items?",
     "SELECT seller_id, COUNT(*) AS n_items FROM order_items GROUP BY seller_id "
     "HAVING COUNT(*) >= 100 ORDER BY n_items DESC"),
    ("tp:ol-hav-3", "olist", "having-min-count",
     "Which customer states have more than 5000 orders?",
     "SELECT c.customer_state, COUNT(*) AS n_orders FROM orders o "
     "JOIN customers c ON c.customer_id = o.customer_id "
     "GROUP BY c.customer_state HAVING COUNT(*) > 5000 ORDER BY n_orders DESC"),

    ("tp:ol-nest-1", "olist", "nested-aggregate",
     "What is the average total revenue per order?",
     "SELECT AVG(order_total) AS avg_order_value FROM "
     "(SELECT order_id, SUM(price) AS order_total FROM order_items GROUP BY order_id) x"),
    ("tp:ol-nest-2", "olist", "nested-aggregate",
     "What is the largest number of items in a single order?",
     "SELECT MAX(item_count) AS max_items FROM "
     "(SELECT order_id, COUNT(*) AS item_count FROM order_items GROUP BY order_id) x"),
    ("tp:ol-nest-3", "olist", "nested-aggregate",
     "What is the average number of payment records per order?",
     "SELECT AVG(n_payments) AS avg_payments FROM "
     "(SELECT order_id, COUNT(*) AS n_payments FROM order_payments GROUP BY order_id) x"),

    ("tp:ol-rep-1", "olist", "repeat-entity",
     "How many sellers have sold more than one distinct product?",
     "SELECT COUNT(*) AS n_sellers FROM (SELECT seller_id FROM order_items "
     "GROUP BY seller_id HAVING COUNT(DISTINCT product_id) > 1) x"),
    ("tp:ol-rep-2", "olist", "repeat-entity",
     "How many orders have more than one payment record?",
     "SELECT COUNT(*) AS n_orders FROM (SELECT order_id FROM order_payments "
     "GROUP BY order_id HAVING COUNT(*) > 1) x"),
    ("tp:ol-rep-3", "olist", "repeat-entity",
     "How many products were sold in more than one order?",
     "SELECT COUNT(*) AS n_products FROM (SELECT product_id FROM order_items "
     "GROUP BY product_id HAVING COUNT(DISTINCT order_id) > 1) x"),

    # ================= Soccer (SQLite) =================
    ("tp:sc-agg-1", "soccer", "simple-aggregate",
     "How many leagues are in the database?",
     'SELECT COUNT(*) AS n_leagues FROM "League"'),
    ("tp:sc-agg-2", "soccer", "simple-aggregate",
     "How many teams are in the database?",
     'SELECT COUNT(*) AS n_teams FROM "Team"'),
    ("tp:sc-agg-3", "soccer", "simple-aggregate",
     "How many goals were scored in total across all matches?",
     'SELECT SUM(home_team_goal + away_team_goal) AS total_goals FROM "Match"'),

    ("tp:sc-grp-1", "soccer", "per-group-aggregate",
     "How many matches were played in each season?",
     'SELECT season, COUNT(*) AS n_matches FROM "Match" GROUP BY season ORDER BY season'),
    ("tp:sc-grp-2", "soccer", "per-group-aggregate",
     "How many matches were hosted by each country?",
     'SELECT c.name AS country, COUNT(*) AS n_matches FROM "Match" m '
     'JOIN "Country" c ON c.id = m.country_id GROUP BY c.name ORDER BY n_matches DESC'),
    ("tp:sc-grp-3", "soccer", "per-group-aggregate",
     "What is the average number of goals per match in each season?",
     'SELECT season, AVG(home_team_goal + away_team_goal) AS avg_goals FROM "Match" '
     'GROUP BY season ORDER BY season'),

    ("tp:sc-arg-1", "soccer", "argmax-top1",
     "Which match had the most goals in total?",
     'SELECT id, season, home_team_goal, away_team_goal, '
     '(home_team_goal + away_team_goal) AS total_goals FROM "Match" '
     'ORDER BY total_goals DESC LIMIT 1'),
    ("tp:sc-arg-2", "soccer", "argmax-top1",
     "Which league scored the most goals in total?",
     'SELECT l.name AS league, SUM(m.home_team_goal + m.away_team_goal) AS total_goals '
     'FROM "Match" m JOIN "League" l ON l.id = m.league_id '
     'GROUP BY l.name ORDER BY total_goals DESC LIMIT 1'),
    ("tp:sc-arg-3", "soccer", "argmax-top1",
     "Which player is the youngest in the database?",
     'SELECT player_name, birthday FROM "Player" ORDER BY birthday DESC LIMIT 1'),

    ("tp:sc-ha-1", "soccer", "home-away-union",
     "How many matches has each team played in total, counting home and away? Top 10.",
     'SELECT t.team_long_name, COUNT(*) AS n_matches FROM '
     '(SELECT home_team_api_id AS team_api_id FROM "Match" '
     ' UNION ALL SELECT away_team_api_id FROM "Match") x '
     'JOIN "Team" t ON t.team_api_id = x.team_api_id '
     'GROUP BY t.team_long_name ORDER BY n_matches DESC LIMIT 10'),
    ("tp:sc-ha-2", "soccer", "home-away-union",
     "Which 10 teams conceded the most goals in total, counting home and away matches?",
     'SELECT t.team_long_name, SUM(x.conceded) AS goals_conceded FROM '
     '(SELECT home_team_api_id AS team_api_id, away_team_goal AS conceded FROM "Match" '
     ' UNION ALL SELECT away_team_api_id, home_team_goal FROM "Match") x '
     'JOIN "Team" t ON t.team_api_id = x.team_api_id '
     'GROUP BY t.team_long_name ORDER BY goals_conceded DESC LIMIT 10'),
    ("tp:sc-ha-3", "soccer", "home-away-union",
     "What is each team's average goals scored per match, for teams with at least 100 matches? Top 10.",
     'SELECT t.team_long_name, AVG(x.scored) AS avg_scored, COUNT(*) AS n_matches FROM '
     '(SELECT home_team_api_id AS team_api_id, home_team_goal AS scored FROM "Match" '
     ' UNION ALL SELECT away_team_api_id, away_team_goal FROM "Match") x '
     'JOIN "Team" t ON t.team_api_id = x.team_api_id GROUP BY t.team_long_name '
     'HAVING COUNT(*) >= 100 ORDER BY avg_scored DESC LIMIT 10'),

    ("tp:sc-wld-1", "soccer", "case-wld-counting",
     "How many home wins did each league have? Top 5 leagues.",
     'SELECT l.name AS league, '
     'SUM(CASE WHEN m.home_team_goal > m.away_team_goal THEN 1 ELSE 0 END) AS home_wins '
     'FROM "Match" m JOIN "League" l ON l.id = m.league_id '
     'GROUP BY l.name ORDER BY home_wins DESC LIMIT 5'),
    ("tp:sc-wld-2", "soccer", "case-wld-counting",
     "How many matches ended in a draw in each season?",
     'SELECT season, '
     'SUM(CASE WHEN home_team_goal = away_team_goal THEN 1 ELSE 0 END) AS draws '
     'FROM "Match" GROUP BY season ORDER BY season'),
    ("tp:sc-wld-3", "soccer", "case-wld-counting",
     "How many wins, losses and draws does Arsenal have overall?",
     'SELECT '
     'SUM(CASE WHEN (m.home_team_api_id = t.team_api_id AND m.home_team_goal > m.away_team_goal) '
     '      OR (m.away_team_api_id = t.team_api_id AND m.away_team_goal > m.home_team_goal) '
     '     THEN 1 ELSE 0 END) AS wins, '
     'SUM(CASE WHEN (m.home_team_api_id = t.team_api_id AND m.home_team_goal < m.away_team_goal) '
     '      OR (m.away_team_api_id = t.team_api_id AND m.away_team_goal < m.home_team_goal) '
     '     THEN 1 ELSE 0 END) AS losses, '
     'SUM(CASE WHEN m.home_team_goal = m.away_team_goal THEN 1 ELSE 0 END) AS draws '
     'FROM "Match" m JOIN "Team" t ON t.team_api_id IN (m.home_team_api_id, m.away_team_api_id) '
     "WHERE t.team_long_name = 'Arsenal'"),

    ("tp:sc-anti-1", "soccer", "anti-join",
     "Which teams never played a home match?",
     'SELECT t.team_long_name FROM "Team" t WHERE NOT EXISTS '
     '(SELECT 1 FROM "Match" m WHERE m.home_team_api_id = t.team_api_id) '
     'ORDER BY t.team_long_name'),
    # NOTE: the equivalent query over Player_Attributes takes >20s -- SQLite has no
    # index on player_api_id, so it rescans 184k rows per player. Team_Attributes
    # teaches the same technique in milliseconds.
    ("tp:sc-anti-2", "soccer", "anti-join",
     "Which teams have no entries in the team attributes table?",
     'SELECT t.team_long_name FROM "Team" t WHERE NOT EXISTS '
     '(SELECT 1 FROM "Team_Attributes" ta WHERE ta.team_api_id = t.team_api_id) '
     'ORDER BY t.team_long_name'),
    ("tp:sc-anti-3", "soccer", "anti-join",
     "Which leagues had no matches in the 2015/2016 season?",
     'SELECT l.name AS league FROM "League" l WHERE NOT EXISTS '
     '(SELECT 1 FROM "Match" m WHERE m.league_id = l.id AND m.season = \'2015/2016\') '
     'ORDER BY l.name'),
]


def main():
    mem = Memory()
    mem.entries = []                       # rebuild from scratch: pool only, no gold
    engines = {db: get_engine(url) for db, url in DATABASES.items()}
    stored, failed = 0, []

    for qid, db, technique, question, sql in POOL:
        try:
            cols, rows = run_sql(engines[db], sql)
        except Exception as exc:
            orig = getattr(exc, "orig", exc)
            failed.append((qid, str(orig).splitlines()[0]))
            print(f"  FAIL  {qid:<16} {str(orig).splitlines()[0][:70]}")
            continue
        mem.add(db, question, sql, id=qid, technique=technique, save=False)
        stored += 1
        preview = str(tuple(rows[0])) if rows else "()"
        print(f"  ok    {qid:<16} {len(rows):>5} rows  first={preview[:52]}")

    mem.save()

    # ---- coverage table -------------------------------------------------
    print("\n=== coverage: technique x database ===")
    ok = True
    for db, techniques in TECHNIQUE_COVERAGE.items():
        print(f"\n  {db}")
        for tech, gold_qs in techniques.items():
            n = sum(1 for e in mem.entries if e["db"] == db and e["technique"] == tech)
            flag = "ok " if n >= 3 else "LOW"
            if n < 3:
                ok = False
            print(f"    [{flag}] {tech:<24} n={n}   covers gold {gold_qs}")

    print(f"\nstored {stored} / {len(POOL)}   failed {len(failed)}")
    assert not failed, f"{len(failed)} training pairs failed to execute: {failed}"
    assert ok, "some technique has fewer than 3 training examples"
    print("ALL TECHNIQUES HAVE >= 3 VERIFIED EXAMPLES")


if __name__ == "__main__":
    main()
