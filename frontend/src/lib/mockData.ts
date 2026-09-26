import type { AskResponse } from "./api";
import type { DbId } from "./databases";

/**
 * Offline sample answers (VITE_USE_MOCK=true, the default) so the UI previews
 * without a backend.
 *
 * The numbers are this project's REAL verified gold answers from
 * gold_answers.json, not invented figures — so mock mode and live mode look
 * consistent instead of contradicting each other.
 */

type Canned = { match: string[]; response: AskResponse };

const base = { provider: "mock", providerFallback: null, truncated: false, elapsedMs: 1200 };

const movielens: Canned[] = [
  {
    match: ["per genre", "each genre", "genre"],
    response: {
      ...base,
      sql: `SELECT g AS genre, COUNT(*) AS n_movies
FROM movies
CROSS JOIN unnest(string_to_array(genres, '|')) AS g
GROUP BY g
ORDER BY n_movies DESC;`,
      columns: ["genre", "n_movies"],
      rows: [
        ["Drama", 4361], ["Comedy", 3756], ["Thriller", 1894], ["Action", 1828],
        ["Romance", 1596], ["Adventure", 1263], ["Crime", 1199], ["Sci-Fi", 980],
        ["Horror", 978], ["Fantasy", 779], ["Children", 664], ["Animation", 611],
      ],
      attempts: 1,
      succeeded: true,
      insight:
        "Drama and Comedy dominate the catalogue. Note the genres column is pipe-delimited, so it has to be split before counting.",
      chartHint: { type: "bar", x: "genre", y: "n_movies" },
    },
  },
  {
    match: ["most ratings", "most-rated", "top 10 movies"],
    response: {
      ...base,
      sql: `SELECT m.title, COUNT(*) AS n_ratings
FROM ratings r
JOIN movies m ON m.movieid = r.movieid
GROUP BY m.movieid, m.title
ORDER BY n_ratings DESC
LIMIT 10;`,
      columns: ["title", "n_ratings"],
      rows: [
        ["Forrest Gump (1994)", 329], ["Shawshank Redemption, The (1994)", 317],
        ["Pulp Fiction (1994)", 307], ["Silence of the Lambs, The (1991)", 279],
        ["Matrix, The (1999)", 278], ["Star Wars: Episode IV - A New Hope (1977)", 251],
        ["Jurassic Park (1993)", 238], ["Braveheart (1995)", 237],
        ["Terminator 2: Judgment Day (1991)", 224], ["Schindler's List (1993)", 220],
      ],
      attempts: 1,
      succeeded: true,
      insight:
        "Forrest Gump leads on volume with 329 ratings, narrowly ahead of Shawshank — which holds a much higher average score.",
      chartHint: { type: "bar", x: "title", y: "n_ratings" },
    },
  },
  {
    match: ["average rating per genre", "avg rating per genre"],
    response: {
      ...base,
      sql: `SELECT g AS genre, AVG(r.rating) AS avg_rating
FROM movies m
JOIN ratings r ON r.movieid = m.movieid
CROSS JOIN unnest(string_to_array(m.genres, '|')) AS g
GROUP BY g
ORDER BY avg_rating DESC;`,
      columns: ["genre", "avg_rating"],
      rows: [
        ["Film-Noir", 3.92], ["War", 3.81], ["Documentary", 3.8], ["Crime", 3.66],
        ["Drama", 3.66], ["Mystery", 3.63], ["Animation", 3.6], ["IMAX", 3.62],
        ["Western", 3.58], ["Musical", 3.56], ["Romance", 3.51], ["Comedy", 3.38],
      ],
      attempts: 2,
      succeeded: true,
      insight:
        "Film-Noir rates highest on average. The first attempt failed on an unnest alias and was fixed automatically.",
      chartHint: { type: "bar", x: "genre", y: "avg_rating" },
    },
  },
  {
    match: ["each year", "by year", "trend"],
    response: {
      ...base,
      sql: `SELECT EXTRACT(YEAR FROM to_timestamp(timestamp)) AS year,
       COUNT(*) AS n_ratings
FROM ratings
GROUP BY year
ORDER BY year;`,
      columns: ["year", "n_ratings"],
      rows: [
        [1996, 6040], [1997, 1916], [1998, 507], [1999, 2439], [2000, 10061],
        [2001, 3922], [2002, 3478], [2003, 4014], [2004, 3279], [2005, 5813],
        [2006, 4059], [2007, 7114], [2008, 4351], [2009, 4158], [2010, 3746],
      ],
      attempts: 1,
      succeeded: true,
      insight:
        "Rating activity peaks in 2000 with 10,061 ratings. The timestamps are Unix epoch seconds, so they need converting first.",
      chartHint: { type: "line", x: "year", y: "n_ratings" },
    },
  },
];

const olist: Canned[] = [
  {
    match: ["categories by revenue", "revenue", "categor"],
    response: {
      ...base,
      sql: `SELECT t.product_category_name_english AS category,
       SUM(oi.price) AS revenue
FROM order_items oi
JOIN products p ON p.product_id = oi.product_id
JOIN product_category_name_translation t
  ON t.product_category_name = p.product_category_name
GROUP BY category
ORDER BY revenue DESC
LIMIT 10;`,
      columns: ["category", "revenue"],
      rows: [
        ["health_beauty", 1258681.34], ["watches_gifts", 1205005.68],
        ["bed_bath_table", 1036988.68], ["sports_leisure", 988048.97],
        ["computers_accessories", 911954.32], ["furniture_decor", 729762.49],
        ["cool_stuff", 635290.85], ["housewares", 632248.66],
        ["auto", 592720.11], ["garden_tools", 485256.46],
      ],
      attempts: 2,
      succeeded: true,
      insight:
        "Health & beauty leads at R$1.26M. Watches & gifts earns nearly as much from far fewer orders — a high-ticket category.",
      chartHint: { type: "bar", x: "category", y: "revenue" },
    },
  },
  {
    match: ["delivery time", "delivery", "days"],
    response: {
      ...base,
      sql: `SELECT AVG(EXTRACT(EPOCH FROM (order_delivered_customer_date
                         - order_purchase_timestamp)) / 86400.0) AS avg_days
FROM orders
WHERE order_status = 'delivered'
  AND order_delivered_customer_date IS NOT NULL;`,
      columns: ["avg_days"],
      rows: [[12.558217098051975]],
      attempts: 1,
      succeeded: true,
      insight: "avg_days: 12.56 — delivered orders take about twelve and a half days on average.",
      chartHint: { type: "scalar", label: "avg_days" },
    },
  },
  {
    match: ["customer state", "per state", "state"],
    response: {
      ...base,
      sql: `SELECT c.customer_state, COUNT(*) AS n_orders
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY c.customer_state
ORDER BY n_orders DESC;`,
      columns: ["customer_state", "n_orders"],
      rows: [
        ["SP", 41746], ["RJ", 12852], ["MG", 11635], ["RS", 5466], ["PR", 5045],
        ["SC", 3637], ["BA", 3380], ["DF", 2140], ["ES", 2033], ["GO", 2020],
        ["PE", 1652], ["CE", 1336],
      ],
      attempts: 1,
      succeeded: true,
      insight: "São Paulo alone accounts for 41,746 orders — about 42% of the marketplace.",
      chartHint: { type: "bar", x: "customer_state", y: "n_orders" },
    },
  },
  {
    match: ["payment type", "payment"],
    response: {
      ...base,
      sql: `SELECT payment_type, COUNT(*) AS n
FROM order_payments
GROUP BY payment_type
ORDER BY n DESC;`,
      columns: ["payment_type", "n"],
      rows: [
        ["credit_card", 76795], ["boleto", 19784], ["voucher", 5775],
        ["debit_card", 1529], ["not_defined", 3],
      ],
      attempts: 1,
      succeeded: true,
      insight: "Credit card dominates with 76,795 payments; boleto is a distant second at 19,784.",
      chartHint: { type: "bar", x: "payment_type", y: "n" },
    },
  },
];

const soccer: Canned[] = [
  {
    match: ["per league", "matches were played", "league"],
    response: {
      ...base,
      sql: `SELECT l.name AS league, COUNT(*) AS n_matches
FROM "Match" m
JOIN "League" l ON l.id = m.league_id
GROUP BY l.name
ORDER BY n_matches DESC;`,
      columns: ["league", "n_matches"],
      rows: [
        ["England Premier League", 3040], ["France Ligue 1", 3040],
        ["Spain LIGA BBVA", 3040], ["Italy Serie A", 3017],
        ["Germany 1. Bundesliga", 2448], ["Netherlands Eredivisie", 2448],
        ["Portugal Liga ZON Sagres", 2052], ["Poland Ekstraklasa", 1920],
        ["Scotland Premier League", 1824], ["Belgium Jupiler League", 1728],
        ["Switzerland Super League", 1422],
      ],
      attempts: 1,
      succeeded: true,
      insight:
        "England, France and Spain tie on 3,040 matches each — eight seasons of a 20-team league.",
      chartHint: { type: "bar", x: "league", y: "n_matches" },
    },
  },
  {
    match: ["total goals", "top 10 teams", "goals scored"],
    response: {
      ...base,
      sql: `SELECT t.team_long_name,
       SUM(CASE WHEN t.team_api_id = m.home_team_api_id
                THEN m.home_team_goal ELSE m.away_team_goal END) AS goals_scored
FROM "Team" t
JOIN "Match" m ON t.team_api_id = m.home_team_api_id
               OR t.team_api_id = m.away_team_api_id
GROUP BY t.team_long_name
ORDER BY goals_scored DESC
LIMIT 10;`,
      columns: ["team_long_name", "goals_scored"],
      rows: [
        ["FC Barcelona", 849], ["Real Madrid CF", 843], ["Celtic", 695],
        ["FC Bayern Munich", 653], ["PSV", 652], ["Ajax", 647],
        ["FC Basel", 619], ["Manchester City", 606], ["Chelsea", 583],
        ["Manchester United", 582],
      ],
      attempts: 2,
      succeeded: true,
      insight:
        "Barcelona edges Real Madrid 849 to 843. A side-aware CASE is essential here — summing both teams' goals would count goals conceded too.",
      chartHint: { type: "bar", x: "team_long_name", y: "goals_scored" },
    },
  },
  {
    match: ["home win", "draw", "away win"],
    response: {
      ...base,
      sql: `SELECT SUM(CASE WHEN home_team_goal > away_team_goal THEN 1 ELSE 0 END) AS home_wins,
       SUM(CASE WHEN away_team_goal > home_team_goal THEN 1 ELSE 0 END) AS away_wins,
       SUM(CASE WHEN home_team_goal = away_team_goal THEN 1 ELSE 0 END) AS draws
FROM "Match";`,
      columns: ["home_wins", "away_wins", "draws"],
      rows: [[11917, 7466, 6596]],
      attempts: 1,
      succeeded: true,
      insight:
        "Home advantage is real: hosts win 11,917 of 25,979 matches (45.9%), against 7,466 away wins.",
      chartHint: { type: "bar", x: "home_wins", y: "away_wins" },
    },
  },
  {
    match: ["players", "rating"],
    response: {
      ...base,
      sql: `SELECT p.player_name, AVG(pa.overall_rating) AS avg_rating
FROM "Player_Attributes" pa
JOIN "Player" p ON p.player_api_id = pa.player_api_id
GROUP BY p.player_name
ORDER BY avg_rating DESC, p.player_name
LIMIT 10;`,
      columns: ["player_name", "avg_rating"],
      rows: [
        ["Lionel Messi", 92.19], ["Gianluigi Buffon", 90.67], ["Cristiano Ronaldo", 90.24],
        ["Xavi Hernandez", 89.5], ["Andres Iniesta", 88.95], ["Wayne Rooney", 88.42],
        ["Iker Casillas", 88.24], ["Zlatan Ibrahimovic", 87.86], ["Manuel Neuer", 87.61],
        ["Franck Ribery", 87.29],
      ],
      attempts: 1,
      succeeded: true,
      insight: "Messi averages 92.19 across a decade of attribute snapshots.",
      chartHint: { type: "bar", x: "player_name", y: "avg_rating" },
    },
  },
];

const catalogue: Record<DbId, Canned[]> = { movielens, olist, soccer };

export async function mockAnswer(db: DbId, question: string): Promise<AskResponse> {
  const q = question.toLowerCase();
  const hit = catalogue[db].find((c) => c.match.some((m) => q.includes(m)));
  await new Promise((r) => setTimeout(r, 1300));
  return hit ? hit.response : catalogue[db][0].response;
}
