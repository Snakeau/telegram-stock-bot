import unittest

from chatbot.copilot.learning import compute_learning_metrics, auto_tune_settings


class TestCopilotLearning(unittest.TestCase):
    def test_compute_learning_metrics(self):
        logs = [
            {
                "ticker": "AAPL",
                "action": "BUY",
                "confidence": 0.8,
            },
            {
                "ticker": "MSFT",
                "action": "SELL",
                "confidence": 0.7,
            },
        ]
        outcomes = {
            "AAPL": {1: 2.0, 7: 3.0, 30: 3.0},
            "MSFT": {1: -2.0, 7: -4.0, 30: -4.0},
        }
        metrics = compute_learning_metrics(logs, outcomes)
        self.assertEqual(2, metrics["sample_size"])
        self.assertGreater(metrics["hit_rate"], 0.9)
        self.assertGreater(metrics["usefulness_score"], 0.5)

    def test_auto_tune_settings_increases_threshold_on_low_quality(self):
        settings = {
            "profiles": {
                "conservative": {"min_confidence": 0.6},
                "aggressive": {"min_confidence": 0.5},
            },
            "last_tuned_at": None,
        }
        metrics = {"hit_rate": 0.3, "usefulness_score": 0.3}
        tuned = auto_tune_settings(settings, metrics)
        self.assertGreater(tuned["profiles"]["conservative"]["min_confidence"], 0.6)
        self.assertGreater(tuned["profiles"]["aggressive"]["min_confidence"], 0.5)


if __name__ == "__main__":
    unittest.main()
