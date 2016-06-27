CREATE TABLE lineup (
  id VARCHAR(32) NOT NULL PRIMARY KEY,
  transport VARCHAR(32) NOT NULL,
  modified TIMESTAMP NOT NULL
);

CREATE TABLE station (
  id VARCHAR(12) NOT NULL PRIMARY KEY,
  active BOOLEAN NOT NULL,
  name VARCHAR(64) NOT NULL,
  callsign VARCHAR(32) NOT NULL,
  affiliate VARCHAR(32),
  city VARCHAR(32),
  state CHAR(2),
  logo_url VARCHAR(255),
  logo_width SMALLINT,
  logo_height SMALLINT
);

CREATE TABLE lineup_station (
  lineup_id VARCHAR(32) NOT NULL,
  station_id VARCHAR(32) NOT NULL,
  channel SMALLINT NOT NULL,
  atsc VARCHAR(16),
  PRIMARY KEY (lineup_id, station_id)
);
ALTER TABLE lineup_station ADD CONSTRAINT ls_fk_lineup FOREIGN KEY (lineup_id) REFERENCES lineup ON DELETE CASCADE;
ALTER TABLE lineup_station ADD CONSTRAINT ls_fk_station FOREIGN KEY (station_id) REFERENCES station ON DELETE CASCADE;

CREATE TABLE program (
  id CHAR(14) NOT NULL PRIMARY KEY,
  md5 CHAR(22) NOT NULL,
  title VARCHAR(255) NOT NULL,
  episode_title VARCHAR(255),
  description TEXT,
  long_description TEXT,
  original_air_date DATE,
  season SMALLINT,
  episode SMALLINT,
  genres TEXT,
  venue TEXT,
  teams TEXT,
  game_date DATE,
  entity_type VARCHAR(32) NOT NULL,
  show_type VARCHAR(32),
  movie_release_year SMALLINT,
  duration SMALLINT,
  cast_list TEXT,
  tsv TSVECTOR
);

CREATE TRIGGER program_tsv_update BEFORE INSERT OR UPDATE
ON program FOR EACH ROW EXECUTE PROCEDURE
tsvector_update_trigger(tsv, 'pg_catalog.english', title);

CREATE TABLE station_schedule (
  station_id VARCHAR(12) NOT NULL,
  start_date_utc DATE NOT NULL,
  md5 CHAR(22) NOT NULL,
  PRIMARY KEY (station_id, start_date_utc)
);
ALTER TABLE station_schedule ADD CONSTRAINT ss_fk_station FOREIGN KEY (station_id) REFERENCES station ON DELETE CASCADE;

CREATE TABLE station_program (
  id SERIAL PRIMARY KEY,
  station_id VARCHAR(12) NOT NULL,
  start_date_utc DATE NOT NULL,
  air_date_time TIMESTAMP NOT NULL,
  program_id CHAR(14) NOT NULL,
  duration SMALLINT NOT NULL,
  new BOOLEAN NOT NULL,
  md5 CHAR(22) NOT NULL
);
ALTER TABLE station_program ADD CONSTRAINT sp_fk_station FOREIGN KEY (station_id) REFERENCES station ON DELETE CASCADE;
ALTER TABLE station_program ADD CONSTRAINT sp_fk_program FOREIGN KEY (program_id) REFERENCES program ON DELETE CASCADE;
CREATE UNIQUE INDEX station_program_unq ON station_program (station_id, start_date_utc, air_date_time);

CREATE TABLE season_pass (
  id SERIAL PRIMARY KEY,
  program_title VARCHAR(255) NOT NULL,
  new_only BOOLEAN NOT NULL,
  priority SMALLINT NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX season_pass_unq ON season_pass (program_title);

CREATE TYPE recording_status AS ENUM ('pending', 'scheduled', 'recording', 'ready');

CREATE TABLE recording (
  id SERIAL PRIMARY KEY,
  status recording_status NOT NULL,
  station_program_id INT NOT NULL,
  season_pass_id INT,
  media_path VARCHAR(255) NOT NULL
);
ALTER TABLE recording ADD CONSTRAINT rec_fk_station_program FOREIGN KEY (station_program_id) REFERENCES station_program ON DELETE SET NULL;
ALTER TABLE recording ADD CONSTRAINT rec_fk_season_pass FOREIGN KEY (season_pass_id) REFERENCES season_pass ON DELETE SET NULL;
