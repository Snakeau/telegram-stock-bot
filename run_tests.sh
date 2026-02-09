#!/bin/bash
# Test runner script - unified interface for running tests

set -e

CHATBOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$CHATBOT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Activate virtual environment
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Main test runner
run_tests() {
    local test_type=$1
    local extra_args=$2
    
    case $test_type in
        all)
            print_header "Running ALL TESTS"
            python -m pytest tests/ -v --tb=short $extra_args
            ;;
        quick)
            print_header "Running QUICK TESTS (no coverage)"
            python -m pytest tests/ -q --tb=line $extra_args
            ;;
        failed)
            print_header "Running ONLY FAILED TESTS"
            python -m pytest tests/ --lf -v --tb=short $extra_args
            ;;
        failed-only)
            print_header "Running tests that failed last time"
            python -m pytest tests/ --lf --tb=short $extra_args
            ;;
        coverage)
            print_header "Running TESTS with COVERAGE"
            python -m pytest tests/ --cov=chatbot --cov-report=html --cov-report=term-missing $extra_args
            echo -e "${GREEN}Coverage report: htmlcov/index.html${NC}"
            ;;
        bug-fixes)
            print_header "Testing BUG FIXES (test_bug_fixes.py)"
            python -m pytest tests/test_bug_fixes.py -v --tb=short $extra_args
            ;;
        asset-resolution)
            print_header "Testing ASSET RESOLUTION"
            python -m pytest tests/test_asset_resolution.py -v --tb=short $extra_args
            ;;
        portfolio)
            print_header "Testing PORTFOLIO"
            python -m pytest tests/test_integration_portfolio.py -v --tb=short $extra_args
            ;;
        market)
            print_header "Testing MARKET DATA"
            python -m pytest tests/test_market_data_service.py -v --tb=short $extra_args
            ;;
        callbacks)
            print_header "Testing CALLBACKS"
            python -m pytest tests/test_callbacks_routing.py -v --tb=short $extra_args
            ;;
        ui)
            print_header "Testing UI SCREENS"
            python -m pytest tests/test_screens.py tests/test_asset_ui_display.py -v --tb=short $extra_args
            ;;
        *)
            print_header "TEST RUNNER HELP"
            echo ""
            echo "Usage: ./run_tests.sh [test_type] [pytest_args]"
            echo ""
            echo "Test types:"
            echo "  all              - Run all tests with coverage"
            echo "  quick            - Run all tests (no coverage, fast)"
            echo "  failed           - Run only failed tests"
            echo "  failed-only      - Run tests that failed last time"
            echo "  coverage         - Run tests with detailed coverage report"
            echo "  bug-fixes        - Run BUG #1 & #2 regression tests"
            echo "  asset-resolution - Run asset resolution tests"
            echo "  portfolio        - Run portfolio integration tests"
            echo "  market           - Run market data tests"
            echo "  callbacks        - Run callback routing tests"
            echo "  ui               - Run UI/screens tests"
            echo ""
            echo "Example: ./run_tests.sh quick"
            echo "Example: ./run_tests.sh all -k 'not test_slow'"
            echo ""
            ;;
    esac
}

# Show summary
show_summary() {
    print_header "TEST STATISTICS"
    python -m pytest tests/ --collect-only -q 2>/dev/null | wc -l
    echo "test files found in tests/"
}

# Main execution
if [ "$1" = "--summary" ]; then
    show_summary
else
    run_tests "$@"
fi
