#!/bin/bash
# Complete test report generator

set -e

CHATBOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$CHATBOT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║             TEST SUITE COMPREHENSIVE REPORT                    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Activate venv
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate >> /dev/null 2>&1
fi

# Test count
echo -e "${CYAN}📊 TEST INVENTORY${NC}"
echo -e "${CYAN}─────────────────────────────────────────${NC}"
test_files=$(find tests -name "test_*.py" | wc -l)
test_count=$(python -m pytest tests/ --collect-only -q 2>/dev/null | grep "test_" | wc -l)
echo -e "Test Files: ${GREEN}$test_files${NC}"
echo -e "Total Tests: ${GREEN}$test_count${NC}"
echo ""

# Latest test run
echo -e "${CYAN}🧪 RUNNING TESTS${NC}"
echo -e "${CYAN}─────────────────────────────────────────${NC}"

# Quick run with summary
python -m pytest tests/ -q --tb=no 2>&1 | tail -5

echo ""

# Test groups breakdown
echo -e "${CYAN}📋 TEST COVERAGE BY GROUP${NC}"
echo -e "${CYAN}─────────────────────────────────────────${NC}"

for test_file in tests/test_*.py; do
    filename=$(basename "$test_file")
    count=$(python -m pytest "$test_file" --collect-only -q 2>/dev/null | grep "test_" | wc -l || echo "0")
    printf "  %-35s: ${GREEN}%3d${NC} tests\n" "$filename" "$count"
done

echo ""
echo -e "${CYAN}📈 QUICK COMMANDS${NC}"
echo -e "${CYAN}─────────────────────────────────────────${NC}"
echo -e "  ${YELLOW}./run_tests.sh quick${NC}        - Fast test run"
echo -e "  ${YELLOW}./run_tests.sh bug-fixes${NC}    - Test bug fixes"
echo -e "  ${YELLOW}make test-quick${NC}             - Make command"
echo -e "  ${YELLOW}make test-watch${NC}             - Watch mode"
echo ""

echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
