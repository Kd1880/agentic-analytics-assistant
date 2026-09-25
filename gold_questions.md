# Gold Benchmark Questions (starter set)

~15 questions per database, easy → hard. These are your evaluation ground truth.
**For each, your team must run the query, verify the answer is correct, and record
that answer as the gold label.** Suggested SQL is a starting point — VERIFY it
against your loaded data (column names/edge cases may differ).

Difficulty: E = easy (1 table / simple agg), M = medium (1 join / grouping),
H = hard (multi-join / date logic / subquery).

---

## MovieLens (movies, ratings, tags, links)

1. (E) How many movies are in the database?
2. (E) How many ratings are there in total?
3. (E) What is the overall average rating?
4. (M) Which 10 movies have the most ratings? `-- join ratings→movies, group by title, count, order desc`
5. (M) Top 10 highest-average-rated movies with at least 50 ratings. `-- HAVING count(*)>=50`
6. (M) How many movies are there per genre? `-- unnest(string_to_array(genres,'|'))`
7. (M) Which user has rated the most movies?
8. (M) Average rating per genre.
9. (H) Average rating per release year (year is in the title, e.g. "Toy Story (1995)"). `-- regexp to extract year`
10. (M) What are the 10 most frequently used tags?
11. (H) Which movies have a high average rating (>4) but fewer than 10 ratings?
12. (H) For each genre, the single highest-rated movie (min 20 ratings).
13. (M) Distribution of rating values (how many 0.5, 1.0, ... 5.0).
14. (H) Which movies are tagged but have no rating?
15. (H) Ratings count trend by year (from the rating timestamp).

## Olist Brazilian E-Commerce

1. (E) How many orders are in the database?
2. (E) What is the total revenue? `-- sum(price) from order_items`
3. (M) Top 10 product categories by revenue (English names). `-- order_items→products→product_category_name_translation`
4. (M) How many orders per order_status?
5. (M) Average review score overall, and per product category.
6. (H) Average delivery time in days (delivered - purchase) for delivered orders.
7. (H) Percentage of orders delivered AFTER the estimated delivery date.
8. (M) Distribution of payment types.
9. (M) Top 10 sellers by total revenue.
10. (M) Number of orders per customer state.
11. (H) Monthly order count over time (from order_purchase_timestamp).
12. (H) Which category has the worst average review score (min 100 orders)?
13. (H) Average freight value by customer state.
14. (M) Average number of items per order.
15. (H) Repeat customers: how many customer_unique_ids placed more than one order?

## European Soccer Database (SQLite: Country, League, Match, Team, Player, Player_Attributes, Team_Attributes)

1. (E) How many matches are in the database?
2. (E) How many players are there?
3. (M) How many matches per league? `-- join Match→League`
4. (M) Average goals per match by league. `-- (home_team_goal + away_team_goal)`
5. (M) Which season has the most matches?
6. (H) Top 10 teams by total goals scored (home + away). `-- join Match→Team on home/away api_id`
7. (H) Home-win vs away-win vs draw counts overall.
8. (M) Player with the highest overall_rating (from Player_Attributes).
9. (H) Top 10 players by average overall_rating across their attribute records.
10. (M) Which league has the highest average goals per match?
11. (H) For a given team, wins/losses/draws in a chosen season.
12. (H) Total goals scored per season across all leagues.
13. (M) Tallest / heaviest players (from Player).
14. (H) Average home-team goals vs average away-team goals (home advantage).
15. (H) Teams that never lost at home in a given season.

---

**Scoring:** run each question through the agent in all 4 configs (baseline,
+self-correction, +memory, +both). Mark correct if the agent's result matches
this gold answer. Report accuracy per database and overall.
