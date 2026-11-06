from pathlib import Path
import pandas as pd
import unittest

from pbp_parsers import ParserFAC, ParserSHOT, find_player_id_in_row

class TestParser(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.test_root = Path(__file__).parent / "test_data"

    def test__find_player_id_in_row__player_found(self):
        row = pd.read_csv(self.test_root / "test_data_for_find_player_id_in_row.csv").iloc[0]

        player_id = find_player_id_in_row("FORSBERG", "NSH", row)
        self.assertEqual(player_id, 8476887)


    def test_faceoff_parser(self):
        row = pd.read_csv(self.test_root / "test_data_for_fac_event_parser.csv").iloc[0]

        faceoff = ParserFAC()(row)



    def test_shot_parser(self):
        row = pd.read_csv(self.test_root / "test_data_for_shot_event_parser.csv").iloc[0]
        shot = ParserSHOT()(row)

        
