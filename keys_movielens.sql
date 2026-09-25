-- MovieLens (ml-latest-small): keys + indexes.
-- Run AFTER load_csv_to_postgres.py --csv-dir ./movielens --db movielens
-- Tables expected: movies, ratings, tags, links
-- Columns are lowercased by the loader: movieid, userid, rating, timestamp, genres, title, tag, imdbid, tmdbid

ALTER TABLE movies ADD PRIMARY KEY (movieid);
ALTER TABLE links  ADD PRIMARY KEY (movieid);

ALTER TABLE links   ADD FOREIGN KEY (movieid) REFERENCES movies(movieid);
ALTER TABLE ratings ADD FOREIGN KEY (movieid) REFERENCES movies(movieid);
ALTER TABLE tags    ADD FOREIGN KEY (movieid) REFERENCES movies(movieid);

CREATE INDEX IF NOT EXISTS idx_ratings_movie ON ratings(movieid);
CREATE INDEX IF NOT EXISTS idx_ratings_user  ON ratings(userid);
CREATE INDEX IF NOT EXISTS idx_tags_movie    ON tags(movieid);

-- Note: `genres` in movies is a pipe-delimited string (e.g. 'Action|Comedy').
-- For genre-level questions, split it in SQL, e.g.:
--   SELECT unnest(string_to_array(genres,'|')) AS genre, count(*) FROM movies GROUP BY 1;
-- `timestamp` columns are Unix epoch seconds; convert with to_timestamp(timestamp).
