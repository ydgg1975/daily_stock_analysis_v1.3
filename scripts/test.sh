#!/bin/bash
# ===================================
# Agu/ganggu/meigu zhinengfenxixitong - ceshijiaoben
# ===================================
#
# shiyongfangfa：
#   ./scripts/test.sh [ceshichangjing]
#
# ceshichangjing：
#   market      - jindapanfupan
#   a-stock     - Agugegufenxi（maotai、pinganyinhang）
#   etf         - etffenxi(weixingetf 563230)
#   hk-stock    - ganggufenxi（tengxun、ali）
#   us-stock    - meigufenxi（pingguo、tesila）
#   mixed       - hunheshichangfenxi
#   single      - dangumoshiceshi
#   dry-run     - jinhuoqushujubufenxi
#   full        - wanzhengliuchengceshi
#   quick       - kuaisuceshi（danzhigupiao）
#   all         - yunxingsuoyouceshi
#
# shili：
#   ./scripts/test.sh market      # ceshidapanfupan
#   ./scripts/test.sh us-stock    # ceshimeigufenxi
#   ./scripts/test.sh quick       # kuaisuceshi
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

# yansedingyi
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# dayindaiyansedexinxi
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

# jianchaPythonhuanjing
check_python() {
    if ! command -v python3 &> /dev/null; then
        error "Python3 weianzhuang"
        exit 1
    fi
    info "Pythonbanben: $(python3 --version)"
}

# jianchayilai
check_deps() {
    info "jianchayilai..."
    python3 -c "import yfinance" 2>/dev/null || { warn "yfinance weianzhuang，meiguceshikenengshibai"; }
    python3 -c "import akshare" 2>/dev/null || { warn "akshare weianzhuang，Agu/gangguceshikenengshibai"; }
    success "yilaijianchawancheng"
}

# ==================== ceshichangjing ====================

# ceshi1: dapanfupan
test_market() {
    header "ceshichangjing: dapanfupan"
    info "yunxingdapanfupanfenxi..."
    python3 main.py --market-review "$@"
    success "dapanfupanceshiwancheng"
}

# ceshi2: Agufenxi
test_a_stock() {
    header "ceshichangjing: Agufenxi"
    info "fenxiAgu: 600519(maotai), 000001(pinganyinhang)"
    python3 main.py --stocks 600519,000001  --no-market-review "$@"
    success "Agufenxiceshiwancheng"
}

# ceshi2.5: ETFfenxi
test_etf() {
    header "ceshichangjing: ETFfenxi"
    info "fenxiETF: 563230(weixingETF)"
    python3 main.py --stocks 563230,512400 --no-market-review "$@"
    success "ETFfenxiceshiwancheng"
}

# ceshi3: ganggufenxi
test_hk_stock() {
    header "ceshichangjing: ganggufenxi"
    info "fenxiganggu: hk00700(tengxun), hk09988(ali)"
    python3 main.py --stocks hk00700,hk09988 --no-market-review "$@"
    success "ganggufenxiceshiwancheng"
}

# ceshi4: meigufenxi
test_us_stock() {
    header "ceshichangjing: meigufenxi"
    info "fenximeigu: AAPL(pingguo), TSLA(tesila)"
    # yunxutouchuancanshu，morenbudai --no-notify
    python3 main.py --stocks AAPL --no-market-review "$@"
    success "meigufenxiceshiwancheng"
}

# ceshi5: hunheshichang
test_mixed() {
    header "ceshichangjing: hunheshichangfenxi"
    info "fenxihunheshichang: 600519(Agu), hk00700(ganggu), AAPL(meigu)"
    python3 main.py --stocks 600519,hk00700,AAPL --no-market-review
    success "hunheshichangceshiwancheng"
}

# ceshi6: dangutuisongmoshi
test_single() {
    header "ceshichangjing: dangutuisongmoshi"
    info "ceshidangutuisongmoshi..."
    python3 main.py --stocks 600519 --single-notify --no-market-review
    success "dangutuisongmoshiceshiwancheng"
}

# ceshi7: dry-runmoshi
test_dry_run() {
    header "ceshichangjing: Dry-Run moshi"
    info "jinhuoqushuju，bujinxingAIfenxi..."
    python3 main.py --stocks 600519,AAPL --dry-run --no-notify
    success "Dry-Run ceshiwancheng"
}

# ceshi8: wanzhengliucheng
test_full() {
    header "ceshichangjing: wanzhengliucheng"
    info "yunxingwanzhengfenxiliucheng（gegu+dapan）..."
    python3 main.py --stocks 600519 --no-notify
    success "wanzhengliuchengceshiwancheng"
}

# ceshi9: kuaisuceshi
test_quick() {
    header "ceshichangjing: kuaisuceshi"
    info "danzhigupiaokuaisuceshi..."
    python3 main.py --stocks 600519 --no-market-review --no-notify "$@"
    success "kuaisuceshiwancheng"
}

# ceshi10: daimashibieceshi
test_code_recognition() {
    header "ceshichangjing: daimashibie"
    info "ceshigupiaodaimashibieluoji..."

    python3 << 'PYTEST'
import sys
sys.path.insert(0, '.')
from data_provider.akshare_fetcher import _is_hk_code, _is_us_code

test_cases = [
    # (daima, yuqiHK, yuqiUS, miaoshu)
    ("AAPL", False, True, "meigu-pingguo"),
    ("TSLA", False, True, "meigu-tesila"),
    ("BRK.B", False, True, "meigu-bokexierB"),
    ("hk00700", True, False, "ganggu-tengxun"),
    ("HK09988", True, False, "ganggu-ali"),
    ("600519", False, False, "Agu-maotai"),
    ("000001", False, False, "Agu-pingan"),
]

print("\ngupiaodaimashibieceshi:")
print("-" * 60)
all_pass = True
for code, exp_hk, exp_us, desc in test_cases:
    is_hk = _is_hk_code(code)
    is_us = _is_us_code(code)
    hk_ok = is_hk == exp_hk
    us_ok = is_us == exp_us
    status = "✅" if (hk_ok and us_ok) else "❌"
    all_pass = all_pass and hk_ok and us_ok
    print(f"{status} {code:10} | HK:{is_hk:5} US:{is_us:5} | {desc}")

print("-" * 60)
print(f"{'✅ suoyouceshitongguo!' if all_pass else '❌ youceshishibai!'}")
sys.exit(0 if all_pass else 1)
PYTEST

    success "daimashibieceshiwancheng"
}

# ceshi11: YFinancedaimazhuanhuanceshi
test_yfinance_convert() {
    header "ceshichangjing: YFinance daimazhuanhuan"
    info "ceshiYFinancedaimazhuanhuanluoji..."

    python3 << 'PYTEST'
import sys
sys.path.insert(0, '.')
from data_provider.yfinance_fetcher import YfinanceFetcher

fetcher = YfinanceFetcher()

test_cases = [
    ("AAPL", "AAPL", "meigu"),
    ("tsla", "TSLA", "meiguxiaoxie"),
    ("BRK.B", "BRK.B", "meiguteshu"),
    ("hk00700", "0700.HK", "ganggu"),
    ("HK09988", "9988.HK", "ganggudaxie"),
    ("600519", "600519.SS", "Aguhushi"),
    ("000001", "000001.SZ", "Agushenshi"),
    ("300750", "300750.SZ", "Aguchuangyeban"),
]

print("\nYFinance daimazhuanhuanceshi:")
print("-" * 60)
all_pass = True
for input_code, expected, desc in test_cases:
    result = fetcher._convert_stock_code(input_code)
    status = "✅" if result == expected else "❌"
    all_pass = all_pass and (result == expected)
    print(f"{status} {input_code:10} -> {result:12} (qiwang: {expected:12}) | {desc}")

print("-" * 60)
print(f"{'✅ suoyouceshitongguo!' if all_pass else '❌ youceshishibai!'}")
sys.exit(0 if all_pass else 1)
PYTEST

    success "YFinance daimazhuanhuanceshiwancheng"
}

# ceshi12: yufajiancha
test_syntax() {
    header "ceshichangjing: Python yufajiancha"
    info "jianchasuoyouPythonwenjianyufa..."

    python3 -m py_compile main.py src/config.py src/notification.py \
        data_provider/akshare_fetcher.py \
        data_provider/yfinance_fetcher.py \
        bot/commands/analyze.py

    success "yufajianchatongguo"
}

# ceshi13: Flake8 jingtaijiancha
test_flake8() {
    header "ceshichangjing: Flake8 jingtaijiancha"
    info "yunxing Flake8 jianchayanzhongcuowu..."

    if command -v flake8 &> /dev/null; then
        flake8 main.py src/config.py src/notification.py --select=F821,E999 --max-line-length=120
        success "Flake8 jianchatongguo"
    else
        warn "Flake8 weianzhuang，tiaoguojiancha"
    fi
}

# yunxingsuoyouceshi
test_all() {
    header "yunxingsuoyouceshi"

    test_syntax
    test_code_recognition
    test_yfinance_convert
    test_flake8

    echo ""
    info "yixiaceshixuyaowangluoheAPIpeizhi，kenenghuishibai:"
    echo ""

    test_dry_run || warn "Dry-Run ceshishibai（kenengshiwangluowenti）"
    test_quick || warn "kuaisuceshishibai（kenengshiAPIwenti）"

    success "suoyouceshiwancheng!"
}

# ==================== zhuchengxu ====================

main() {
    header "Agu/ganggu/meigu zhinengfenxixitong - ceshi"

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
            echo "shiyongfangfa: $0 [ceshichangjing]"
            echo ""
            echo "ceshichangjing:"
            echo "  market      - jindapanfupan"
            echo "  a-stock     - Agugegufenxi"
            echo "  etf         - ETFfenxi"
            echo "  hk-stock    - ganggufenxi"
            echo "  us-stock    - meigufenxi"
            echo "  mixed       - hunheshichangfenxi"
            echo "  single      - dangutuisongmoshi"
            echo "  dry-run     - jinhuoqushuju"
            echo "  full        - wanzhengliucheng"
            echo "  quick       - kuaisuceshi（tuijian）"
            echo "  code        - daimashibieceshi"
            echo "  yfinance    - YFinancezhuanhuanceshi"
            echo "  syntax      - yufajiancha"
            echo "  flake8      - jingtaijiancha"
            echo "  all         - yunxingsuoyouceshi"
            echo ""
            echo "shili:"
            echo "  $0 quick     # kuaisuceshi"
            echo "  $0 us-stock  # ceshimeigu"
            echo "  $0 code      # ceshidaimashibie"
            echo "  $0 all       # yunxingsuoyouceshi"
            ;;
    esac
}

main "$@"
