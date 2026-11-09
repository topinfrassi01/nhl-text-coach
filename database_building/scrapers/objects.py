from typing import Optional
import attrs
import attrs.validators as validators
from attrs import field
from datetime import datetime
import enum


class Zone(enum.Enum):
    D = "Defensive"
    O = "Offensive"
    N = "Neutral"


class Position(enum.Enum):
    G = "Goaltender"
    F = "Forward"
    D = "Defenseman"


@attrs.define(frozen=True)
class Team():
    id: int
    fullName: str
    triCode: str


@attrs.define(frozen=True)
class Event:
    game_id: int
    period: int
    time_elapsed:int # in seconds
    home_team_defending_side: Optional[str]
    location: Optional[tuple[float, float]] #xC,yC

@attrs.define(frozen=True)
class Game:
    id: int
    date: datetime
    homeTeamId: int
    awayTeamId: int
    homeTeamScore: int
    awayTeamScore: int
    endedInOvertime: bool
    endedInShootout: bool
    play_by_play: list[Event]


@attrs.define(frozen=True)
class Schedule:
    team_id: int
    season: int
    games:list[Game]


@attrs.define(frozen=True)
class PlayerIdentifiers:
    id: int
    first_name: str
    last_name: str
    number: Optional[int]


@attrs.define(frozen=True)
class Roster:
    team_id: int
    players: list[PlayerIdentifiers]


@attrs.define(frozen=True)
class Player:
    id: int
    current_team_id: int
    first_name: str
    last_name: str
    position: Position
    number: int # Note that players can change numbers, I don't know how it's dealt with.
    birth_date: datetime
    shoots_catches: str = field(validator=validators.in_(["L", "R"]))
    draft_year:int


@attrs.define(frozen=True)
class PlayerSeason:
    season_year: int
    league: str
    team_id: Optional[int] # defined only for nhl teams
    team_abbrev: str
    assists: int
    goals: int
    games_played: int


@attrs.define(frozen=True)
class SkaterSeason(PlayerSeason):
    faceoffWinningPctg: float
    avgToi: float
    pim: int
    plusMinus: int
    powerPlayGoals: int
    powerPlayPoints: int
    gameWinningGoals: int
    otGoals: int
    shootingPctg: int
    shorthandedGoals: int
    shortHandedPoints: int
    shots: int

    @property
    def points(self):
        return self.goals + self.assists


@attrs.define(frozen=True)
class GoaltenderSeason(PlayerSeason):
    goalsAgainst: int
    goalsAgainstAvg: float
    wins: int
    losses: int
    otLosses: int
    gamesStarted: int
    shotsAgainst: int
    timeOnIce: float


@attrs.define(frozen=True)
class Skater(Player):
    seasonTotals: dict[int, SkaterSeason]

@attrs.define(frozen=True)
class Goaltender(Player):
    seasonTotals: dict[int, GoaltenderSeason]

@attrs.define(frozen=True)
class Faceoff(Event):
    winningTeamId: str
    winningPlayerId: int
    losingPlayerId: int 
    zone: Optional[Zone]


@attrs.define(frozen=True)
class Shot(Event):
    shooter_id: int
    shooter_team_id: int
    goaltender_id: Optional[int]
    type: Optional[str]
    zone: Optional[Zone]


@attrs.define(frozen=True)
class Hit(Event):
    hitting_player_id: int
    hitting_player_team_id: int
    receiving_player_id: int
    zone: Optional[Zone]


@attrs.define(frozen=True)
class Stop(Event):
    reason: Optional[str]


@attrs.define(frozen=True)
class BlockedShot(Event):
    """ reason seems to be available after 2022... """
    shooting_player_id: int
    shooting_player_team_id: int
    blocking_player_id: Optional[int]
    zone: Optional[Zone]
    blocked_by_teammate: Optional[bool]
    blocked_by_other: Optional[bool]
    reason: Optional[str]



@attrs.define(frozen=True)
class FailedShotAttempt(Event):
    shooting_player_id: int
    shooting_player_team_id: int
    goaltender_id: Optional[int]
    zone: Optional[Zone]


@attrs.define(frozen=True)
class Giveaway(Event):
    player_id: int
    zone: Optional[Zone]


@attrs.define(frozen=True)
class Takeaway(Event):
    player_id: int
    zone: Optional[Zone]

@attrs.define(frozen=True)
class Goal(Event):
    player_id: int
    player_team_id: int
    primary_assist_id: Optional[int]
    secondary_assist_id: Optional[int]
    shot_type: Optional[str]
    zone: Optional[Zone]


@attrs.define(frozen=True)
class MissedShot(Event):
    shooting_player_id: int
    shooting_player_team_id: int
    shot_type: Optional[str]
    zone: Optional[Zone]
    reason: Optional[str]


@attrs.define(frozen=True)
class Penalty(Event):
    team_id: int
    description: str
    type: str
    committed_by_player_id: Optional[int]
    drawn_by_player_id: Optional[int]
    served_by_player_id: Optional[int]
    duration: int
    zone: Optional[Zone]

    @property
    def is_team_penalty(self) -> bool:
        return self.committed_by_player_id is None