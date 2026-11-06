--CREATE DATABASE {database} WITH OWNER={remote_user};

CREATE TABLE players (
    id UUID PRIMARY KEY,
    name varchar(250) NOT NULL,
    number smallint NOT NULL,
    team_id UUID NOT NULL
);

CREATE TABLE teams (
    id UUID PRIMARY KEY,
    abbrev varchar(10) NOT NULL,
    name varchar(250) NOT NULL,
    city varchar(250) NOT NULL
);

CREATE TABLE games (
    sk_id UUID PRIMARY KEY,
    game_id integer NOT NULL,
    starting_date timestamp NOT NULL,
    timezone varchar(10) NOT NULL,
    home_team_id UUID NOT NULL,
    away_team_id UUID NOT NULL,
    home_team_score smallint NOT NULL CHECK (home_team_score >= 0),
    away_team_score smallint NOT NULL CHECK (away_team_score >= 0),
    ended_in_ot boolean NOT NULL,
    ended_in_shootout boolean NOT NULL
);

-- CREATE TABLE game_events (
--     sk_id UUID PRIMARY KEY,
--     game_id UUID NOT NULL,
--     event_type varchar(100) NOT NULL,
--     period integer NOT NULL,
--     time_elapsed integer NOT NULL CHECK (time_elapsed >= 0 AND time_elapsed <= 1200),
--     location_x real,
--     location_y real,
--     players_on_ice UUID[] NOT NULL,
--     concerned_players UUID[],
--     CONSTRAINT location_tuple CHECK ((location_x is null AND location_y is null) OR not (location_x is null and location_y is null))
-- )

CREATE TABLE faceoff_events (
    sk_id UUID PRIMARY KEY,
    game_id UUID NOT NULL,
    period integer NOT NULL,
    time_elapsed integer NOT NULL CHECK (time_elapsed >= 0 AND time_elapsed <= 1200),
    location_x real,
    location_y real,
    winning_team_id UUID NOT NULL,
    zone smallint NOT NULL,
    winning_player_id UUID NOT NULL,
    loosing_player_id UUID NOT NULL
)



