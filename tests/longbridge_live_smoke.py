# -*- coding: utf-8 -*-
"""
长桥 OpenAPI 联调冒烟脚本（不由 pytest 收集，文件名无 test_ 前缀）。

用法：
    # 1. 复制 .env.example 为 .env 并填写 LONGBRIDGE_*（应用不会自动加载 .env.example）
    # 2. 或在 shell 中设置环境变量，例如 set LONGBRIDGE_APP_KEY=...

    # 3. 在仓库根目录或 tests 目录下运行均可（Python 3.10+）
    python tests/longbridge_live_smoke.py

    # 4. 指定标的
    python tests/longbridge_live_smoke.py TSLA

    # 5. 临时传入凭证（优先仍用 .env；命令行可能进入 shell 历史记录）
    python tests/longbridge_live_smoke.py AAPL --lb-app-key ... --lb-app-secret ... --lb-access-token ...

级别说明：
    级别 1：单独 LongbridgeFetcher（长桥 API 是否可用）
    级别 2：DataFetcherManager 美股/港股行情（按路由优先长桥或 YFinance 后的合并效果）
    级别 3：完整 get_realtime_quote 链路
    级别 4：自选分组（fetch_stock_codes_for_watchlist_group_names；需 LONGBRIDGE_WATCHLIST_GROUPS 或 --watchlist-groups）
"""

import argparse
import logging
import os
import sys
from typing import List, Optional

# 仓库根目录（加入 sys.path，便于从 tests/ 直接运行）
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _PROJECT_ROOT)

# 加载仓库根目录 .env（不依赖当前工作目录，避免在 tests/ 下运行时找不到 ../.env）
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))
except ImportError:
    pass


def _print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def _print_field(label: str, value, ok_if_not_none=True):
    status = "OK" if (value is not None and value != 0) else "MISSING"
    mark = "[+]" if status == "OK" else "[x]"
    if ok_if_not_none:
        print(f"  {mark} {label:20s}: {value}  [{status}]")
    else:
        print(f"     {label:20s}: {value}")


def run_level1_standalone(stock_code: str):
    """仅使用 LongbridgeFetcher 拉取行情。"""
    _print_header(f"级别 1：LongbridgeFetcher 单测 ({stock_code})")

    from data_provider.longbridge_fetcher import LongbridgeFetcher

    fetcher = LongbridgeFetcher()

    if not fetcher._is_available():
        print("  [x] 未配置长桥凭证！")
        print("  请设置 LONGBRIDGE_APP_KEY、LONGBRIDGE_APP_SECRET、LONGBRIDGE_ACCESS_TOKEN")
        return False

    print("  [+] 已检测到凭证")

    quote = fetcher.get_realtime_quote(stock_code)
    if quote is None:
        print(f"  [x] get_realtime_quote({stock_code}) 返回 None")
        _print_longbridge_connect_troubleshoot()
        return False

    print(f"\n  {stock_code} 行情（来源: {quote.source.value}）:")
    _print_field("price", quote.price)
    _print_field("change_pct", f"{quote.change_pct}%" if quote.change_pct else None)
    _print_field("volume", quote.volume)
    _print_field("amount (turnover)", quote.amount)
    _print_field("volume_ratio", quote.volume_ratio)
    _print_field("turnover_rate", f"{quote.turnover_rate}%" if quote.turnover_rate else None)
    _print_field("pe_ratio", quote.pe_ratio)
    _print_field("pb_ratio", quote.pb_ratio)
    _print_field("total_mv", quote.total_mv)
    _print_field("name", quote.name, ok_if_not_none=False)

    critical_fields = [quote.volume_ratio, quote.turnover_rate, quote.pe_ratio]
    filled = sum(1 for f in critical_fields if f is not None and f != 0)
    print(f"\n  结果：关键字段 {filled}/3 有值（量比、换手率、市盈率）")
    return filled >= 2


def run_level2_supplement(stock_code: str):
    """YFinance 行情 + 长桥补充字段。"""
    _print_header(f"级别 2：YFinance + 长桥补充 ({stock_code})")

    from data_provider.base import DataFetcherManager

    manager = DataFetcherManager()

    # 先只走 yfinance
    yf_quote = None
    for fetcher in manager._get_fetchers_snapshot():
        if fetcher.name == "YfinanceFetcher":
            try:
                yf_quote = fetcher.get_realtime_quote(stock_code)
            except Exception as e:
                print(f"  [x] YFinance 失败: {e}")
            break

    if yf_quote is None:
        print(f"  [x] YFinance 对 {stock_code} 返回 None")
    else:
        print(f"  YFinance 行情:")
        _print_field("price", yf_quote.price)
        _print_field("volume_ratio", yf_quote.volume_ratio)
        _print_field("turnover_rate", yf_quote.turnover_rate)
        _print_field("pe_ratio", yf_quote.pe_ratio)

    # 补充前打快照（合并会原地改 primary_quote，补充后再比会误判「无新字段」）
    _supp_fields = ["volume_ratio", "turnover_rate", "pe_ratio", "pb_ratio", "total_mv"]
    yf_snapshot = None
    if yf_quote is not None:
        yf_snapshot = {f: getattr(yf_quote, f, None) for f in _supp_fields}

    # 再走长桥补充
    result = manager._supplement_from_longbridge(stock_code, yf_quote)
    if result is None:
        print(f"\n  [x] 补充流程返回 None")
        return False

    print(f"\n  长桥补充后:")
    _print_field("price", result.price)
    _print_field("volume_ratio", result.volume_ratio)
    _print_field("turnover_rate", result.turnover_rate)
    _print_field("pe_ratio", result.pe_ratio)
    _print_field("pb_ratio", result.pb_ratio)
    _print_field("total_mv", result.total_mv)

    newly_filled = []
    if yf_snapshot is not None:
        for field in _supp_fields:
            old = yf_snapshot.get(field)
            new = getattr(result, field, None)
            if old is None and new is not None:
                newly_filled.append(field)
    if newly_filled:
        print(f"\n  [+] 长桥补全 {len(newly_filled)} 个字段: {newly_filled}")
    else:
        print(f"\n  [!] 无新增字段（长桥也可能缺数，或凭证未就绪）")
    return True


def run_level3_full_pipeline(stock_code: str):
    """完整 DataFetcherManager.get_realtime_quote 路径。"""
    _print_header(f"级别 3：完整 get_realtime_quote ({stock_code})")

    from data_provider.base import DataFetcherManager

    manager = DataFetcherManager()
    quote = manager.get_realtime_quote(stock_code)

    if quote is None:
        print(f"  [x] get_realtime_quote({stock_code}) 返回 None")
        return False

    print(f"  来源: {quote.source.value}")
    _print_field("price", quote.price)
    _print_field("volume_ratio", quote.volume_ratio)
    _print_field("turnover_rate", quote.turnover_rate)
    _print_field("pe_ratio", quote.pe_ratio)
    _print_field("total_mv", quote.total_mv)

    missing = []
    for field in ["volume_ratio", "turnover_rate", "pe_ratio"]:
        if getattr(quote, field, None) is None:
            missing.append(field)

    if missing:
        print(f"\n  [!] 仍缺字段: {missing}")
    else:
        print(f"\n  [+] 关键字段齐全")
    return len(missing) == 0


def run_level4_watchlist_groups(group_names_override: Optional[List[str]]) -> bool:
    """
    自选分组：列出账号下分组，并将指定分组映射为系统股票代码。
    未配置分组名时跳过（视为通过，不判失败）。
    """
    _print_header("级别 4：自选分组 -> 股票代码")

    from data_provider.longbridge_fetcher import (
        LongbridgeFetcher,
        fetch_stock_codes_for_watchlist_group_names,
    )

    fetcher = LongbridgeFetcher()
    if not fetcher._is_available():
        print("  [x] 未配置长桥凭证！")
        return False

    names: List[str] = list(group_names_override or [])
    if not names:
        raw = (os.getenv("LONGBRIDGE_WATCHLIST_GROUPS") or "").strip()
        names = [x.strip() for x in raw.split(",") if x.strip()]

    if not names:
        print(
            "  [!] 未指定分组名 — 请在 .env 设置 LONGBRIDGE_WATCHLIST_GROUPS，"
            "或使用 --watchlist-groups \"分组A,分组B\""
        )
        print("  级别 4 已跳过（不算失败）。")
        return True

    print(f"  请求的分组: {names!r}")

    try:
        ctx = fetcher._get_ctx()
        if ctx is not None:
            all_groups = ctx.watchlist()
            available = [getattr(g, "name", "?") for g in (all_groups or [])]
            print(f"  当前账号下的分组: {available}")
    except Exception as e:
        print(f"  [!] 列举 watchlist 失败: {e}")

    codes = fetch_stock_codes_for_watchlist_group_names(names, fetcher=fetcher)
    if not codes:
        print("  [x] 未得到任何代码 — 若分组名无误，请查看上方 [Longbridge] 日志是否连接失败")
        _print_longbridge_connect_troubleshoot()
        return False

    preview = ", ".join(codes[:24])
    if len(codes) > 24:
        preview += ", ..."
    print(f"  [+] 映射得到 {len(codes)} 个代码: {preview}")

    # 可选：与主程序相同的分析入口（需完整 Config；缺少可选依赖时可能跳过）
    try:
        from src.config import get_config

        cfg = get_config()
        cfg.refresh_stock_list()
        analysis_codes = cfg.get_stock_codes_for_analysis()
        print(f"  [+] get_stock_codes_for_analysis(): 共 {len(analysis_codes)} 个代码")
        if len(analysis_codes) <= 30:
            print(f"      {analysis_codes}")
    except Exception as e:
        print(f"  [!] get_stock_codes_for_analysis() 已跳过: {e}")

    return True


def _print_longbridge_connect_troubleshoot() -> None:
    """长桥 API 连不上时的中文排障提示（与 data_provider 内日志配合）。"""
    print(
        "  排障: 若日志中有 Connect / error sending request / openapi.longbridge —— "
        "在中国大陆网络请在 .env 设置 LONGBRIDGE_REGION=cn（使用 openapi.longbridge.cn）；"
        "使用代理时请检查 HTTP_PROXY 与 NO_PROXY 是否误拦长桥域名。"
    )


def _apply_cli_credentials(args: argparse.Namespace) -> None:
    """若三个参数齐全，则从命令行写入 LONGBRIDGE_*（在导入业务配置之前）。"""
    if args.lb_app_key and args.lb_app_secret and args.lb_access_token:
        os.environ["LONGBRIDGE_APP_KEY"] = args.lb_app_key
        os.environ["LONGBRIDGE_APP_SECRET"] = args.lb_app_secret
        os.environ["LONGBRIDGE_ACCESS_TOKEN"] = args.lb_access_token
    elif any((args.lb_app_key, args.lb_app_secret, args.lb_access_token)):
        print(
            "警告: --lb-app-key / --lb-app-secret / --lb-access-token 须同时使用，已忽略不完整参数。",
            file=sys.stderr,
        )


def main():
    # 输出 LongbridgeFetcher 的 WARNING，便于看到 quote/watchlist 失败原因
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s [%(name)s] %(message)s",
        force=True,
    )

    parser = argparse.ArgumentParser(description="长桥 OpenAPI 联调冒烟")
    parser.add_argument(
        "stock",
        nargs="?",
        default="AAPL",
        help="股票代码，例如 AAPL、00700、HK00700",
    )
    parser.add_argument(
        "--lb-app-key",
        "--lb-appkey",
        dest="lb_app_key",
        default=None,
        help="LONGBRIDGE_APP_KEY",
    )
    parser.add_argument("--lb-app-secret", dest="lb_app_secret", default=None, help="LONGBRIDGE_APP_SECRET")
    parser.add_argument(
        "--lb-access-token",
        dest="lb_access_token",
        default=None,
        help="LONGBRIDGE_ACCESS_TOKEN",
    )
    parser.add_argument(
        "--watchlist-groups",
        dest="watchlist_groups",
        default=None,
        metavar="名称列表",
        help="逗号分隔的自选分组名，用于级别 4（本次运行覆盖环境变量 LONGBRIDGE_WATCHLIST_GROUPS）",
    )
    args = parser.parse_args()
    stock = (args.stock or "AAPL").strip()

    _apply_cli_credentials(args)

    wl_names: Optional[List[str]] = None
    if args.watchlist_groups:
        wl_names = [x.strip() for x in args.watchlist_groups.split(",") if x.strip()]

    print("长桥联调冒烟")
    print(f"标的: {stock}")

    has_creds = bool(
        os.getenv("LONGBRIDGE_APP_KEY")
        and os.getenv("LONGBRIDGE_APP_SECRET")
        and os.getenv("LONGBRIDGE_ACCESS_TOKEN")
    )
    print(f"凭证: {'已配置' if has_creds else '未配置'}")

    results = {}
    results["L1"] = run_level1_standalone(stock)
    results["L2"] = run_level2_supplement(stock)
    results["L3"] = run_level3_full_pipeline(stock)
    results["L4"] = run_level4_watchlist_groups(wl_names)

    _print_header("汇总")
    for level, passed in results.items():
        mark = "[+]" if passed else "[x]"
        print(f"  {mark} {level}: {'通过' if passed else '失败'}")

    if all(results.values()):
        print("\n  全部级别通过，数据链路可用。")
    elif not has_creds:
        print("\n  请配置 LONGBRIDGE_* 环境变量或传入 --lb-* 后重试。")


if __name__ == "__main__":
    main()
