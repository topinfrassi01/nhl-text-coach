from abc import ABC, abstractmethod
import re
from typing import Generic, TypeVar, Callable

from attrs import asdict, fields
import pandas as pd
import numpy as np
from pandas import Series

from database_building.pbp_parsers.objects import Event, EventSpecificAttributes

from .regexes import *
from .objects import *


def find_player_id_in_row(player_last_name:str, player_team:str, row:pd.Series) -> int:
    (home_team, away_team) = row[["Home_Team", "Away_Team"]]
    column_prefix = None
    player_team = TEAM_ABBREV_EQUIVALENCES.get(player_team, player_team)
    home_team = TEAM_ABBREV_EQUIVALENCES.get(home_team, home_team)
    away_team = TEAM_ABBREV_EQUIVALENCES.get(away_team, away_team)

    if home_team == player_team:
        column_prefix = "home"
    elif away_team == player_team:
        column_prefix = "away"
    else:
        raise ValueError(f"{player_team} doesn't match either home: {home_team} or away: {away_team}")

    player_names = row[[f"{column_prefix}Player{i}" for i in range(1, 7)]]

    matched_id = None
    for i, player_name in enumerate(player_names):
        if player_last_name in player_name:
            if matched_id is None:
                try:
                    matched_id = int(row[f"{column_prefix}Player{i+1}_id"])
                except ValueError as val_error:
                    raise NotImplementedError("Player has nan ID, need to implement secondary search based on parsed players or other events with same player") from val_error
            else:
                raise NotImplementedError("Multiple players share the same last name on the ice. Search needs to be implemented")

    if matched_id is None:
        raise ValueError(f"Player {player_last_name} was not found amongst {player_names}")

    return matched_id


def specific_fields_for_subclass(
    base_cls: type,
    subclass: type,
) -> set:
    base_names = {
        field.name for field in fields(base_cls)
    }

    specific_fields: set[str] = {
        field.name for field in fields(subclass)
        if field.name not in base_names
    }

    return specific_fields



class GameParser:
    time_parser = re.compile(PERIOD_START_REGEX)
    def parse(self, game_events:pd.Series) -> Game:
        game_id = int(game_events["Game_Id"].values[0])
        date = str(game_events["Date"].values[0])
        home_team_abbrev = str(game_events["Home_Team"].values[0])
        away_team_abbrev = str(game_events["Away_Team"].values[0])
        period_start_desc = str(game_events.loc[(game_events["Period"] == 1) & (game_events["Event"] == "PSTR"), "Description"].values[0])
        match = re.match(GameParser.time_parser, period_start_desc)

        if not match:
            raise RegexParserException(GameParser, period_start_desc)

        time = match.group(1)
        hours, minutes = (s.zfill(2) for s in time.split(":"))
        tz = match.group(2)

        datetime_starting = datetime.strptime(f'{date} {hours}:{minutes}', "%Y-%m-%d %I:%M")

        game_score = tuple([
            int(s)
            for s 
            in game_events.loc[game_events["Event"] == "GEND", ["Home_Score", "Away_Score"]].values[0] # pyright: ignore[reportGeneralTypeIssues]
        ])

        ended_in_shootout = len(game_events.loc[game_events["Event"] == "SOC"] ) > 0
        ended_in_ot = (not ended_in_shootout) and (game_events["Period"].max() > 3)

        return Game(
            game_id,
            datetime_starting,
            tz,
            home_team_abbrev,
            away_team_abbrev,
            game_score, # pyright: ignore[reportArgumentType]
            ended_in_ot,
            ended_in_shootout
        )


TEvent = TypeVar('TEvent', bound=Event)
class EventParser(ABC, Generic[TEvent]):
    event_type: type[TEvent]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        event_cls = cls.__dict__.get("event_type")

        if event_cls is None:
            raise TypeError(f"{cls.__name__} must define event_type")

        if not isinstance(event_cls, type) or not issubclass(event_cls, Event):
            raise TypeError(f"{cls.__name__}.event_type must be an Event subclass")

    def __call__(self, row:pd.Series) -> TEvent:
        base_event = self._parse_common_data(row)
        specific_event_data = self._parse_specific_data(row)

        return self.event_type(**asdict(base_event), **asdict(specific_event_data))

    def _parse_common_data(self, row:pd.Series) -> Event:
        if np.isnan(row["xC"]):
            location = None
        else:
            location = (float(row["xC"]), float(row["xC"]))

        return Event(
            int(row["Game_Id"]),
            int(row["Period"]),
            int(row["Seconds_Elapsed"]),
            location,
            int(row["Home_Goalie_Id"]),
            int(row["Away_Goalie_Id"])
        )

    @abstractmethod
    def _parse_specific_data(self, row:pd.Series) -> EventSpecificAttributes[TEvent]:
        pass


class ParserFAC(EventParser[Faceoff]):
    """
    # example : NSH won Neu. Zone - NSH #90 O'REILLY vs TBL #71 CIRELLI
    """
    event_type = Faceoff
    regex = re.compile(rf"^({TEAM_IDENTIFICATION_REGEX})\swon\s{ZONE_REGEX}\s-\s{PLAYER_IDENTIFICATION_REGEX}\svs\s{PLAYER_IDENTIFICATION_REGEX}$")

    def _parse_specific_data(self, row: pd.Series) -> EventSpecificAttributes[Faceoff]:
        description = row["Description"]
        groups = re.match(self.regex, description)

        if not groups:
            raise RegexParserException(type(self), description)

        (
            winner_team,
            zone,
            _,
            _,
            winner_name,
            looser_team,         
            _,
            looser_name
        ) = groups.groups()

        winning_player_id = row["p1_ID"]
        if np.isnan(winning_player_id):
            winning_player_id = find_player_id_in_row(winner_name, winner_team, row)

        loosing_player_id = row["p2_ID"]
        if np.isnan(loosing_player_id):
            loosing_player_id = find_player_id_in_row(looser_name, looser_team, row)

        return FaceoffSpecificAttributes(
            TEAM_ABBREV_EQUIVALENCES.get(winner_team, winner_team),
            Zone[zone],
            winning_player_id,
            loosing_player_id
        )


class ParserSHOT(EventParser[Shot]):
    # Example : TBL ONGOAL - #43 RADDYSH, Wrist , Off. Zone, 39 ft.
    event_type = Shot
    regex = re.compile(rf"^{PLAYER_IDENTIFICATION_REGEX},\s{SHOT_REGEX}\s?,.*{ZONE_REGEX}, ([0-9]*).*$")

    def _parse_specific_data(self, row: pd.Series) -> EventSpecificAttributes[Shot]:
        description = row["Description"]
        groups = re.match(self.regex, description)

        if not groups:
            raise RegexParserException(type(self), description)

        (
            player_team,
            _,
            player_name,
            shot_type,
            zone,
            distance_to_net,         
        ) = groups.groups()

        is_penalty_shot = False
        if "Penalty Shot" in shot_type:
            is_penalty_shot = True
            shot_type = shot_type.replace("Penalty Shot", "").replace(",","").strip()

        is_defensive_deflection = False
        if "Defensive Deflection" in shot_type:
            is_defensive_deflection = True
            shot_type = shot_type.replace("Defensive Deflection", "").replace(",","").strip()

        player_id = find_player_id_in_row(player_name, player_team, row)
        return ShotSpecificAttributes(
            player_id,
            shot_type,
            Zone[zone],
            float(distance_to_net),
            is_defensive_deflection,
            is_penalty_shot
        )


class ParserHIT(EventParser[Hit]):
    # Example : TBL ONGOAL - #43 RADDYSH, Wrist , Off. Zone, 39 ft.
    event_type = Hit
    regex = re.compile(rf"^{PLAYER_IDENTIFICATION_REGEX}\sHIT\s{PLAYER_IDENTIFICATION_REGEX},\s{ZONE_REGEX}")

    def _parse_specific_data(self, row: pd.Series) -> EventSpecificAttributes[Hit]:
        description = row["Description"]
        groups = re.match(self.regex, description)

        if not groups:
            raise RegexParserException(type(self), description)

        (
            hitting_player_team,
            hitting_player_number,
            hitting_player_name,
            hit_player_team,
            hit_player_number,
            hit_player_name,            
            zone,
        ) = groups.groups()

        hitting_player_id = find_player_id_in_row(hitting_player_name, hitting_player_team, row)
        hit_player_id = find_player_id_in_row(hit_player_name, hit_player_team, row)

        return HitSpecificAttributes(
            hitting_player_id,
            hit_player_id,
            Zone[zone]
        )


class ParserSTOP(EventParser[Stop]):
    event_type = Stop
    def _parse_specific_data(self, row: pd.Series) -> EventSpecificAttributes[Stop]:
        return StopSpecificAttributes(row["Description"])


class ParserBLOCK(EventParser[BlockedShot]):
    #Examples :
    # - NSH #9 FORSBERG BLOCKED BY TEAMMATE, Snap, Off. Zone
    # - NSH #90 O'REILLY OPPONENT-BLOCKED BY TBL #43 RADDYSH, Snap, Def. Zone 
    event_type = BlockedShot
    regex = re.compile(rf"^{PLAYER_IDENTIFICATION_REGEX}\s(?:OPPONENT-BLOCKED|BLOCKED)\sBY\s({PLAYER_IDENTIFICATION_REGEX.replace('(', '(?:')}|TEAMMATE|OTHER),\s{SHOT_REGEX},\s{ZONE_REGEX}\s?(Flub|Broken Stick|)$")
    def _parse_specific_data(self, row: Series) -> EventSpecificAttributes[BlockedShot]:
        description = row["Description"]
        groups = re.match(self.regex, description.strip())

        if not groups:
            raise RegexParserException(type(self), description)

        (
            shooting_player_team,
            shooting_player_number,
            shooting_player_name,
            blocking_player_info, 
            shot_type,       
            zone,
            additional_info
        ) = groups.groups()

        is_flub = additional_info == "FLUB"
        is_broken_stick = additional_info == "BROKEN_STICK"
        
        if blocking_player_info != "TEAMMATE":
            submatch = re.match(PLAYER_IDENTIFICATION_REGEX, blocking_player_info)
            
            (team, number, name) = submatch.groups() # pyright: ignore[reportOptionalMemberAccess]
            blocking_player_id = find_player_id_in_row(name, team, row)
            is_blocked_by_teammate = False
        else:
            blocking_player_id = None
            is_blocked_by_teammate = True

        shooting_player_id = find_player_id_in_row(shooting_player_name, shooting_player_team, row)

        return BlockedShotSpecificAttributes(
            shooting_player_id,
            blocking_player_id,
            shot_type,
            Zone[zone],
            is_blocked_by_teammate,
            is_flub,
            is_broken_stick
        )


class ParserMISS(EventParser[MissedShot]):
    event_type = MissedShot
    regex = re.compile(rf"^{PLAYER_IDENTIFICATION_REGEX},\s{SHOT_REGEX},\s?([\s\w]*|$),\s{ZONE_REGEX},\s([0-9]*)\sft\.\s?(Flub|Broken Stick|)$")
    regex_failed_attempt = re.compile(rf"^{PLAYER_IDENTIFICATION_REGEX},(\sPenalty Shot,|) Failed Attempt\s?(Flub|Broken Stick|)$")
    def _parse_specific_data(self, row: Series) -> EventSpecificAttributes[MissedShot]:
        description = row["Description"]

        if "Failed Attempt" in description:
            groups = re.match(self.regex_failed_attempt, description)
            if not groups:
                raise RegexParserException(type(self), description)
            (shooting_player_team, shooting_player_number, shooting_player_name, additional_info) = groups.groups()
            shot_type = None
            direction = None
            zone = None
            distance_to_net = None
        else:
            groups = re.match(self.regex, description.strip())

            if not groups:
                raise RegexParserException(type(self), description)

            (
                shooting_player_team,
                shooting_player_number,
                shooting_player_name,
                shot_type, 
                direction,       
                zone,
                distance_to_net,
                additional_info
            ) = groups.groups()

        is_flub = additional_info == "FLUB"
        is_broken_stick = additional_info == "BROKEN_STICK"

        shooting_player_id = find_player_id_in_row(shooting_player_name, shooting_player_team, row)

        return MissedShotSpecificAttributes(
            shooting_player_id,
            shot_type,
            direction,
            zone,
            distance_to_net,
            is_flub,
            is_broken_stick
        )


class ParserGIVE(EventParser[Giveaway]):
    event_type = Giveaway
    regex = re.compile(rf"^{PLAYER_IDENTIFICATION_REGEX},\s{ZONE_REGEX}$")
    def _parse_specific_data(self, row: Series) -> EventSpecificAttributes[Giveaway]:
        description = row["Description"]
        match = re.match(self.regex, description.strip())

        if not match:
            raise RegexParserException(type(self), description)

        (
            team,
            number,
            name,
            zone
        ) = match.groups()

        player_id = find_player_id_in_row(name, team, row)

        return GiveawaySpecificAttributes(
            player_id,
            Zone[zone]
        )



class ParserTAKE(EventParser[Takeaway]):
    event_type = Takeaway
    regex = re.compile(rf"^{PLAYER_IDENTIFICATION_REGEX},\s{ZONE_REGEX}$")
    def _parse_specific_data(self, row: Series) -> EventSpecificAttributes[Takeaway]:
        description = row["Description"]
        match = re.match(self.regex, description.strip())

        if not match:
            raise RegexParserException(type(self), description)

        (
            team,
            number,
            name,
            zone
        ) = match.groups()

        player_id = find_player_id_in_row(name, team, row)

        return TakeawaySpecificAttributes(
            player_id,
            Zone[zone]
        )

# TODO : I'll get back to it, it sucks because there seems to be a billion ways the description can be parsed
# class ParserPENL(EventParser[Penalty]):
#     event_type = Penalty
#     TIME_REGEX = r"\(([0-9]{1,2})\smin\)"
#     regex_drawn_by = re.compile(rf"^{PLAYER_IDENTIFICATION_REGEX},([\s\w-]*).*{TIME_REGEX},\s{ZONE_REGEX}.*:\s{PLAYER_IDENTIFICATION_REGEX}$")
#     regex_no_drawn = re.compile(rf"^{PLAYER_IDENTIFICATION_REGEX},([\s\w-]*).*{TIME_REGEX},\s{ZONE_REGEX}$")
#     regex_served_by_no_drawn = re.compile(rf"^{PLAYER_IDENTIFICATION_REGEX},([\s\w-]*).*{TIME_REGEX}.*{PLAYER_IDENTIFICATION_REGEX}$")
#     def _parse_specific_data(self, row: Series) -> EventSpecificAttributes[Penalty]:
#         description = row["Description"]

#         # There's a bug in the writing of the pbp data (at least for those I've seen)
#         description = description.replace(u'\xa0', ',')
#         match = re.match(self.regex, description.strip())

#         if not match:
#             raise RegexParserException(type(self), description)


class ParserGOAL(EventParser[Goal]):
    event_type = Goal
    regex_up_to_assists = re.compile(rf"^{PLAYER_IDENTIFICATION_REGEX},\s{SHOT_REGEX},\s{ZONE_REGEX},\s([0-9]*)\sft\..*$")
    assisting_player_regex = re.compile(rf"^{PLAYER_IDENTIFICATION_REGEX}\([0-9]*\)$")
    def _parse_specific_data(self, row: Series) -> EventSpecificAttributes[Goal]:
        description: str = row["Description"]
        match = re.match(self.regex_up_to_assists, description.strip())

        if not match:
            raise RegexParserException(type(self), description)

        (
            team,
            number,
            scorer_name,
            shot_type,
            zone,
            distance_to_net
        ) = match.groups()

        scorer_id = find_player_id_in_row(scorer_name, team, row)
        primary_assist_player_id = None
        secondary_assist_player_id = None
        if "Assist" in description:
            assists_start_idx = description.rfind(":")
            if assists_start_idx == -1:
                raise ValueError(f"GOAL description {description} didn't fit the expected format")
            for i, assist in enumerate(description[assists_start_idx:].split(";")):
                matches = re.match(self.assisting_player_regex, assist.strip())
                if matches is None:
                    raise ValueError(f"GOAL description {description} didn't fit the expected format")
                (_, _, assist_name) = matches.groups()
                assisting_player_id = find_player_id_in_row(assist_name, team, row)
                if i == 0:
                    primary_assist_player_id = int(assisting_player_id)
                else:
                    secondary_assist_player_id = int(assisting_player_id)

        return GoalSpecificAttributes(
            scorer_id,
            primary_assist_player_id,
            secondary_assist_player_id,
            shot_type,
            Zone[zone],
            float(distance_to_net)
        )


def parser_factory(short_event_name:str) -> Callable:
    if short_event_name == "SHOT":
        return ParserSHOT()
    elif short_event_name == "FAC":
        return ParserFAC()
    

    raise ValueError(f"{short_event_name} has no known parsers")
    
    