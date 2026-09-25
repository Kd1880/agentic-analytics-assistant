"""
gold_eval.py — the 45 gold questions, their VERIFIED reference SQL, and metadata.

The grader compares RESULTS, never SQL (many different queries are equally
correct). The reference SQL exists only to produce the frozen gold result.

Fields per question:
  id, db, difficulty (E/M/H)
  question        : the exact text sent to the agent
  sql             : verified reference SQL (written fresh -- some suggested SQL
                    in gold_questions.md is known wrong)
  shape           : 'scalar' | 'set' | 'list'
  order_sensitive : True for top-N / trends; False for "count per X"
  note            : set when the question had to be changed or is ambiguous

Run this to (re)freeze gold_answers.json.
"""

from db import DATABASES, get_engine, run_sql

GOLD = [
    # ======================= MovieLens =======================
    dict(id="ml#1", db="movielens", difficulty="E", shape="scalar", order_sensitive=False,
         question="How many movies are in the database?",
         sql="SELECT COUNT(*) AS n_movies FROM movies"),
    dict(id="ml#2", db="movielens", difficulty="E", shape="scalar", order_sensitive=False,
         question="How many ratings are there in total?",
         sql="SELECT COUNT(*) AS n_ratings FROM ratings"),
    dict(id="ml#3", db="movielens", difficulty="E", shape="scalar", order_sensitive=False,
         question="What is the overall average rating?",
         sql="SELECT AVG(rating) AS avg_rating FROM ratings"),
    dict(id="ml#4", db="movielens", difficulty="M", shape="list", order_sensitive=True,
         question="Which 10 movies have the most ratings?",
         sql="SELECT m.title, COUNT(*) AS n_ratings FROM ratings r "
             "JOIN movies m ON m.movieid = r.movieid "
             "GROUP BY m.movieid, m.title ORDER BY n_ratings DESC, m.title LIMIT 10"),
    dict(id="ml#5", db="movielens", difficulty="M", shape="list", order_sensitive=True,
         question="What are the top 10 highest-average-rated movies with at least 50 ratings?",
         sql="SELECT m.title, AVG(r.rating) AS avg_rating FROM ratings r "
             "JOIN movies m ON m.movieid = r.movieid GROUP BY m.movieid, m.title "
             "HAVING COUNT(*) >= 50 ORDER BY avg_rating DESC, m.title LIMIT 10"),
    dict(id="ml#6", db="movielens", difficulty="M", shape="set", order_sensitive=False,
         question="How many movies are there per genre?",
         sql="SELECT g AS genre, COUNT(*) AS n_movies FROM movies "
             "CROSS JOIN unnest(string_to_array(genres, '|')) AS g GROUP BY g"),
    dict(id="ml#7", db="movielens", difficulty="M", shape="list", order_sensitive=True,
         question="Which user has rated the most movies?",
         sql="SELECT userid, COUNT(*) AS n_ratings FROM ratings "
             "GROUP BY userid ORDER BY n_ratings DESC, userid LIMIT 1"),
    dict(id="ml#8", db="movielens", difficulty="M", shape="set", order_sensitive=False,
         question="What is the average rating per genre?",
         sql="SELECT g AS genre, AVG(r.rating) AS avg_rating FROM movies m "
             "JOIN ratings r ON r.movieid = m.movieid "
             "CROSS JOIN unnest(string_to_array(m.genres, '|')) AS g GROUP BY g"),
    dict(id="ml#9", db="movielens", difficulty="H", shape="list", order_sensitive=True,
         question="What is the average rating per release year?",
         sql=r"WITH y AS (SELECT movieid, substring(title FROM '\((\d{4})\)\s*$')::int "
             r"AS release_year FROM movies) "
             r"SELECT y.release_year, AVG(r.rating) AS avg_rating FROM ratings r "
             r"JOIN y ON y.movieid = r.movieid WHERE y.release_year IS NOT NULL "
             r"GROUP BY y.release_year ORDER BY y.release_year"),
    dict(id="ml#10", db="movielens", difficulty="M", shape="list", order_sensitive=True,
         question="What are the 10 most frequently used tags?",
         sql="SELECT tag, COUNT(*) AS n FROM tags GROUP BY tag ORDER BY n DESC, tag LIMIT 10"),
    dict(id="ml#11", db="movielens", difficulty="H", shape="set", order_sensitive=False,
         question="Which movies have an average rating above 4 but fewer than 10 ratings?",
         sql="SELECT m.title, AVG(r.rating) AS avg_rating, COUNT(*) AS n_ratings FROM ratings r "
             "JOIN movies m ON m.movieid = r.movieid GROUP BY m.movieid, m.title "
             "HAVING AVG(r.rating) > 4 AND COUNT(*) < 10"),
    dict(id="ml#12", db="movielens", difficulty="H", shape="set", order_sensitive=False,
         question="For each genre, which movie has the highest average rating "
                  "(counting only movies with at least 20 ratings)?",
         sql="WITH g AS (SELECT unnest(string_to_array(m.genres, '|')) AS genre, "
             "m.movieid, m.title FROM movies m), "
             "s AS (SELECT g.genre, g.movieid, g.title, AVG(r.rating) AS avg_rating "
             "FROM g JOIN ratings r ON r.movieid = g.movieid "
             "GROUP BY g.genre, g.movieid, g.title HAVING COUNT(*) >= 20) "
             "SELECT genre, title, avg_rating FROM (SELECT s.*, ROW_NUMBER() OVER "
             "(PARTITION BY genre ORDER BY avg_rating DESC, title) AS rn FROM s) x WHERE rn = 1"),
    dict(id="ml#13", db="movielens", difficulty="M", shape="set", order_sensitive=False,
         question="What is the distribution of rating values?",
         sql="SELECT rating, COUNT(*) AS n FROM ratings GROUP BY rating"),
    dict(id="ml#14", db="movielens", difficulty="H", shape="set", order_sensitive=False,
         question="Which movies have been tagged but have no rating?",
         sql="SELECT DISTINCT m.movieid, m.title FROM tags t "
             "JOIN movies m ON m.movieid = t.movieid "
             "WHERE NOT EXISTS (SELECT 1 FROM ratings r WHERE r.movieid = m.movieid)"),
    dict(id="ml#15", db="movielens", difficulty="H", shape="list", order_sensitive=True,
         question="How many ratings were made in each year?",
         sql="SELECT EXTRACT(YEAR FROM to_timestamp(timestamp)) AS year, COUNT(*) AS n_ratings "
             "FROM ratings GROUP BY year ORDER BY year"),

    # ======================= Olist =======================
    dict(id="ol#1", db="olist", difficulty="E", shape="scalar", order_sensitive=False,
         question="How many orders are in the database?",
         sql="SELECT COUNT(*) AS n_orders FROM orders"),
    dict(id="ol#2", db="olist", difficulty="E", shape="scalar", order_sensitive=False,
         question="What is the total revenue?",
         sql="SELECT SUM(price) AS total_revenue FROM order_items"),
    dict(id="ol#3", db="olist", difficulty="M", shape="list", order_sensitive=True,
         question="What are the top 10 product categories by revenue, using the English "
                  "category names?",
         sql="SELECT t.product_category_name_english AS category, SUM(oi.price) AS revenue "
             "FROM order_items oi JOIN products p ON p.product_id = oi.product_id "
             "JOIN product_category_name_translation t "
             "ON t.product_category_name = p.product_category_name "
             "GROUP BY category ORDER BY revenue DESC LIMIT 10"),
    dict(id="ol#4", db="olist", difficulty="M", shape="set", order_sensitive=False,
         question="How many orders are there per order status?",
         sql="SELECT order_status, COUNT(*) AS n FROM orders GROUP BY order_status"),
    dict(id="ol#5", db="olist", difficulty="M", shape="set", order_sensitive=False,
         question="What is the average review score per product category, using the English "
                  "category names?",
         note="gold_questions.md asks for overall AND per-category in one question; "
              "graded on per-category only. Reviews are counted once per order item, "
              "the conventional Olist join.",
         sql="SELECT t.product_category_name_english AS category, "
             "AVG(rv.review_score) AS avg_score FROM order_reviews rv "
             "JOIN orders o ON o.order_id = rv.order_id "
             "JOIN order_items oi ON oi.order_id = o.order_id "
             "JOIN products p ON p.product_id = oi.product_id "
             "JOIN product_category_name_translation t "
             "ON t.product_category_name = p.product_category_name GROUP BY category"),
    dict(id="ol#6", db="olist", difficulty="H", shape="scalar", order_sensitive=False,
         question="What is the average delivery time in days (delivered date minus purchase "
                  "date) for delivered orders?",
         sql="SELECT AVG(EXTRACT(EPOCH FROM (order_delivered_customer_date "
             "- order_purchase_timestamp)) / 86400.0) AS avg_days FROM orders "
             "WHERE order_status = 'delivered' AND order_delivered_customer_date IS NOT NULL"),
    dict(id="ol#7", db="olist", difficulty="H", shape="scalar", order_sensitive=False,
         question="What percentage of orders were delivered after the estimated delivery date?",
         sql="SELECT 100.0 * SUM(CASE WHEN order_delivered_customer_date "
             "> order_estimated_delivery_date THEN 1 ELSE 0 END) / COUNT(*) AS pct_late "
             "FROM orders WHERE order_delivered_customer_date IS NOT NULL"),
    dict(id="ol#8", db="olist", difficulty="M", shape="set", order_sensitive=False,
         question="What is the distribution of payment types?",
         sql="SELECT payment_type, COUNT(*) AS n FROM order_payments GROUP BY payment_type"),
    dict(id="ol#9", db="olist", difficulty="M", shape="list", order_sensitive=True,
         question="Who are the top 10 sellers by total revenue?",
         sql="SELECT seller_id, SUM(price) AS revenue FROM order_items "
             "GROUP BY seller_id ORDER BY revenue DESC LIMIT 10"),
    dict(id="ol#10", db="olist", difficulty="M", shape="set", order_sensitive=False,
         question="How many orders are there per customer state?",
         sql="SELECT c.customer_state, COUNT(*) AS n_orders FROM orders o "
             "JOIN customers c ON c.customer_id = o.customer_id GROUP BY c.customer_state"),
    dict(id="ol#11", db="olist", difficulty="H", shape="list", order_sensitive=True,
         question="How many orders were placed each month over time?",
         sql="SELECT date_trunc('month', order_purchase_timestamp) AS month, "
             "COUNT(*) AS n_orders FROM orders GROUP BY month ORDER BY month"),
    dict(id="ol#12", db="olist", difficulty="H", shape="list", order_sensitive=True,
         question="Which product category has the worst average review score, counting only "
                  "categories with at least 100 orders? Use the English category names.",
         sql="SELECT t.product_category_name_english AS category, "
             "AVG(rv.review_score) AS avg_score FROM order_reviews rv "
             "JOIN orders o ON o.order_id = rv.order_id "
             "JOIN order_items oi ON oi.order_id = o.order_id "
             "JOIN products p ON p.product_id = oi.product_id "
             "JOIN product_category_name_translation t "
             "ON t.product_category_name = p.product_category_name GROUP BY category "
             "HAVING COUNT(DISTINCT o.order_id) >= 100 ORDER BY avg_score ASC, category LIMIT 1"),
    dict(id="ol#13", db="olist", difficulty="H", shape="set", order_sensitive=False,
         question="What is the average freight value by customer state?",
         sql="SELECT c.customer_state, AVG(oi.freight_value) AS avg_freight "
             "FROM order_items oi JOIN orders o ON o.order_id = oi.order_id "
             "JOIN customers c ON c.customer_id = o.customer_id GROUP BY c.customer_state"),
    dict(id="ol#14", db="olist", difficulty="M", shape="scalar", order_sensitive=False,
         question="What is the average number of items per order?",
         sql="SELECT AVG(item_count) AS avg_items FROM (SELECT order_id, COUNT(*) AS item_count "
             "FROM order_items GROUP BY order_id) x"),
    dict(id="ol#15", db="olist", difficulty="H", shape="scalar", order_sensitive=False,
         question="How many unique customers placed more than one order?",
         sql="SELECT COUNT(*) AS n_repeat_customers FROM (SELECT c.customer_unique_id "
             "FROM orders o JOIN customers c ON c.customer_id = o.customer_id "
             "GROUP BY c.customer_unique_id HAVING COUNT(DISTINCT o.order_id) > 1) x"),

    # ======================= Soccer (SQLite) =======================
    dict(id="sc#1", db="soccer", difficulty="E", shape="scalar", order_sensitive=False,
         question="How many matches are in the database?",
         sql='SELECT COUNT(*) AS n_matches FROM "Match"'),
    dict(id="sc#2", db="soccer", difficulty="E", shape="scalar", order_sensitive=False,
         question="How many players are there?",
         sql='SELECT COUNT(*) AS n_players FROM "Player"'),
    dict(id="sc#3", db="soccer", difficulty="M", shape="set", order_sensitive=False,
         question="How many matches were played per league?",
         sql='SELECT l.name AS league, COUNT(*) AS n_matches FROM "Match" m '
             'JOIN "League" l ON l.id = m.league_id GROUP BY l.name'),
    dict(id="sc#4", db="soccer", difficulty="M", shape="set", order_sensitive=False,
         question="What is the average number of goals per match by league?",
         sql='SELECT l.name AS league, AVG(m.home_team_goal + m.away_team_goal) AS avg_goals '
             'FROM "Match" m JOIN "League" l ON l.id = m.league_id GROUP BY l.name'),
    dict(id="sc#5", db="soccer", difficulty="M", shape="list", order_sensitive=True,
         question="Which season has the most matches?",
         sql='SELECT season, COUNT(*) AS n_matches FROM "Match" '
             'GROUP BY season ORDER BY n_matches DESC, season LIMIT 1'),
    dict(id="sc#6", db="soccer", difficulty="H", shape="list", order_sensitive=True,
         question="Which are the top 10 teams by total goals scored (home and away combined)?",
         sql='SELECT t.team_long_name, SUM(CASE WHEN t.team_api_id = m.home_team_api_id '
             'THEN m.home_team_goal ELSE m.away_team_goal END) AS goals_scored '
             'FROM "Team" t JOIN "Match" m ON t.team_api_id = m.home_team_api_id '
             'OR t.team_api_id = m.away_team_api_id GROUP BY t.team_long_name '
             'ORDER BY goals_scored DESC, t.team_long_name LIMIT 10'),
    dict(id="sc#7", db="soccer", difficulty="H", shape="scalar", order_sensitive=False,
         question="How many matches ended in a home win, an away win, and a draw overall?",
         sql='SELECT SUM(CASE WHEN home_team_goal > away_team_goal THEN 1 ELSE 0 END) AS home_wins, '
             'SUM(CASE WHEN away_team_goal > home_team_goal THEN 1 ELSE 0 END) AS away_wins, '
             'SUM(CASE WHEN home_team_goal = away_team_goal THEN 1 ELSE 0 END) AS draws '
             'FROM "Match"'),
    dict(id="sc#8", db="soccer", difficulty="M", shape="list", order_sensitive=True,
         question="Which player has the highest overall rating?",
         sql='SELECT p.player_name, MAX(pa.overall_rating) AS best_rating '
             'FROM "Player_Attributes" pa JOIN "Player" p ON p.player_api_id = pa.player_api_id '
             'GROUP BY p.player_name ORDER BY best_rating DESC, p.player_name LIMIT 1'),
    dict(id="sc#9", db="soccer", difficulty="H", shape="list", order_sensitive=True,
         question="Who are the top 10 players by average overall rating across their "
                  "attribute records?",
         sql='SELECT p.player_name, AVG(pa.overall_rating) AS avg_rating '
             'FROM "Player_Attributes" pa JOIN "Player" p ON p.player_api_id = pa.player_api_id '
             'GROUP BY p.player_name ORDER BY avg_rating DESC, p.player_name LIMIT 10'),
    dict(id="sc#10", db="soccer", difficulty="M", shape="list", order_sensitive=True,
         question="Which league has the highest average goals per match?",
         sql='SELECT l.name AS league, AVG(m.home_team_goal + m.away_team_goal) AS avg_goals '
             'FROM "Match" m JOIN "League" l ON l.id = m.league_id '
             'GROUP BY l.name ORDER BY avg_goals DESC, l.name LIMIT 1'),
    dict(id="sc#11", db="soccer", difficulty="H", shape="scalar", order_sensitive=False,
         question="How many wins, losses and draws did Arsenal have in the 2015/2016 season?",
         note="gold_questions.md says 'for a given team, in a chosen season'; "
              "concretised to Arsenal / 2015-2016 so the question is answerable.",
         sql='SELECT '
             'SUM(CASE WHEN (m.home_team_api_id = t.team_api_id AND m.home_team_goal > m.away_team_goal) '
             '       OR (m.away_team_api_id = t.team_api_id AND m.away_team_goal > m.home_team_goal) '
             '      THEN 1 ELSE 0 END) AS wins, '
             'SUM(CASE WHEN (m.home_team_api_id = t.team_api_id AND m.home_team_goal < m.away_team_goal) '
             '       OR (m.away_team_api_id = t.team_api_id AND m.away_team_goal < m.home_team_goal) '
             '      THEN 1 ELSE 0 END) AS losses, '
             'SUM(CASE WHEN m.home_team_goal = m.away_team_goal THEN 1 ELSE 0 END) AS draws '
             'FROM "Match" m JOIN "Team" t '
             'ON t.team_api_id IN (m.home_team_api_id, m.away_team_api_id) '
             "WHERE t.team_long_name = 'Arsenal' AND m.season = '2015/2016'"),
    dict(id="sc#12", db="soccer", difficulty="H", shape="set", order_sensitive=False,
         question="What is the total number of goals scored per season across all leagues?",
         sql='SELECT season, SUM(home_team_goal + away_team_goal) AS total_goals '
             'FROM "Match" GROUP BY season'),
    dict(id="sc#13", db="soccer", difficulty="M", shape="list", order_sensitive=True,
         question="Who are the 10 tallest players?",
         note="gold_questions.md says 'tallest / heaviest'; graded on tallest only.",
         sql='SELECT player_name, height FROM "Player" '
             'ORDER BY height DESC, player_name LIMIT 10'),
    dict(id="sc#14", db="soccer", difficulty="H", shape="scalar", order_sensitive=False,
         question="What is the average number of home-team goals compared with the average "
                  "number of away-team goals?",
         sql='SELECT AVG(home_team_goal) AS avg_home_goals, '
             'AVG(away_team_goal) AS avg_away_goals FROM "Match"'),
    dict(id="sc#15", db="soccer", difficulty="H", shape="set", order_sensitive=False,
         question="Which teams never lost a home match in the 2015/2016 season?",
         note="gold_questions.md says 'in a given season'; concretised to 2015/2016.",
         sql='SELECT t.team_long_name FROM "Team" t '
             'WHERE EXISTS (SELECT 1 FROM "Match" m WHERE m.home_team_api_id = t.team_api_id '
             "AND m.season = '2015/2016') "
             'AND NOT EXISTS (SELECT 1 FROM "Match" m WHERE m.home_team_api_id = t.team_api_id '
             "AND m.season = '2015/2016' AND m.home_team_goal < m.away_team_goal)"),
]


def freeze(path="gold_answers.json"):
    import json
    engines = {db: get_engine(url) for db, url in DATABASES.items()}
    out, failed = [], []

    for g in GOLD:
        try:
            cols, rows = run_sql(engines[g["db"]], g["sql"])
        except Exception as exc:
            orig = getattr(exc, "orig", exc)
            failed.append((g["id"], str(orig).splitlines()[0]))
            print(f"  FAIL {g['id']:<6} {str(orig).splitlines()[0][:70]}")
            continue
        rec = dict(g)
        rec["gold_cols"] = [str(c) for c in cols]
        rec["gold_rows"] = [[None if v is None else (float(v) if isinstance(v, (int, float))
                             and not isinstance(v, bool) else str(v)) for v in r] for r in rows]
        rec["n_rows"] = len(rows)
        out.append(rec)
        mark = " *" if g.get("note") else "  "
        print(f"  ok{mark} {g['id']:<6} {g['difficulty']} {g['shape']:<7} "
              f"order={str(g['order_sensitive']):<5} {len(rows):>4} rows  "
              f"first={str(tuple(rows[0]))[:46] if rows else '()'}")

    assert not failed, f"reference SQL failed: {failed}"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(f"\nfroze {len(out)} gold answers -> {path}")
    print("questions with notes (changed or ambiguous):")
    for g in out:
        if g.get("note"):
            print(f"  {g['id']}: {g['note']}")


if __name__ == "__main__":
    freeze()
