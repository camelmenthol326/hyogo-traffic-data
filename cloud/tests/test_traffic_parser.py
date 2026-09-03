import unittest

from cloud.traffic_parser import DISTRICTS, normalize_text, parse_traffic_plan
from cloud.update_data import date_parts_from_url, find_pdf_urls


SAMPLE_TEXT = """
日 曜 地区 取締り重点路線 取締り内容
    神戸 県道神戸三田線 交差点関連
    阪神 国道１７６号 速度
    東播 国道１７５号 速度
3 木 西播 国道２９号 速度
    但馬 国道９号 交差点関連
    淡路 国道２８号 速度
    高速 山陽自動車道 速度
"""


class TrafficParserTests(unittest.TestCase):
    def test_normalizes_full_width_characters_and_spaces(self):
        self.assertEqual(normalize_text(" 国道　１７６号  "), "国道 176号")

    def test_applies_day_to_all_seven_district_rows(self):
        plans = parse_traffic_plan(SAMPLE_TEXT, 2026, 9)

        self.assertEqual(len(plans), 7)
        self.assertEqual(tuple(plan.district for plan in plans), DISTRICTS)
        self.assertTrue(all(plan.date == "2026-09-03" for plan in plans))
        self.assertEqual(plans[1].route, "国道176号")

    def test_rejects_incomplete_daily_group(self):
        with self.assertRaises(ValueError):
            parse_traffic_plan("3 木 西播 国道29号 速度", 2026, 9)

    def test_finds_and_resolves_official_pdf_links(self):
        html = '<a href="data/20260901.pdf">計画</a>'
        self.assertEqual(
            find_pdf_urls(html),
            ["https://www.police.pref.hyogo.lg.jp/traffic/violation/jyouho/data/20260901.pdf"],
        )

    def test_reads_year_and_month_from_pdf_url(self):
        self.assertEqual(date_parts_from_url("https://example.com/20260901.pdf"), (2026, 9))


if __name__ == "__main__":
    unittest.main()
