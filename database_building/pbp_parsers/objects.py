# import re
# from collections import namedtuple
# from datetime import datetime
# from typing import Generic, Optional, TypeVar, get_type_hints
# import attrs
# from attrs import define, field, fields, validators, make_class
# from .regexes import TEAM_IDENTIFICATION_REGEX, RegexParserException
# import enum


# @define(frozen=True)
# class Game:
#     game_id: int
#     starting_date: datetime
#     timezone: str
#     home_team_abbrev: str
#     away_team_abbrev: str
#     final_score: tuple[int, int]
#     ended_in_ot: bool
#     ended_in_shootout: bool

# @define(frozen=True)
# class Event:
#     game_id: int
#     period: int = field(validator=[validators.gt(0), validators.lt(6)])
#     time_elapsed:int # in seconds
#     location: Optional[tuple[float, float]] #xC,yC
#     home_goalie_id: int
#     away_goalie_id: int

# TEAM_ABBREV_EQUIVALENCES:dict[str,str] = {
#     "T.B":"TBL",
#     "L.A":"LAK"
# }


# ALLOWED_SHOT_TYPES = [
#     'Wrap-around',
#     'Poke',
#     'Snap,'
#     'Backhand',
#     'Wrist',
#     'Deflected',
#     'Snap',
#     'Bat',
#     'Cradle',
#     'Between Legs',
#     'Tip-In',
#     'Slap'
# ]

# class Zone(enum.Enum):
#     Def = "Defensive"
#     Off = "Offensive"
#     Neu = "Neutral"

# TEvent = TypeVar("TEvent")
# class EventSpecificAttributes(Generic[TEvent]):
#     pass


# def make_specific_attrs_class(base_cls: type, subclass: type) -> type:
#     base_fields = set(get_type_hints(base_cls))
#     subclass_hints = get_type_hints(subclass)

#     specific_fields = {
#         name: attrs.field(type=typ)
#         for name, typ in subclass_hints.items()
#         if name not in base_fields
#     }

#     return attrs.make_class(
#         f"{subclass.__name__}SpecificAttributes",
#         specific_fields,
#         bases=(EventSpecificAttributes["Faceoff"],)
#     )


# @define(frozen=True)
# class Faceoff(Event):
#     winning_team_abbrev: str
#     zone: Zone
#     winning_player_id: int
#     loosing_player_id: int 

# FaceoffSpecificAttributes = make_specific_attrs_class(Event, Faceoff)


# @define(frozen=True)
# class Shot(Event):
#     player_id: int
#     type: str = field(validator=[validators.in_(ALLOWED_SHOT_TYPES)])
#     zone: Zone
#     distance_to_net: float = field(validator=[validators.ge(0.0)])
#     is_defensive_deflection: bool
#     is_penalty_shot: bool


# ShotSpecificAttributes = make_specific_attrs_class(Event, Shot)

# @define(frozen=True)
# class Hit(Event):
#     hitting_player_id: int
#     receiving_player_id: int
#     zone: Zone

# HitSpecificAttributes = make_specific_attrs_class(Event, Shot)

# @define(frozen=True)
# class Stop(Event):
#     reason: str
# StopSpecificAttributes = make_specific_attrs_class(Event, Stop)

# @define(frozen=True)
# class BlockedShot(Event):
#     shooting_player_id: int
#     blocking_player_id: Optional[int]
#     shot_type: str = field(validator=[validators.in_(ALLOWED_SHOT_TYPES)])
#     zone: Zone
#     is_blocked_by_teammate: bool
#     is_a_flub: bool # if it's a flub why does it count as a block?
#     is_a_broken_stick: bool # who has the broken stick??
# BlockedShotSpecificAttributes = make_specific_attrs_class(Event, BlockedShot)

# @define(frozen=True)
# class MissedShot(Event):
#     shooting_player_id: int
#     shot_type: Optional[str] = field(validator=[validators.in_(ALLOWED_SHOT_TYPES)])
#     direction: Optional[str]
#     zone: Optional[Zone]
#     distane_to_net: Optional[float] = field(validator=[validators.ge(0.0)])
#     is_a_flub: bool
#     is_a_broken_stick: bool
#     is_a_failed_attempt: bool
# MissedShotSpecificAttributes = make_specific_attrs_class(Event, MissedShot)

# @define(frozen=True)
# class Giveaway(Event):
#     player_id: int
#     zone: Zone
# GiveawaySpecificAttributes = make_specific_attrs_class(Event, Giveaway)

# @define(frozen=True)
# class Takeaway(Event):
#     player_id: int
#     zone: Zone
# TakeawaySpecificAttributes = make_specific_attrs_class(Event, Takeaway)

# # @define(frozen=True)
# # class Penalty(Event):
# #     responsible_player_id: Optional[int]
# #     type: str
# #     duration: int
# #     zone: Zone
# #     served_by_player_id: Optional[int]
# #     drawn_by_player_id: Optional[int]
# #     penalized_team: 
# # PenaltySpecificAttributes = make_specific_attrs_class(Event, Penalty)

# @define(frozen=True)
# class Goal(Event):
#     player_id: int
#     primary_assist_id: Optional[int]
#     secondary_assist_id: Optional[int]
#     shot_type: str = field(validator=[validators.in_(ALLOWED_SHOT_TYPES)])
#     zone: Zone
#     distance_to_net: float = field(validator=[validators.ge(0.0)])
# GoalSpecificAttributes = make_specific_attrs_class(Event, Goal)