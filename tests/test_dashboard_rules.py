"""Focused tests for the dashboard's journey-SLI requirement."""

import unittest

from dashboard_rules import has_journey_ratio


NAMESPACE = "SignalForge/Test"
DEPLOYMENT = "signalforge-test"


def dashboard(expression, *, service="canary", stat="Sum", deployment=DEPLOYMENT):
    metrics = [
        [NAMESPACE, "JourneyGood", "Deployment", deployment, "Service", service,
         {"id": "m_canary_good", "stat": stat, "visible": False}],
        [NAMESPACE, "JourneyTotal", "Deployment", deployment, "Service", service,
         {"id": "m_canary_total", "stat": stat, "visible": False}],
        [{"expression": expression, "id": "sli"}],
    ]
    return {"widgets": [{"type": "metric", "properties": {"metrics": metrics}}]}


class JourneyRatioTests(unittest.TestCase):
    def test_valid_formula_variants(self):
        for formula in (
            "m_canary_good/m_canary_total",
            "100 * (m_canary_good / m_canary_total)",
            "IF(m_canary_total,100*m_canary_good/m_canary_total,0)",
        ):
            with self.subTest(formula=formula):
                self.assertTrue(has_journey_ratio(dashboard(formula), NAMESPACE, DEPLOYMENT))

    def test_short_metric_ids(self):
        body = dashboard("g/t")
        metrics = body["widgets"][0]["properties"]["metrics"]
        metrics[0][-1]["id"] = "g"
        metrics[1][-1]["id"] = "t"
        self.assertTrue(has_journey_ratio(body, NAMESPACE, DEPLOYMENT))

    def test_rejects_unrelated_formula(self):
        self.assertFalse(has_journey_ratio(dashboard("m_canary_total/m_canary_good"), NAMESPACE, DEPLOYMENT))

    def test_rejects_wrong_series(self):
        for change in ({"service": "api"}, {"stat": "Average"}, {"deployment": "other"}):
            with self.subTest(change=change):
                self.assertFalse(has_journey_ratio(dashboard("m_canary_good/m_canary_total", **change),
                                                   NAMESPACE, DEPLOYMENT))

    def test_rejects_text_only_claim(self):
        body = dashboard("m_canary_good+m_canary_total")
        body["widgets"].append({"type": "text", "properties": {"markdown": "JourneyGood / JourneyTotal"}})
        self.assertFalse(has_journey_ratio(body, NAMESPACE, DEPLOYMENT))


if __name__ == "__main__":
    unittest.main()
