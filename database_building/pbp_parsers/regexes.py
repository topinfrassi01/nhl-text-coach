class RegexParserException(Exception):
    def __init__(self, type:type, description:str):
        super().__init__(f"Parser {str(type)} couldn't parse {description}")

#players can be identified as:
# - NSH #90 O'REILLY
# - TBL ONGOAL - #43 RADDYSH
# - NSH\xa0TAKEAWAY - #27 MCDONAGH
# - TBL #86 KUCHEROV(1), Slap , Off. Zone, 42 ft.Assists: #77 HEDMAN(1); #21 POINT(1)
# \xa0 should be matched with \s
PLAYER_IDENTIFICATION_REGEX = r"([A-Z]{3}|)\s?[\s\w-]*#([0-9]{1,2})\s([\w \.\-']*)"
#PLAYER_DATA_REGEX = re.compile(r"([A-Z]{3}|)(?: |)(#[0-9]{1,2}) ([\w\-']*)")
TEAM_IDENTIFICATION_REGEX = r"[A-Z\.]{3}"
ZONE_REGEX = r"(Neu|Off|Def)\. Zone"
PERIOD_START_REGEX = r"Period Start- Local time: ([0-9]{1,2}:[0-9]{2}) ([A-Z]{3})"
SHOT_REGEX = r"([\w\-\s,]*[[\w\-])"