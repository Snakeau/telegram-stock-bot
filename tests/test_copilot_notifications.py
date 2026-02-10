import tempfile
import unittest
from pathlib import Path

from chatbot.copilot.notifications import NotificationGuard


class TestCopilotNotifications(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.guard = NotificationGuard(Path(self.tmpdir.name) / "notifications.json")
        self.reco = {
            "action": "REDUCE",
            "ticker": "AAPL",
            "priority": "warning",
            "reason": ["Concentration risk"],
        }

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_dedup_within_cooldown(self):
        ok1, why1 = self.guard.should_send(
            user_id=1,
            recommendation=self.reco,
            portfolio_version="v1",
            cooldown_minutes=120,
            max_alerts_per_day=10,
        )
        ok2, why2 = self.guard.should_send(
            user_id=1,
            recommendation=self.reco,
            portfolio_version="v1",
            cooldown_minutes=120,
            max_alerts_per_day=10,
        )
        self.assertTrue(ok1)
        self.assertEqual("ok", why1)
        self.assertFalse(ok2)
        self.assertEqual("cooldown", why2)

    def test_daily_limit(self):
        for i in range(2):
            ok, _ = self.guard.should_send(
                user_id=2,
                recommendation={**self.reco, "ticker": f"AAPL{i}"},
                portfolio_version="v1",
                cooldown_minutes=0,
                max_alerts_per_day=2,
            )
            self.assertTrue(ok)

        ok3, why3 = self.guard.should_send(
            user_id=2,
            recommendation={**self.reco, "ticker": "TSLA"},
            portfolio_version="v1",
            cooldown_minutes=0,
            max_alerts_per_day=2,
        )
        self.assertFalse(ok3)
        self.assertEqual("daily_limit", why3)


if __name__ == "__main__":
    unittest.main()
