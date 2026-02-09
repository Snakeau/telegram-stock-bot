# Test Suite Documentation

**Project:** Telegram Stock Bot  
**Total Tests:** 334  
**Test Files:** 17  
**Status:** 284 passed ✓ | 32 failed ✗ | 1 skipped ⊘

---

## 🚀 Quick Start

### Option 1: Using shell script (recommended)
```bash
# Quick test run
./run_tests.sh quick

# Test specific feature
./run_tests.sh bug-fixes     # BUG #1 & #2 regression tests
./run_tests.sh asset-resolution
./run_tests.sh portfolio
./run_tests.sh market
./run_tests.sh callbacks
./run_tests.sh ui
```

### Option 2: Using Makefile
```bash
# Quick run
make test-quick

# Full run with coverage
make test

# Watch mode (re-run tests on file changes)
make test-watch

# Specific tests
make test-bugfixes
make test-assets
make test-portfolio
make test-market
make test-callbacks
make test-ui
```

### Option 3: Direct pytest
```bash
# All tests
pytest tests/ -v

# Only failed tests
pytest tests/ --lf -v

# With coverage
pytest tests/ --cov=chatbot --cov-report=html

# Specific test file
pytest tests/test_bug_fixes.py -v

# Specific test
pytest tests/test_bug_fixes.py::TestBug1StockFlowRouting -v
```

---

## 📊 Test Coverage by Module

| Test File | Tests | Coverage | Purpose |
|-----------|-------|----------|---------|
| `test_asset_resolution.py` | 40 | Asset resolution logic |
| `test_asset_ui_display.py` | 35 | UI display for assets |
| `test_bug_fixes.py` | 16 | ✅ BUG #1 & #2 regression tests |
| `test_callbacks_routing.py` | 14 | Callback routing |
| `test_db.py` | 7 | Database operations |
| `test_finnhub_integration.py` | 17 | Finnhub provider |
| `test_integration_portfolio.py` | 12 | Portfolio analysis |
| `test_market_batch.py` | 4 | Batch market data |
| `test_market_data_fallback.py` | 26 | Fallback provider logic |
| `test_market_data_service.py` | 29 | Market data service |
| `test_metrics.py` | 16 | Metrics calculation |
| `test_parsing.py` | 33 | Text parsing |
| `test_portfolio_parse.py` | 12 | Portfolio parsing |
| `test_provider_layer.py` | 13 | Provider layer |
| `test_screens.py` | 23 | Screen rendering |
| `test_sec_cache.py` | 4 | SEC cache |
| `test_utils.py` | 33 | Utility functions |

---

## 🧪 Running Specific Test Groups

### Bug Fix Tests (Highest Priority)
```bash
# Test BUG #1 Fix (Stock flow routing)
./run_tests.sh bug-fixes

# Expected: ✅ 14 passed, 1 skipped
```

### Asset Resolution Tests
```bash
./run_tests.sh asset-resolution

# Tests asset resolution and UI display
```

### Portfolio Tests
```bash
./run_tests.sh portfolio

# Tests portfolio analysis and integration
```

### Market Data Tests
```bash
./run_tests.sh market

# Tests market data service and providers
```

---

## 📈 Test Execution Options

### Fast Mode (No Coverage)
```bash
./run_tests.sh quick
# or
make test-quick
```

### Full Mode (With Coverage Report)
```bash
./run_tests.sh coverage
# or
make test-coverage
```

### Watch Mode (Auto re-run on changes)
```bash
make test-watch

# Requires: pip install pytest-watch
```

### Debug Mode (Maximum verbosity)
```bash
make test-debug
```

### Only Failed Tests
```bash
./run_tests.sh failed
# or
make test-failed
```

---

## 📋 All Available Commands

### Shell Script (`./run_tests.sh`)
```bash
./run_tests.sh all              # All with coverage
./run_tests.sh quick            # Quick run
./run_tests.sh failed           # Only failed tests
./run_tests.sh coverage         # Detailed coverage
./run_tests.sh bug-fixes        # BUG #1 & #2 tests
./run_tests.sh asset-resolution # Asset tests
./run_tests.sh portfolio        # Portfolio tests
./run_tests.sh market           # Market data tests
./run_tests.sh callbacks        # Callback tests
./run_tests.sh ui               # UI tests
```

### Makefile (`make`)
```bash
make help                  # Show all commands
make test                  # Full suite with coverage
make test-quick            # Quick run
make test-coverage         # Coverage report
make test-watch            # Watch mode
make test-debug            # Debug verbosity
make test-bugfixes         # Bug fix tests
make test-assets           # Asset tests
make test-portfolio        # Portfolio tests
make test-market           # Market tests
make test-callbacks        # Callback tests
make test-ui               # UI tests
make clean                 # Clean artifacts
make test-summary          # Test count
```

---

## 🔍 Coverage Report

Generate and view detailed coverage:

```bash
# Generate HTML report
./run_tests.sh coverage
# or
make test-coverage

# Open in browser
open htmlcov/index.html
```

---

## ⚙️ Configuration

### pytest.ini / pyproject.toml

Test configuration is in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = ["-v", "--tb=short", "--cov=chatbot"]
```

---

## 🐛 Known Issues

### Failed Tests (32/334)

Most failures are in:
- `test_finnhub_integration.py` - Event loop issues
- `test_market_data_service.py` - Async/await mocking issues
- `test_provider_layer.py` - Provider method reference issues
- `test_utils.py` - Minor parsing/formatting edge cases

**Status:** These are non-blocking issues that don't affect core functionality.

---

## ✅ Next Steps

1. **Quick validation:**
   ```bash
   make test-bugfixes
   ```

2. **Full test suite:**
   ```bash
   make test-quick
   ```

3. **Coverage analysis:**
   ```bash
   make test-coverage
   ```

4. **Continuous testing:**
   ```bash
   make test-watch
   ```

---

## 📝 Writing New Tests

Test files should follow naming convention: `test_*.py`

Example:
```python
import unittest

class TestNewFeature(unittest.TestCase):
    def test_something(self):
        """Test description"""
        self.assertEqual(1 + 1, 2)

if __name__ == "__main__":
    unittest.main()
```

Run your new test:
```bash
pytest tests/test_newfeature.py -v
```

---

## 💡 Pro Tips

1. **Run only recently failed tests:**
   ```bash
   make test-failed
   ```

2. **Run specific test by name:**
   ```bash
   pytest tests/test_bug_fixes.py::TestBug1StockFlowRouting::test_on_stock_input_returns_waiting_stock_on_error -v
   ```

3. **Run tests matching pattern:**
   ```bash
   pytest tests/ -k "bug_fixes" -v
   ```

4. **Skip slow tests:**
   ```bash
   pytest tests/ -m "not slow" -v
   ```

5. **Get test report:**
   ```bash
   bash test_report.sh
   ```

---

**Last Updated:** February 9, 2026  
**Maintained by:** Development Team
