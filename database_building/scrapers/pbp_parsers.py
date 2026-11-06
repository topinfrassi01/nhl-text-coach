from abc import ABC, abstractmethod
from traceback import print_exception
import re
from typing import Generic, TypeVar, Callable
import jsonschema
from attrs import asdict, fields
import pandas as pd
import numpy as np
from pandas import Series

from objects import *


def time_to_seconds(time:str) -> int:
    (minutes, seconds) = time.split(":")
    return int(minutes) * 60 + int(seconds)


class EventParser(ABC):
    event_type: type[Event]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        event_cls = cls.__dict__.get("event_type")

        if event_cls is None:
            raise TypeError(f"{cls.__name__} must define event_type")

        if not isinstance(event_cls, type) or not issubclass(event_cls, Event):
            raise TypeError(f"{cls.__name__}.event_type must be an Event subclass")

    def __call__(self, game_id:int, data:dict) -> Optional[Event]:
        base_event = self._parse_common_data(game_id, data)
        specific_event_data = self._parse_specific_data(data)

        return self.event_type(**asdict(base_event), **specific_event_data)

    def _parse_common_data(self, game_id:int, data:dict) -> Event:
        if "xCoord" not in data.get("details", {}):
            location = None
        else:
            location = (float(data["details"]["xCoord"]), float(data["details"]["yCoord"]))

        return Event(
            game_id,
            data["periodDescriptor"]["number"],
            time_to_seconds(data["timeInPeriod"]),
            data.get("homeTeamDefendingSide", None),
            location
        )

    @abstractmethod
    def _parse_specific_data(self, data:dict) -> dict:
        pass


class ParserFaceoff(EventParser):
    """
    """
    event_type = Faceoff

    def _parse_specific_data(self, data:dict) -> dict:
        event_details = data["details"]
        
        return {
            "winningTeamId": event_details["eventOwnerTeamId"],
            "winningPlayerId": event_details["winningPlayerId"],
            "losingPlayerId": event_details["losingPlayerId"],
            "zone": Zone[event_details["zoneCode"]]
        }

class ParserShot(EventParser):
    event_type = Shot
    def _parse_specific_data(self, data:dict) -> dict:
        event_details = data["details"]
        return {
            "shooter_id": event_details["shootingPlayerId"],
            "shooter_team_id": event_details["eventOwnerTeamId"],
            "goaltender_id": event_details["goalieInNetId"],
            "type": event_details["shotType"],
            "zone": Zone[event_details["zoneCode"]]
        }


class ParserHit(EventParser):
    event_type = Hit
    def _parse_specific_data(self, data:dict) -> dict:
        event_details = data["details"]
        return {
            "hitting_player_id": event_details["hittingPlayerId"],
            "hitting_player_team_id":event_details["eventOwnerTeamId"],
            "receiving_player_id":event_details["hitteePlayerId"],
            "zone": Zone[event_details["zoneCode"]]
        }


class ParserStop(EventParser):
    event_type = Stop
    def _parse_specific_data(self, data:dict) -> dict:
        event_details = data["details"]
        return {
            "reason": event_details["reason"]
        }


class ParserBlockedShot(EventParser):
    event_type = BlockedShot
    def _parse_specific_data(self, data: dict) -> dict:
        event_details = data["details"]
        reason = event_details.get("reason", None)
        return {
            "shooting_player_id": event_details["shootingPlayerId"],
            "shooting_player_team_id": event_details["eventOwnerTeamId"],
            "blocking_player_id": event_details.get("blockingPlayerId", None),
            "zone": Zone[event_details["zoneCode"]] if "zoneCode" in event_details else None,
            "blocked_by_teammate" : reason == "teammate-blocked",
            "blocked_by_other" : reason == "other-blocked",
            "reason": reason
        }

class ParserFailedShotAttempt(EventParser):
    event_type = FailedShotAttempt
    def _parse_specific_data(self, data: dict) -> dict:
        event_details = data["details"]
        return {
            "shooting_player_id": event_details["shootingPlayerId"],
            "shooting_player_team_id": event_details["eventOwnerTeamId"],
            "goaltender_id": event_details["goalieInNetId"],
            "zone": Zone[event_details["zoneCode"]]
        }


class ParserGiveaway(EventParser):
    event_type = Giveaway
    def _parse_specific_data(self, data: dict) -> dict:
        event_details = data["details"]
        return {
            "player_id": event_details["playerId"],
            "zone": Zone[event_details["zoneCode"]]
        }


class ParserTakeaway(EventParser):
    event_type = Takeaway
    def _parse_specific_data(self, data: dict) -> dict:
        event_details = data["details"]
        return {
            "player_id": event_details["playerId"],
            "zone": Zone[event_details["zoneCode"]]
        }


class ParserGoal(EventParser):
    event_type = Goal
    def _parse_specific_data(self, data: dict) -> dict:
        event_details = data["details"]
        return {
            "player_id": event_details["scoringPlayerId"],
            "player_team_id": event_details["eventOwnerTeamId"],
            "primary_assist_id": event_details.get("assist1PlayerId", None),
            "secondary_assist_id": event_details.get("assist2PlayerId", None),
            "shot_type": event_details.get("shotType", None),
            "zone": Zone[event_details["zoneCode"]]
        }

class ParserMissedShot(EventParser):
    event_type = MissedShot
    def _parse_specific_data(self, data: dict) -> dict:
        event_details = data["details"]
        return {
            "shooting_player_id": event_details["shootingPlayerId"],
            "shooting_player_team_id": event_details["eventOwnerTeamId"],
            "shot_type": event_details["shotType"],
            "zone": Zone[event_details["zoneCode"]],
            "reason": event_details["reason"]
        }


class ParserPenalty(EventParser):
    event_type = Penalty
    def _parse_specific_data(self, data: dict) -> dict:
        event_details = data["details"]
        return {
            "team_id": event_details["eventOwnerTeamId"],
            "description": event_details["descKey"],
            "type": event_details["typeCode"],
            "committed_by_player_id": event_details.get("committedByPlayerId", None),
            "drawn_by_player_id": event_details.get("drawnByPlayerId", None),
            "served_by_player_id": event_details.get("servedByPlayerId", None),
            "duration": int(event_details["duration"]),
            "zone": Zone[event_details["zoneCode"]] if "zoneCode" in event_details else None
        }

def parse_event(game_id: int, data:dict) -> Optional[Event]:
    event_type = data["typeDescKey"]

    if event_type == "blocked-shot":
        parser = ParserBlockedShot()
    elif event_type == "faceoff":
        parser = ParserFaceoff()
    elif event_type == "failed-shot-attempt":
        parser = ParserFailedShotAttempt()
    elif event_type == "giveaway":
        parser = ParserGiveaway()
    elif event_type == "takeaway":
        parser = ParserTakeaway()
    elif event_type == "goal":
        parser = ParserGoal()
    elif event_type == "hit":
        parser = ParserHit()
    elif event_type == "missed-shot":
        parser = ParserMissedShot()
    elif event_type == "penalty":
        parser = ParserPenalty()
    elif event_type == "shot-on-goal":
        parser = ParserShot()
    elif event_type == "stoppage":
        parser = ParserStop()
    else:
        return None

    return parser(game_id, data)