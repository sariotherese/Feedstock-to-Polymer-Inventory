import unittest
from collections import defaultdict
from datetime import date, datetime, timedelta

from plant_data import ASSETS, BASE_FEED, MATERIALS, MEASURES, SCHEMAS, YIELDS, generate


class PlantDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.end = date(2026, 11, 23)
        cls.tables = generate(cls.end)
        cls.facts = cls.tables["fact_plant_data"]
        cls.days = [r[0] for r in cls.tables["dim_date"]]

    def test_exact_shape_referential_integrity_and_reproducibility(self):
        self.assertEqual(self.tables, generate(self.end))
        self.assertEqual(set(self.tables), set(SCHEMAS))
        self.assertEqual(len(self.facts), 2550)
        self.assertEqual(len({r[:5] for r in self.facts}), 2550)
        self.assertEqual([len(self.tables[n]) for n in
                          ["dim_date", "dim_shift", "dim_asset", "dim_material", "dim_measure"]],
                         [30, 3, 9, 12, 8])
        keys = [set(self.days), {"A", "B", "C"}, {r[0] for r in ASSETS},
                {r[0] for r in MATERIALS}, {r[0] for r in MEASURES}]
        for row in self.facts:
            for value, dimension in zip(row[:5], keys):
                self.assertIn(value, dimension)
            self.assertGreaterEqual(row[5], 0)
            if row[4] == "STOCK_BOOK":
                self.assertEqual(row[1], "C")
            expected_date = datetime.strptime(str(row[0]), "%Y%m%d").date()
            if row[1] == "C":
                expected_date += timedelta(days=1)
            self.assertEqual(row[6].date(), expected_date)

    def test_feed_and_exact_anomaly_magnitudes(self):
        totals = defaultdict(lambda: defaultdict(float))
        for day, shift, asset, material, measure, value, stamp in self.facts:
            totals[day][measure] += value
            if measure == "FEED":
                self.assertLessEqual(abs(value / BASE_FEED[material] - 1), 0.0300001)
            if measure == "PURITY":
                lo, hi = (93.7, 94.3) if day in self.days[24:26] else (97.5, 99)
                self.assertTrue(lo <= value <= hi)
        for index, day in enumerate(self.days):
            gap = (totals[day]["FEED"] - totals[day]["OUTPUT"]) / totals[day]["FEED"]
            self.assertAlmostEqual(gap, 0.03 if index == 26 else 0.0, places=12)
            for shift in "ABC":
                rows = [r for r in self.facts if r[0] == day and r[1] == shift]
                feeds = {r[3]: r[5] for r in rows if r[4] == "FEED"}
                ethylene = next(r[5] for r in rows if r[4] == "OUTPUT" and r[3] == "ETHYLENE")
                expected = sum(feeds[m] * YIELDS[m][0] for m in feeds)
                if index in (24, 25):
                    expected -= feeds["ETHANE"] * 0.78 * 0.04
                self.assertAlmostEqual(ethylene, expected)

    def test_tank_refill_bounds_and_book_discrepancy(self):
        by_shift = defaultdict(dict)
        for day, shift, tank, material, measure, value, stamp in self.facts:
            if measure == "STOCK_SENSOR":
                maximum = next(a[5] for a in ASSETS if a[0] == tank)
                self.assertLessEqual(value, maximum)
                by_shift[(day, shift)][tank] = value
            if measure == "STOCK_BOOK":
                sensor = next(r[5] for r in self.facts
                              if r[:4] == (day, shift, tank, material) and r[4] == "STOCK_SENSOR")
                if day == self.days[27] and material == "ETHANE":
                    self.assertAlmostEqual(value / sensor, 1.03)
                else:
                    self.assertLessEqual(abs(value / sensor - 1), 0.0050001)
        totals = [60000] + [v["T-ETH-01"] + v["T-ETH-02"] for v in by_shift.values()]
        increases = [b - a for a, b in zip(totals, totals[1:]) if b > a]
        self.assertEqual(len(increases), 1)
        self.assertTrue(49000 < increases[0] < 50000)

    def test_finished_goods_conservation_and_polymer_conversion(self):
        previous = {}
        for day in self.days:
            for shift in "ABC":
                rows = [r for r in self.facts if r[0] == day and r[1] == shift]
                outputs = {r[3]: r[5] for r in rows if r[4] == "OUTPUT"}
                production = {r[3]: r[5] for r in rows if r[4] == "PRODUCTION"}
                self.assertAlmostEqual(sum(v for g, v in production.items() if not g.startswith("PP")),
                                       outputs["ETHYLENE"] * 0.97)
                self.assertAlmostEqual(production["PP-IM"] + production["PP-RA"],
                                       outputs["PROPYLENE"] * 0.97)
                for grade, tons in production.items():
                    shipped = next(r[5] for r in rows if r[3] == grade and r[4] == "SHIPPED")
                    stock = next(r[5] for r in rows if r[3] == grade and r[4] == "FG_STOCK")
                    self.assertTrue(0.95 * tons <= shipped <= tons)
                    if grade in previous:
                        self.assertAlmostEqual(stock, previous[grade] + tons - shipped)
                    previous[grade] = stock


if __name__ == "__main__":
    unittest.main()
