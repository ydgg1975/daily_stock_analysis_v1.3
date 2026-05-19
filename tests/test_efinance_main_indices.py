import os
import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_provider.efinance_fetcher import EfinanceFetcher


class TestEfinanceMainIndices(unittest.TestCase):
    def test_get_main_indices_prefers_jinkai_column_for_open_price(self):
        fetcher = EfinanceFetcher()
        fake_df = pd.DataFrame(
            {
                "gupiaodaima": ["000001"],
                "zuixinjia": [3200.0],
                "zhangdiefu": [0.63],
                "zhangdiee": [20.0],
                "jinkai": [3188.0],
                "kaipan": [0.0],
                "zuigao": [3215.0],
                "zuidi": [3170.0],
                "chengjiaoliang": [123456789],
                "chengjiaoe": [9876543210.0],
                "zhenfu": [1.2],
            }
        )
        fake_efinance = types.SimpleNamespace(
            stock=types.SimpleNamespace(get_realtime_quotes=lambda *args, **kwargs: fake_df)
        )

        with patch.dict(sys.modules, {"efinance": fake_efinance}):
            with patch.object(fetcher, "_set_random_user_agent", return_value=None), patch.object(
                fetcher, "_enforce_rate_limit", return_value=None
            ):
                data = fetcher.get_main_indices(region="cn")

        self.assertIsNotNone(data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["code"], "sh000001")
        self.assertEqual(data[0]["name"], "shangzhengzhishu")
        self.assertAlmostEqual(data[0]["open"], 3188.0)
        self.assertAlmostEqual(data[0]["current"], 3200.0)

    def test_get_main_indices_falls_back_to_kaipan_when_jinkai_is_missing(self):
        fetcher = EfinanceFetcher()
        fake_df = pd.DataFrame(
            {
                "gupiaodaima": ["000001"],
                "zuixinjia": [3200.0],
                "zhangdiefu": [0.63],
                "zhangdiee": [20.0],
                "jinkai": [""],
                "kaipan": [3186.0],
                "zuigao": [3215.0],
                "zuidi": [3170.0],
                "chengjiaoliang": [123456789],
                "chengjiaoe": [9876543210.0],
                "zhenfu": [1.2],
            }
        )
        fake_efinance = types.SimpleNamespace(
            stock=types.SimpleNamespace(get_realtime_quotes=lambda *args, **kwargs: fake_df)
        )

        with patch.dict(sys.modules, {"efinance": fake_efinance}):
            with patch.object(fetcher, "_set_random_user_agent", return_value=None), patch.object(
                fetcher, "_enforce_rate_limit", return_value=None
            ):
                data = fetcher.get_main_indices(region="cn")

        self.assertIsNotNone(data)
        self.assertEqual(len(data), 1)
        self.assertAlmostEqual(data[0]["open"], 3186.0)


if __name__ == "__main__":
    unittest.main()
