#!/bin/bash
# Daily Stock Analysis test helper.
#
# Usage:
#   ./scripts/test.sh [scenario]
#
# Scenarios:
#   market      - market review only
#   a-stock     - A-share stock analysis
#   etf         - ETF analysis
#   hk-stock    - Hong Kong stock analysis
#   us-stock    - US stock analysis
#   mixed       - mixed-market analysis
#   single      - single-notification mode
#   dry-run     - fetch data without AI analysis
#   full        - full workflow
#   quick       - quick single-stock smoke test
#   all         - deterministic checks plus quick online smoke tests

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

header() {
    echo ""
    echo "=============================================="
    echo -e "${GREEN}$1${NC}"
    echo "=============================================="
    echo ""
}

check_python() {
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is not installed"
        exit 1
    fi
    info "Python version: $(python3 --version)"
}

check_deps() {
    info "Checking optional dependencies..."
    python3 -c "import yfinance" 2>/dev/null || { warn "yfinance is not installed; US stock checks may fail"; }
    python3 -c "import akshare" 2>/dev/null || { warn "akshare is not installed; A-share and Hong Kong checks may fail"; }
    success "Dependency check completed"
}

test_market() {
    header "Scenario: market review"
    info "Running market review analysis..."
    python3 main.py --market-review "$@"
    success "Market review test completed"
}

test_a_stock() {
    header "Scenario: A-share analysis"
    info "Analyzing A-share examples: 600519, 000001"
    python3 main.py --stocks 600519,000001 --no-market-review "$@"
    success "A-share analysis test completed"
}

test_etf() {
    header "Scenario: ETF analysis"
    info "Analyzing ETF examples: 563230, 512400"
    python3 main.py --stocks 563230,512400 --no-market-review "$@"
    success "ETF analysis test completed"
}

test_hk_stock() {
    header "Scenario: Hong Kong stock analysis"
    info "Analyzing Hong Kong stock examples: hk00700, hk09988"
    python3 main.py --stocks hk00700,hk09988 --no-market-review "$@"
    success "Hong Kong stock analysis test completed"
}

test_us_stock() {
    header "Scenario: US stock analysis"
    info "Analyzing US stock example: AAPL"
    python3 main.py --stocks AAPL --no-market-review "$@"
    success "US stock analysis test completed"
}

test_mixed() {
    header "Scenario: mixed-market analysis"
    info "Analyzing mixed-market examples: 600519, hk00700, AAPL"
    python3 main.py --stocks 600519,hk00700,AAPL --no-market-review
    success "Mixed-market analysis test completed"
}

test_single() {
    header "Scenario: single-notification mode"
    info "Testing single-notification mode..."
    python3 main.py --stocks 600519 --single-notify --no-market-review
    success "Single-notification mode test completed"
}

test_dry_run() {
    header "Scenario: dry-run mode"
    info "Fetching data without AI analysis..."
    python3 main.py --stocks 600519,AAPL --dry-run --no-notify
    success "Dry-run test completed"
}

test_full() {
    header "Scenario: full workflow"
    info "Running full analysis workflow..."
    python3 main.py --stocks 600519 --no-notify
    success "Full workflow test completed"
}

test_quick() {
    header "Scenario: quick smoke test"
    info "Running quick single-stock smoke test..."
    python3 main.py --stocks 600519 --no-market-review --no-notify "$@"
    success "Quick smoke test completed"
}

test_code_recognition() {
    header "Scenario: stock code recognition"
    info "Testing stock code recognition logic..."

    python3 << 'PYTEST'
import sys
sys.path.insert(0, '.')
from src.services.stock_code_utils import is_code_like, normalize_code

test_cases = [
    ("AAPL", True, "AAPL", "US Apple"),
    ("TSLA", True, "TSLA", "US Tesla"),
    ("BRK.B", True, "BRK.B", "US Berkshire B"),
    ("hk00700", True, "00700", "Hong Kong Tencent"),
    ("HK09988", True, "09988", "Hong Kong Alibaba"),
    ("600519", True, "600519", "A-share Kweichow Moutai"),
    ("000001", True, "000001", "A-share Ping An Bank"),
    ("not-a-code", False, None, "plain text"),
]

print("\nStock code recognition test:")
print("-" * 60)
all_pass = True
for code, expected_like, expected_normalized, desc in test_cases:
    code_like = is_code_like(code)
    normalized = normalize_code(code)
    like_ok = code_like == expected_like
    normalize_ok = normalized == expected_normalized
    status = "PASS" if (like_ok and normalize_ok) else "FAIL"
    all_pass = all_pass and like_ok and normalize_ok
    print(
        f"{status} {code:12} | code_like:{code_like!s:5} "
        f"normalized:{str(normalized):8} | {desc}"
    )

print("-" * 60)
print("All tests passed!" if all_pass else "Some tests failed!")
sys.exit(0 if all_pass else 1)
PYTEST

    success "Stock code recognition test completed"
}

test_yfinance_convert() {
    header "Scenario: YFinance-compatible code normalization"
    info "Testing code normalization used before provider-specific conversion..."

    python3 << 'PYTEST'
import sys
sys.path.insert(0, '.')
from src.services.stock_code_utils import normalize_code

test_cases = [
    ("AAPL", "AAPL", "US"),
    ("tsla", "TSLA", "US lowercase"),
    ("BRK.B", "BRK.B", "US special ticker"),
    ("hk00700", "00700", "Hong Kong"),
    ("HK09988", "09988", "Hong Kong uppercase"),
    ("600519", "600519", "A-share Shanghai"),
    ("000001", "000001", "A-share Shenzhen"),
    ("300750", "300750", "A-share ChiNext"),
]

print("\nYFinance-compatible code normalization test:")
print("-" * 60)
all_pass = True
for input_code, expected, desc in test_cases:
    result = normalize_code(input_code)
    status = "PASS" if result == expected else "FAIL"
    all_pass = all_pass and (result == expected)
    print(f"{status} {input_code:10} -> {result:12} (expected: {expected:12}) | {desc}")

print("-" * 60)
print("All tests passed!" if all_pass else "Some tests failed!")
sys.exit(0 if all_pass else 1)
PYTEST

    success "YFinance-compatible code normalization test completed"
}

test_syntax() {
    header "Scenario: Python syntax check"
    info "Checking Python syntax for key files..."

    python3 -m py_compile main.py src/config.py src/notification.py \
        data_provider/akshare_fetcher.py \
        data_provider/yfinance_fetcher.py \
        bot/commands/analyze.py

    success "Python syntax check passed"
}

test_flake8() {
    header "Scenario: Flake8 critical checks"
    info "Running Flake8 critical error checks..."

    if command -v flake8 &> /dev/null; then
        flake8 main.py src/config.py src/notification.py --select=F821,E999 --max-line-length=120
        success "Flake8 critical checks passed"
    else
        warn "Flake8 is not installed; skipping lint check"
    fi
}

test_all() {
    header "Run all test scenarios"

    test_syntax
    test_code_recognition
    test_yfinance_convert
    test_flake8

    echo ""
    info "The following checks require network access and API configuration, so they may fail:"
    echo ""

    test_dry_run || warn "Dry-run test failed, possibly due to network access"
    test_quick || warn "Quick smoke test failed, possibly due to API configuration"

    success "All requested test scenarios completed"
}

main() {
    header "Daily Stock Analysis test helper"

    check_python
    check_deps

    case "${1:-help}" in
        market)
            shift
            test_market "$@"
            ;;
        a-stock|a_stock|astock)
            shift
            test_a_stock "$@"
            ;;
        etf)
            shift
            test_etf "$@"
            ;;
        hk-stock|hk_stock|hkstock|hk)
            shift
            test_hk_stock "$@"
            ;;
        us-stock|us_stock|usstock|us)
            shift
            test_us_stock "$@"
            ;;
        mixed|mix)
            shift
            test_mixed "$@"
            ;;
        single)
            shift
            test_single "$@"
            ;;
        dry-run|dryrun|dry)
            shift
            test_dry_run "$@"
            ;;
        full)
            shift
            test_full "$@"
            ;;
        quick|q)
            shift
            test_quick "$@"
            ;;
        code|recognition)
            shift
            test_code_recognition "$@"
            ;;
        yfinance|yf)
            shift
            test_yfinance_convert "$@"
            ;;
        syntax)
            shift
            test_syntax "$@"
            ;;
        flake8|lint)
            shift
            test_flake8 "$@"
            ;;
        all)
            shift
            test_all "$@"
            ;;
        help|--help|-h|*)
            echo "Usage: $0 [scenario]"
            echo ""
            echo "Scenarios:"
            echo "  market      - market review only"
            echo "  a-stock     - A-share stock analysis"
            echo "  etf         - ETF analysis"
            echo "  hk-stock    - Hong Kong stock analysis"
            echo "  us-stock    - US stock analysis"
            echo "  mixed       - mixed-market analysis"
            echo "  single      - single-notification mode"
            echo "  dry-run     - fetch data without AI analysis"
            echo "  full        - full workflow"
            echo "  quick       - quick smoke test"
            echo "  code        - stock code recognition test"
            echo "  yfinance    - YFinance code conversion test"
            echo "  syntax      - Python syntax check"
            echo "  flake8      - Flake8 critical checks"
            echo "  all         - run all test scenarios"
            echo ""
            echo "Examples:"
            echo "  $0 quick"
            echo "  $0 us-stock"
            echo "  $0 code"
            echo "  $0 all"
            ;;
    esac
}

main "$@"
