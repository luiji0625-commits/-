#!/usr/bin/env python3
"""スクリーニング計算の回帰テスト: python3 scripts/test_pipeline.py"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from screen_offers import DEFAULT_CONFIG, evaluate, expected_recurring_months


def offer(**overrides):
    row = {
        "asp": "A8.net", "merchant": "X", "program_id": "1", "program_name": "P",
        "category": "SaaS", "customer_price_monthly": "3000", "initial_reward_yen": "1000",
        "recurring_reward_monthly_yen": "900", "recurring_cap_months": "0",
        "approval_rate": "0.8", "churn_monthly": "0.05", "churn_source": "own_cohort",
        "landing_url": "", "notes": "",
    }
    row.update({k: str(v) for k, v in overrides.items()})
    return row


class TestExpectedMonths(unittest.TestCase):
    def test_geometric_survival(self):
        # 解約率10%・2ヶ月なら 0.9 + 0.81 = 1.71
        self.assertAlmostEqual(expected_recurring_months(0.10, 2), 1.71, places=6)

    def test_zero_churn_equals_horizon(self):
        self.assertEqual(expected_recurring_months(0.0, 24), 24.0)

    def test_full_churn_yields_nothing(self):
        self.assertEqual(expected_recurring_months(1.0, 24), 0.0)

    def test_capped_by_horizon_not_divergent(self):
        # 無期限案件でも評価期間を超えて積み上がらない
        self.assertLess(expected_recurring_months(0.01, 24), 24.0)


class TestEvaluate(unittest.TestCase):
    def test_pass(self):
        r = evaluate(offer(), DEFAULT_CONFIG)
        self.assertEqual(r["verdict"], "PASS")
        self.assertGreaterEqual(r["ltv_yen"], DEFAULT_CONFIG["ltv_floor_yen"])

    def test_recurring_cap_shortens_horizon(self):
        r = evaluate(offer(recurring_cap_months=3), DEFAULT_CONFIG)
        self.assertEqual(r["evaluated_horizon"], 3)
        self.assertEqual(r["verdict"], "FAIL")

    def test_churn_ceiling(self):
        r = evaluate(offer(churn_monthly=0.20, recurring_reward_monthly_yen=5000), DEFAULT_CONFIG)
        self.assertEqual(r["verdict"], "FAIL")
        self.assertIn("解約率", r["reasons"])

    def test_single_shot_offer_rejected(self):
        r = evaluate(offer(recurring_reward_monthly_yen=0, initial_reward_yen=20000), DEFAULT_CONFIG)
        self.assertEqual(r["verdict"], "FAIL")
        self.assertIn("継続報酬なし", r["reasons"])

    def test_low_confidence_margin_flips_verdict(self):
        # 同じ数字でも解約率の出所が推定ならマージンで落ちる
        numbers = dict(recurring_reward_monthly_yen=1000, churn_monthly=0.11, approval_rate=0.78)
        measured = evaluate(offer(churn_source="own_cohort", **numbers), DEFAULT_CONFIG)
        estimated = evaluate(offer(churn_source="category_proxy", **numbers), DEFAULT_CONFIG)
        self.assertEqual(measured["ltv_yen"], estimated["ltv_yen"])
        self.assertEqual(measured["verdict"], "PASS")
        self.assertEqual(estimated["verdict"], "FAIL")
        self.assertEqual(estimated["verdict_raw"], "PASS")

    def test_approval_rate_guard(self):
        r = evaluate(offer(approval_rate=0.4, recurring_reward_monthly_yen=5000), DEFAULT_CONFIG)
        self.assertIn("承認率", r["reasons"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
