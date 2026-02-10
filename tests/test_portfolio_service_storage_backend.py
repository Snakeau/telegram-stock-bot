import unittest

from app.services.portfolio_service import PortfolioService


class _FakeDB:
    def __init__(self):
        self.data = {}
        self.nav = {}

    def save_portfolio(self, user_id, raw_text):
        self.data[int(user_id)] = raw_text

    def get_portfolio(self, user_id):
        return self.data.get(int(user_id))

    def save_nav(self, user_id, total_value, currency="USD"):
        self.nav[int(user_id)] = (float(total_value), currency)

    def get_nav_series(self, user_id, days=90):
        return []


class _FakeCopilot:
    def __init__(self):
        self.data = {}

    def save_inline_portfolio_text(self, user_id, raw_text):
        self.data[int(user_id)] = raw_text

    def get_inline_portfolio_text(self, user_id):
        return self.data.get(int(user_id))


class TestPortfolioServiceStorageBackend(unittest.TestCase):
    def test_prefers_copilot_backend_and_keeps_sqlite_mirror(self):
        db = _FakeDB()
        copilot = _FakeCopilot()
        svc = PortfolioService(db=db, market_provider=None, sec_provider=None, copilot_service=copilot)

        svc.save_portfolio(123, "AAPL 1 100")

        self.assertEqual("AAPL 1 100", copilot.get_inline_portfolio_text(123))
        self.assertEqual("AAPL 1 100", db.get_portfolio(123))
        self.assertTrue(svc.has_portfolio(123))
        self.assertEqual("AAPL 1 100", svc.get_saved_portfolio(123))

    def test_migrates_legacy_sqlite_record_on_read(self):
        db = _FakeDB()
        copilot = _FakeCopilot()
        db.save_portfolio(123, "MSFT 2 300")

        svc = PortfolioService(db=db, market_provider=None, sec_provider=None, copilot_service=copilot)
        text = svc.get_saved_portfolio(123)

        self.assertEqual("MSFT 2 300", text)
        self.assertEqual("MSFT 2 300", copilot.get_inline_portfolio_text(123))


if __name__ == "__main__":
    unittest.main()
