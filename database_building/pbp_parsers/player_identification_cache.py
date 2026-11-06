import attrs

@attrs.define(frozen=True,hash=True)
class PrimaryPlayerIdentifier:
    name:str
    team:str
    number:int

@attrs.define(frozen=True,hash=True)
class SecondaryPlayerIdentifier:
    name:str
    team:str


class PlayerIdentificationCache:
    def __init__(self) -> None:
        self.primary_cache:dict[PrimaryPlayerIdentifier, int] = dict()
        self.secondary_cache:dict[SecondaryPlayerIdentifier, int] = dict()

    def add(self, player_id:int, name:str, team:str, number:int | None):
        if number is not None:
            primary_identifer = PrimaryPlayerIdentifier(name, team, number)
            if self.primary_cache.get(primary_identifer, player_id) != player_id:
                raise ValueError(f"Primary player identifiers {primary_identifer} lead to different player ids {player_id}, {self.primary_cache[primary_identifer]}")
            self.primary_cache[primary_identifer] = player_id

        secondary_identifer = SecondaryPlayerIdentifier(name, team)
        if self.secondary_cache.get(secondary_identifer, player_id) != player_id:
            raise ValueError(f"Secondary player identifiers {secondary_identifer} lead to different player ids {player_id}, {self.secondary_cache[secondary_identifer]}")

        self.secondary_cache[secondary_identifer] = player_id

    def search(self, name:str, team:str, number:int | None):
        player_id = None
        if number is not None:
            player_id = self.primary_cache.get(PrimaryPlayerIdentifier(name, team, number), None)

        if player_id is None:
            return self.secondary_cache.get(SecondaryPlayerIdentifier(name, team), None)


player_ids_cache = PlayerIdentificationCache()

