from collections import defaultdict
import logging
from pathlib import Path
import pickle
from itertools import chain
import json

from genson import SchemaBuilder
import pandas as pd
import requests
from requests.status_codes import codes as status_codes
from tqdm import tqdm

from objects import *
from pbp_parsers import parse_event

def scrape_teams(output_dir: Path) -> list[Team]:
    #store as https://api.nhle.com/stats/rest/en/
    response = requests.get("https://api.nhle.com/stats/rest/en/team")
    response.raise_for_status()

    json_response = response.json()
    teams:list[Team] = []
    for team_json in json_response["data"]:
        teams.append(Team(**{k:v for k, v in team_json.items() if k in Team.__annotations__.keys()}))

    headers = ["team_id", "full_name", "tri_code"]
    data = []
    for team in teams:
        data.append([team.id, team.fullName, team.triCode])
    pd.DataFrame(data, columns=headers).to_csv(output_dir / "teams.csv", index=False)

    return teams


def parse_player_seasons(data:dict, season_type:type[PlayerSeason]):
    seasons = []
    for season in data["seasonTotals"]:
        seasons.append(season_type(**season))

    return {"seasonTotals":seasons}


def scrape_player(player_id) -> Player:
    response = requests.get(f"https://api-web.nhle.com/v1/player/{player_id}/landing")
    response.raise_for_status()

    json_response = response.json()

    if json_response["position"] == "G":
        return Goaltender(**json_response | parse_player_seasons(json_response, GoaltenderSeason))
    else:
        return Skater(**json_response | parse_player_seasons(json_response, SkaterSeason))


def scrape_roster(season:int, team:Team) -> Roster:
    """
    We'll only scrape rosters to be able to find missing player ids in the play by play
    Rosters only include 20 players, I don't know how they deal with callups etc.

    It should at least help us figure out the ids
    """
    response = requests.get(f"https://api-web.nhle.com/v1/roster/{team.triCode}/{season}{season+1}")
    response.raise_for_status()
    json = response.json()
    roster_players = []
    for player in list(chain.from_iterable(list(json.values()))):
        roster_players.append(PlayerIdentifiers(player["id"], player["firstName"]["default"], player["lastName"]["default"], player.get("sweaterNumber", None)))

    return Roster(team.id, roster_players)

def scrape_all_rosters(teams:list[Team], seasons:list[int], output_dir:Path):
    headers = ["teamId", "teamTriCode", "season", "playerId", "playerFirstName", "playerLastName", "playerNumber"]
    progress_bar = tqdm(total=len(seasons) * len(teams))
    for season in seasons:
        data = []
        for team in teams:
            progress_bar.set_description(f"{season} - {team.triCode}")
            try:
                roster = scrape_roster(season, team)
            except requests.exceptions.HTTPError as http_err:
                if http_err.response is not None and http_err.response.status_code == status_codes.not_found:
                    continue
                raise http_err

            for player in roster.players:
                data.append([team.id, team.triCode, season, player.id, player.first_name, player.last_name, player.number])
            progress_bar.update(1)

        df = pd.DataFrame(data, columns=headers)
        df.to_csv(output_dir / f"all_rosters_{season}{season+1}.csv", index=False)

def scrape_schedule(team:Team, season:int, skip_preseasons=True) -> Schedule:
    response = requests.get(f"https://api-web.nhle.com/v1/club-schedule-season/{team.triCode}/{season}{season+1}")
    response.raise_for_status()
    json = response.json()
    games:list[Game] = []
    for game in json["games"]:
        if (skip_preseasons and game["gameType"] == 1) or game["gameScheduleState"] == "CNCL":
            continue
        last_period_type = game["gameOutcome"]["lastPeriodType"]
        ended_in_ot = last_period_type == "OT"
        ended_in_so = last_period_type == "SO"
        games.append(Game(game["id"], datetime.strptime(game["gameDate"], "%Y-%m-%d"), game["homeTeam"]["id"], game["awayTeam"]["id"], game["homeTeam"]["score"], game["awayTeam"]["score"], ended_in_ot, ended_in_so))

    return Schedule(team.id, season, games)


def scrape_all_schedules(teams:list[Team], seasons:list[int], output_dir:Optional[Path]) -> list[Schedule]:
    if output_dir is not None:
        output_dir.mkdir(exist_ok=True, parents=True)
    headers = ["teamId", "season", "gameId", "date", "homeTeamId", "awayTeamId", "homeTeamScore", "awayTeamScore", "endedInOvertime", "endedInShootout"]
    progress_bar = tqdm(total=len(seasons) * len(teams))
    all_schedules = []
    for season in seasons:
        data = []
        if output_dir is not None and (output_dir / f"all_schedules_{season}{season+1}.csv").exists():
            continue
        for team in teams:
            progress_bar.set_description(f"{season} - {team.triCode}")
            try:
                schedule = scrape_schedule(team, season)
                if len(schedule.games) != 0:
                    all_schedules.append(schedule)
            except requests.exceptions.HTTPError as http_err:
                if http_err.response is not None and http_err.response.status_code == status_codes.not_found:
                    continue
                raise http_err

            for game in schedule.games:
                data.append([team.id, season, game.id, game.date, game.homeTeamId, game.awayTeamId, game.homeTeamScore, game.awayTeamScore, game.endedInOvertime, game.endedInShootout])
            progress_bar.update(1)

        if output_dir is not None:
            df = pd.DataFrame(data, columns=headers)
            df.to_csv(output_dir / f"all_schedules_{season}{season+1}.csv", index=False)

    return all_schedules



def scan_pbp_schemas(schedules:list[Schedule], output_dir:Path):
    """
    I'd only pass a single schedule, assuming all possible variations of a play happens at least once in a season
    """
    output_dir.mkdir(exist_ok=True, parents=True)
    schema_builder_per_event_types: dict[str, SchemaBuilder] = defaultdict(SchemaBuilder)
    progress_bar = tqdm(total=len(schedules) * 82)
    reasons = set()
    for schedule in schedules:
        progress_bar.set_description(str(schedule.team_id))
        for game in schedule.games:
            response = requests.get(f"https://api-web.nhle.com/v1/gamecenter/{game.id}/play-by-play")  
            response.raise_for_status()
            json_data = response.json()

            for play in json_data["plays"]:
                event_type = play["typeDescKey"]
                if event_type == "penalty":
                    if play["details"]["typeCode"] not in reasons:
                        print(play["details"]["typeCode"])
                        reasons.add(play["details"]["typeCode"])
                schema_builder_per_event_types[event_type].add_object(play)
            progress_bar.update(1)
    
    for k, v in schema_builder_per_event_types.items():
        schema = v.to_schema()
        with (output_dir / f"play-{k}.schema.json").open("w", encoding="utf-8") as fs:
            json.dump(schema, fs, indent=2)
        print(f"Schema for {k} has been saved to {output_dir / f"play-{k}.schema.json"}")


def scrape_pbp(game_id:int) -> list[Event]:
    response = requests.get(f"https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play")
    response.raise_for_status()

    data = response.json()

    plays:list[Event] = []
    for play in data["plays"]:
        event = parse_event(game_id, play)
        if event is not None:
            plays.append(event)

    return plays
    

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("log.log", encoding="utf-8"),
            logging.StreamHandler(),
        ]
    )
    seasons_to_scrape = list(range(2008, 2027))
    data_folder = Path(__file__).parent.parent.parent / "data"
    #teams = scrape_teams(data_folder)
    
    #print("Scraping rosters...")
    #rosters = scrape_all_rosters(teams, list(range(2007, 2027)), data_folder / "rosters")
    #print("Scraping schedules...")

    csv_files = list((data_folder / "schedules").glob("*.csv"))
    parsed_game_ids = set()
    games_in_a_season = 1344
    progress_bar = tqdm(total=len(csv_files) *  games_in_a_season)
    for csv in (data_folder / "schedules").glob("*.csv"):
        season = csv.stem.split("_")[-1]
        output_file = data_folder / "pbp" / f"pbp_{season}.pkl"
        if output_file.exists():
            continue
        season_events = []
        df = pd.read_csv(csv)
        for game_id in list(df["gameId"]):
            if game_id not in parsed_game_ids:
                try:
                    season_events += scrape_pbp(int(game_id))
                    parsed_game_ids.add(game_id)
                except KeyError as e:
                    logging.exception(e)
                    logging.info(f"The season {season} doesn't have all required metadata. It will be ignored")
                    progress_bar.update(games_in_a_season)
                    break
            progress_bar.update()
        else:
            with (data_folder / "pbp" / f"pbp_{season}.pkl").open("wb") as fs:
                pickle.dump(season_events, fs)

    #schedules = scrape_all_schedules(teams, list(range(2007, 2026)), data_folder / "schedules")
    #last_year_schedules = scrape_all_schedules(teams, list(range(2025, 2026)), None)
    #scan_pbp_schemas(last_year_schedules[::10], data_folder / "games" / "schemas")
    
