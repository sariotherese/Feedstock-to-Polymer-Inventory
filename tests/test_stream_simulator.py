import unittest
from unittest.mock import patch

from stream_simulator import simulate


class StreamTests(unittest.TestCase):
    def test_four_tanks_per_minute_and_opt_in_temperature_anomaly(self):
        levels = {"T-ETH-01": 35000.0, "T-ETH-02": 25000.0,
                  "T-PRO-01": 20000.0, "T-NAP-01": 30000.0}
        with patch("stream_simulator.send_reading") as send, patch("stream_simulator.time.sleep"):
            self.assertEqual(simulate({}, levels.copy(), minutes=4), 16)
            rows = [c.args[1] for c in send.call_args_list]
        self.assertEqual({r["tank_id"] for r in rows}, set(levels))
        for tank in levels:
            readings = [r for r in rows if r["tank_id"] == tank]
            self.assertEqual(len(readings), 4)
            self.assertEqual(readings[0]["level_tons"], levels[tank])
            self.assertLess(readings[-1]["level_tons"], readings[0]["level_tons"])
            if tank.startswith("T-ETH"):
                self.assertTrue(all(-89.5 <= r["temperature_c"] <= -88.5 for r in readings))
        with patch("stream_simulator.send_reading") as send, patch("stream_simulator.time.sleep"):
            simulate({}, levels.copy(), minutes=4, inject_temperature_alert=True)
            anomaly = [c.args[1] for c in send.call_args_list
                       if c.args[1]["tank_id"] == "T-ETH-01"][-1]
            self.assertGreater(anomaly["temperature_c"], -85)

    def test_invalid_duration_fails_explicitly(self):
        with self.assertRaises(ValueError):
            simulate({}, {}, minutes=0)


if __name__ == "__main__":
    unittest.main()
