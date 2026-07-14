import unittest

import pandas as pd

from models.consumo_actores import build_outputs, hourly_wide_to_long as demand_to_long
from models.precio_bolsa_model import hourly_wide_to_long as price_to_long
from models.precio_bolsa_model import validate_hourly_dataset


class PipelineTests(unittest.TestCase):
    def test_price_wide_to_long_orders_hours(self):
        raw = pd.DataFrame({"Date": ["2026-01-01"], "Values_Hour02": [20], "Values_Hour01": [10]})
        result = price_to_long(raw)
        self.assertEqual(result["precio_bolsa_cop_kwh"].tolist(), [10, 20])
        self.assertEqual(result.datetime.dt.hour.tolist(), [0, 1])

    def test_quality_detects_missing_hour(self):
        data = pd.DataFrame({
            "datetime": pd.to_datetime(["2026-01-01 00:00", "2026-01-01 02:00"]),
            "precio_bolsa_cop_kwh": [100.0, 120.0],
        })
        result = validate_hourly_dataset(data)
        self.assertEqual(result["missing_hours"], 1)
        self.assertEqual(result["duplicated_timestamps"], 0)

    def test_demand_mart_has_market_share(self):
        raw = pd.DataFrame({"Date": ["2026-01-01", "2026-01-01"], "Values_code": ["A", "B"], "Values_Hour01": [75, 25]})
        demand = demand_to_long(raw)
        agents = pd.DataFrame({"agent_code": ["A", "B"], "agent_name": ["Alpha", "Beta"]})
        ranking = build_outputs(demand, agents, 2)["top_consumidores"]
        self.assertAlmostEqual(ranking.share_percent.sum(), 100.0)
        self.assertEqual(ranking.iloc[0].agent_code, "A")


if __name__ == "__main__":
    unittest.main()
