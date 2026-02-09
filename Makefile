# Makefile for convenient test execution and project management

.PHONY: help test test-quick test-failed test-coverage test-watch test-debug \
        test-bugfixes test-assets test-portfolio test-market test-callbacks test-ui \
        test-summary lint format clean install coverage

help:
	@echo "Available commands:"
	@echo ""
	@echo "Testing:"
	@echo "  make test              - Run all tests with coverage"
	@echo "  make test-quick        - Run all tests quickly (no coverage)"
	@echo "  make test-failed       - Run only tests that failed last time"
	@echo "  make test-coverage     - Show detailed coverage report"
	@echo "  make test-watch        - Run tests in watch mode (re-run on file changes)"
	@echo "  make test-debug        - Run tests with maximum verbosity"
	@echo ""
	@echo "Specific tests:"
	@echo "  make test-bugfixes     - BUG #1 & #2 regression tests"
	@echo "  make test-assets       - Asset resolution tests"
	@echo "  make test-portfolio    - Portfolio integration tests"
	@echo "  make test-market       - Market data tests"
	@echo "  make test-callbacks    - Callback routing tests"
	@echo "  make test-ui           - UI/screens tests"
	@echo ""
	@echo "Analysis:"
	@echo "  make test-summary      - Count total tests"
	@echo "  make lint              - Run linters (pylint, flake8)"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean             - Remove test artifacts"
	@echo "  make clean-db          - Remove test database files"

test:
	@source .venv/bin/activate && python -m pytest tests/ -v --tb=short --cov=chatbot --cov-report=term-missing

test-quick:
	@source .venv/bin/activate && python -m pytest tests/ -q --tb=line

test-failed:
	@source .venv/bin/activate && python -m pytest tests/ --lf -v --tb=short

test-failed-quick:
	@source .venv/bin/activate && python -m pytest tests/ --lf -q

test-coverage:
	@source .venv/bin/activate && python -m pytest tests/ --cov=chatbot --cov-report=html --cov-report=term-missing && \
	echo "Coverage report: htmlcov/index.html"

test-watch:
	@source .venv/bin/activate && python -m pytest tests/ -v --tb=short --looponfail

test-debug:
	@source .venv/bin/activate && python -m pytest tests/ -vv --tb=long -s

test-bugfixes:
	@source .venv/bin/activate && python -m pytest tests/test_bug_fixes.py -v --tb=short

test-assets:
	@source .venv/bin/activate && python -m pytest tests/test_asset_resolution.py tests/test_asset_ui_display.py -v --tb=short

test-portfolio:
	@source .venv/bin/activate && python -m pytest tests/test_integration_portfolio.py -v --tb=short

test-market:
	@source .venv/bin/activate && python -m pytest tests/test_market_data_service.py -v --tb=short

test-callbacks:
	@source .venv/bin/activate && python -m pytest tests/test_callbacks_routing.py -v --tb=short

test-ui:
	@source .venv/bin/activate && python -m pytest tests/test_screens.py tests/test_asset_ui_display.py -v --tb=short

test-summary:
	@echo "Total test files:"
	@find tests -name "test_*.py" | wc -l
	@echo ""
	@echo "Total test functions:"
	@source .venv/bin/activate && python -m pytest tests/ --collect-only -q 2>/dev/null | grep "test_" | wc -l
	@echo ""
	@echo "Test file list:"
	@find tests -name "test_*.py" | sort

lint:
	@echo "Checking code quality..."
	@source .venv/bin/activate && python -m flake8 chatbot/ app/ --max-line-length=120 --ignore=E203,W503 || true
	@echo "✓ Linting complete"

clean:
	@echo "Cleaning test artifacts..."
	@rm -rf .pytest_cache/
	@rm -rf htmlcov/
	@rm -rf .coverage
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@echo "✓ Cleaned"

clean-db:
	@echo "Cleaning test databases..."
	@rm -f portfolio.db
	@rm -f test_*.db
	@echo "✓ Cleaned"

install-test-deps:
	@pip install pytest-watch pytest-cov flake8 pylint

install:
	@pip install -r requirements.txt
	@pip install -r requirements-dev.txt

.DEFAULT_GOAL := help
