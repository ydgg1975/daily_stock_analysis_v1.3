# -*- coding: utf-8 -*-
"""
===================================
Aguzixuanguzhinengfenxixitong - huanjingyanzhengceshi
===================================

yongyuyanzheng .env peizhishifouzhengque，baokuo：
1. peizhijiazaiceshi
2. shujukuchakan
3. shujuyuanceshi
4. LLM diaoyongceshi
5. tongzhituisongceshi

shiyongfangfa：
    python scripts/check_env.py              # yunxingsuoyouceshi
    python scripts/check_env.py --db         # jinchakanshujuku
    python scripts/check_env.py --llm        # jinceshi LLM
    python scripts/check_env.py --fetch      # jinceshishujuhuoqu
    python scripts/check_env.py --notify     # jinceshitongzhi

"""
import os
# Proxy config - controlled by USE_PROXY env var, off by default.
# Set USE_PROXY=true in .env if you need a local proxy (e.g. mainland China).
# GitHub Actions always skips this regardless of USE_PROXY.
if os.getenv("GITHUB_ACTIONS") != "true" and os.getenv("USE_PROXY", "false").lower() == "true":
    proxy_host = os.getenv("PROXY_HOST", "127.0.0.1")
    proxy_port = os.getenv("PROXY_PORT", "10809")
    proxy_url = f"http://{proxy_host}:{proxy_port}"
    os.environ["http_proxy"] = proxy_url
    os.environ["https_proxy"] = proxy_url

import argparse
import logging
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# peizhirizhi
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def print_header(title: str):
    """dayinbiaoti"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_section(title: str):
    """dayinxiaojie"""
    print(f"\n--- {title} ---")


def check_config():
    """ceshipeizhijiazai"""
    print_header("1. peizhijiazaiceshi")
    
    from src.config import get_config
    config = get_config()
    
    print_section("jichupeizhi")
    print(f"  gupiaoliebiao: {config.stock_list}")
    print(f"  shujukulujing: {config.database_path}")
    print(f"  zuidabingfashu: {config.max_workers}")
    print(f"  tiaoshimoshi: {config.debug}")
    
    print_section("API peizhi")
    print(f"  Tushare Token: {'yipeizhi ✓' if config.tushare_token else 'weipeizhi ✗'}")
    if config.tushare_token:
        print(f"    Token qian8wei: {config.tushare_token[:8]}...")
    
    print(f"  Gemini API Key: {'yipeizhi ✓' if config.gemini_api_key else 'weipeizhi ✗'}")
    if config.gemini_api_key:
        print(f"    Key qian8wei: {config.gemini_api_key[:8]}...")
    print(f"  Gemini zhumoxing: {config.gemini_model}")
    print(f"  Gemini beixuanmoxing: {config.gemini_model_fallback}")
    
    print(f"  qiyeweixin Webhook: {'yipeizhi ✓' if config.wechat_webhook_url else 'weipeizhi ✗'}")
    
    print_section("peizhiyanzheng")
    issues = config.validate_structured()
    _prefix = {"error": "  ✗", "warning": "  ⚠", "info": "  ·"}
    for issue in issues:
        print(f"{_prefix.get(issue.severity, '  ?')} [{issue.severity.upper()}] {issue.message}")
    if not any(i.severity in ("error", "warning") for i in issues):
        print("  ✓ guanjianpeizhixiangyanzhengtongguo")
    
    return True


def view_database():
    """chakanshujukuneirong"""
    print_header("2. shujukuneirongchakan")
    
    from src.storage import get_db
    from sqlalchemy import text
    
    db = get_db()
    
    print_section("shujukulianjie")
    print(f"  ✓ lianjiechenggong")
    
    # shiyongdulide session chaxun
    session = db.get_session()
    try:
        # tongjixinxi
        result = session.execute(text("""
            SELECT 
                code,
                COUNT(*) as count,
                MIN(date) as min_date,
                MAX(date) as max_date,
                data_source
            FROM stock_daily 
            GROUP BY code
            ORDER BY code
        """))
        stocks = result.fetchall()
        
        print_section(f"yicunchugupiaoshuju (gong {len(stocks)} zhi)")
        if stocks:
            print(f"  {'daima':<10} {'jilushu':<8} {'qishiriqi':<12} {'zuixinriqi':<12} {'shujuyuan'}")
            print("  " + "-" * 60)
            for row in stocks:
                print(f"  {row[0]:<10} {row[1]:<8} {row[2]!s:<12} {row[3]!s:<12} {row[4] or 'Unknown'}")
        else:
            print("  zanwushuju")
        
        # chaxunjinrishuju
        today = date.today()
        result = session.execute(text("""
            SELECT code, date, open, high, low, close, pct_chg, volume, ma5, ma10, ma20, volume_ratio
            FROM stock_daily 
            WHERE date = :today
            ORDER BY code
        """), {"today": today})
        today_data = result.fetchall()
        
        print_section(f"jinrishuju ({today})")
        if today_data:
            for row in today_data:
                code, dt, open_, high, low, close, pct_chg, volume, ma5, ma10, ma20, vol_ratio = row
                print(f"\n  【{code}】")
                print(f"    kaipan: {open_:.2f}  zuigao: {high:.2f}  zuidi: {low:.2f}  shoupan: {close:.2f}")
                print(f"    zhangdiefu: {pct_chg:.2f}%  chengjiaoliang: {volume/10000:.2f}wangu")
                print(f"    MA5: {ma5:.2f}  MA10: {ma10:.2f}  MA20: {ma20:.2f}  liangbi: {vol_ratio:.2f}")
        else:
            print("  jinrizanwushuju")
        
        # chaxunzuijin10tiaoshuju
        result = session.execute(text("""
            SELECT code, date, close, pct_chg, volume, data_source
            FROM stock_daily 
            ORDER BY date DESC, code
            LIMIT 10
        """))
        recent = result.fetchall()
        
        print_section("zuijin10tiaojilu")
        if recent:
            print(f"  {'daima':<10} {'riqi':<12} {'shoupan':<10} {'zhangdie%':<8} {'chengjiaoliang':<15} {'laiyuan'}")
            print("  " + "-" * 70)
            for row in recent:
                vol_str = f"{row[4]/10000:.2f}wan" if row[4] else "N/A"
                print(f"  {row[0]:<10} {row[1]!s:<12} {row[2]:<10.2f} {row[3]:<8.2f} {vol_str:<15} {row[5] or 'Unknown'}")
    finally:
        session.close()
    
    return True


def check_data_fetch(stock_code: str = "600519"):
    """ceshishujuhuoqu"""
    print_header("3. shujuhuoquceshi")
    
    from data_provider import DataFetcherManager
    
    manager = DataFetcherManager()
    
    print_section("shujuyuanliebiao")
    for i, name in enumerate(manager.available_fetchers, 1):
        print(f"  {i}. {name}")
    
    print_section(f"huoqu {stock_code} shuju")
    print(f"  zhengzaihuoqu（kenengxuyaojimiaozhong）...")
    
    try:
        df, source = manager.get_daily_data(stock_code, days=5)
        
        print(f"  ✓ huoquchenggong")
        print(f"    shujuyuan: {source}")
        print(f"    jilushu: {len(df)}")
        
        print_section("shujuyulan（zuijin5tiao）")
        if not df.empty:
            preview_cols = ['date', 'open', 'high', 'low', 'close', 'pct_chg', 'volume']
            existing_cols = [c for c in preview_cols if c in df.columns]
            print(df[existing_cols].tail().to_string(index=False))
        
        return True
        
    except Exception as e:
        print(f"  ✗ huoqushibai: {e}")
        return False


def check_llm():
    """ceshi LLM diaoyong"""
    print_header("4. LLM (Gemini) diaoyongceshi")
    
    from src.analyzer import GeminiAnalyzer
    from src.config import get_config
    import time
    
    config = get_config()
    
    print_section("moxingpeizhi")
    print(f"  zhumoxing: {config.gemini_model}")
    print(f"  beixuanmoxing: {config.gemini_model_fallback}")
    
    # jianchawangluolianjie
    print_section("wangluolianjiejiancha")
    try:
        import socket
        socket.setdefaulttimeout(10)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("generativelanguage.googleapis.com", 443))
        print(f"  ✓ keyilianjiedao Google API fuwuqi")
    except Exception as e:
        print(f"  ✗ wufalianjiedao Google API fuwuqi: {e}")
        print(f"  tishi: qingjianchawangluolianjiehuopeizhidaili")
        print(f"  tishi: keyishezhihuanjingbianliang HTTPS_PROXY=http://your-proxy:port")
        return False
    
    analyzer = GeminiAnalyzer()
    
    print_section("moxingchushihua")
    if analyzer.is_available():
        print(f"  ✓ moxingchushihuachenggong")
    else:
        print(f"  ✗ moxingchushihuashibai（qingjiancha API Key）")
        return False
    
    # gouzaoceshishangxiawen
    test_context = {
        'code': '600519',
        'date': date.today().isoformat(),
        'today': {
            'open': 1420.0,
            'high': 1435.0,
            'low': 1415.0,
            'close': 1428.0,
            'volume': 5000000,
            'amount': 7140000000,
            'pct_chg': 0.56,
            'ma5': 1425.0,
            'ma10': 1418.0,
            'ma20': 1410.0,
            'volume_ratio': 1.1,
        },
        'ma_status': 'duotoupailie 📈',
        'volume_change_ratio': 1.05,
        'price_change_ratio': 0.56,
    }
    
    print_section("fasongceshiqingqiu")
    print(f"  ceshigupiao: guizhoumaotai (600519)")
    print(f"  zhengzaidiaoyong Gemini API（chaoshi: 60miao）...")
    
    start_time = time.time()
    
    try:
        result = analyzer.analyze(test_context)
        
        elapsed = time.time() - start_time
        print(f"\n  ✓ API diaoyongchenggong (haoshi: {elapsed:.2f}miao)")
        
        print_section("fenxijieguo")
        print(f"  qingxupingfen: {result.sentiment_score}/100")
        print(f"  qushiyuce: {result.trend_prediction}")
        print(f"  caozuojianyi: {result.operation_advice}")
        print(f"  jishufenxi: {result.technical_analysis[:80]}..." if len(result.technical_analysis) > 80 else f"  jishufenxi: {result.technical_analysis}")
        print(f"  xiaoximian: {result.news_summary[:80]}..." if len(result.news_summary) > 80 else f"  xiaoximian: {result.news_summary}")
        print(f"  zonghezhaiyao: {result.analysis_summary}")
        
        if not result.success:
            print(f"\n  ⚠ zhuyi: {result.error_message}")
        
        return result.success
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n  ✗ API diaoyongshibai (haoshi: {elapsed:.2f}miao)")
        print(f"  cuowu: {e}")
        
        # tigonggengxiangxidecuowutishi
        error_str = str(e).lower()
        if 'timeout' in error_str or 'unavailable' in error_str:
            print(f"\n  zhenduan: wangluochaoshi，kenengyuanyin:")
            print(f"    1. wangluobutong（xuyaodailifangwen Google）")
            print(f"    2. API fuwuzanshibukeyong")
            print(f"    3. qingqiuliangguodabeixianliu")
        elif 'invalid' in error_str or 'api key' in error_str:
            print(f"\n  zhenduan: API Key kenengwuxiao")
        elif 'model' in error_str:
            print(f"\n  zhenduan: moxingmingchengkenengbuzhengque，changshixiugai .env zhongde GEMINI_MODEL")
        
        return False


def check_notification():
    """ceshitongzhituisong"""
    print_header("5. tongzhituisongceshi")
    
    from src.notification import NotificationService
    from src.config import get_config
    
    config = get_config()
    service = NotificationService()
    
    print_section("peizhijiancha")
    if service.is_available():
        print(f"  ✓ qiyeweixin Webhook yipeizhi")
        webhook_preview = config.wechat_webhook_url[:50] + "..." if len(config.wechat_webhook_url) > 50 else config.wechat_webhook_url
        print(f"    URL: {webhook_preview}")
    else:
        print(f"  ✗ qiyeweixin Webhook weipeizhi")
        return False
    
    print_section("fasongceshixiaoxi")
    
    test_message = f"""## 🧪 xitongceshixiaoxi

zheshiyitiaolaizi **Aguzixuanguzhinengfenxixitong** deceshixiaoxi。

- ceshishijian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- ceshimudi: yanzhengqiyeweixin Webhook peizhi

ruguoninshoudaocixiaoxi，shuomingtongzhigongnengpeizhizhengque ✓"""
    
    print(f"  zhengzaifasong...")
    
    try:
        success = service.send_to_wechat(test_message)
        
        if success:
            print(f"  ✓ xiaoxifasongchenggong，qingjianchaqiyeweixin")
        else:
            print(f"  ✗ xiaoxifasongshibai")
        
        return success
        
    except Exception as e:
        print(f"  ✗ fasongyichang: {e}")
        return False


def run_all_tests():
    """yunxingsuoyouceshi"""
    print("\n" + "🚀" * 20)
    print("  Aguzixuanguzhinengfenxixitong - huanjingyanzheng")
    print("  " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("🚀" * 20)
    
    results = {}
    
    # 1. peizhiceshi
    try:
        results['peizhijiazai'] = check_config()
    except Exception as e:
        print(f"  ✗ peizhiceshishibai: {e}")
        results['peizhijiazai'] = False
    
    # 2. shujukuchakan
    try:
        results['shujuku'] = view_database()
    except Exception as e:
        print(f"  ✗ shujukuceshishibai: {e}")
        results['shujuku'] = False
    
    # 3. shujuhuoqu（tiaoguo，bimiantaiman）
    # results['shujuhuoqu'] = check_data_fetch()
    
    # 4. LLM ceshi（kexuan）
    # results['LLMdiaoyong'] = check_llm()
    
    # huizong
    print_header("ceshijieguohuizong")
    for name, passed in results.items():
        status = "✓ tongguo" if passed else "✗ shibai"
        print(f"  {status}: {name}")
    
    print(f"\ntishi: shiyong --llm canshudanduceshi LLM diaoyong")
    print(f"tishi: shiyong --fetch canshudanduceshishujuhuoqu")
    print(f"tishi: shiyong --notify canshudanduceshitongzhituisong")


def query_stock_data(stock_code: str, days: int = 10):
    """chaxunzhidinggupiaodeshuju"""
    print_header(f"chaxungupiaoshuju: {stock_code}")
    
    from src.storage import get_db
    from sqlalchemy import text
    
    db = get_db()
    
    session = db.get_session()
    try:
        result = session.execute(text("""
            SELECT date, open, high, low, close, pct_chg, volume, amount, ma5, ma10, ma20, volume_ratio
            FROM stock_daily 
            WHERE code = :code
            ORDER BY date DESC
            LIMIT :limit
        """), {"code": stock_code, "limit": days})
        
        rows = result.fetchall()
        
        if rows:
            print(f"\n  zuijin {len(rows)} tiaojilu:\n")
            print(f"  {'riqi':<12} {'kaipan':<10} {'zuigao':<10} {'zuidi':<10} {'shoupan':<10} {'zhangdie%':<8} {'MA5':<10} {'MA10':<10} {'liangbi':<8}")
            print("  " + "-" * 100)
            for row in rows:
                dt, open_, high, low, close, pct_chg, vol, amt, ma5, ma10, ma20, vol_ratio = row
                print(f"  {dt!s:<12} {open_:<10.2f} {high:<10.2f} {low:<10.2f} {close:<10.2f} {pct_chg:<8.2f} {ma5:<10.2f} {ma10:<10.2f} {vol_ratio:<8.2f}")
        else:
            print(f"  weizhaodao {stock_code} deshuju")
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(
        description='Aguzixuanguzhinengfenxixitong - huanjingyanzhengceshi',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument('--db', action='store_true', help='chakanshujukuneirong')
    parser.add_argument('--llm', action='store_true', help='ceshi LLM diaoyong')
    parser.add_argument('--fetch', action='store_true', help='ceshishujuhuoqu')
    parser.add_argument('--notify', action='store_true', help='ceshitongzhituisong')
    parser.add_argument('--config', action='store_true', help='chakanpeizhi')
    parser.add_argument('--stock', type=str, help='chaxunzhidinggupiaoshuju，ru --stock 600519')
    parser.add_argument('--all', action='store_true', help='yunxingsuoyouceshi（baokuo LLM）')
    
    args = parser.parse_args()
    
    # ruguomeiyouzhidingrenhecanshu，yunxingjichuceshi
    if not any([args.db, args.llm, args.fetch, args.notify, args.config, args.stock, args.all]):
        run_all_tests()
        return 0
    
    # genjucanshuyunxingzhidingceshi
    if args.config:
        check_config()
    
    if args.db:
        view_database()
    
    if args.stock:
        query_stock_data(args.stock)
    
    if args.fetch:
        check_data_fetch()
    
    if args.llm:
        check_llm()
    
    if args.notify:
        check_notification()
    
    if args.all:
        check_config()
        view_database()
        check_data_fetch()
        check_llm()
        check_notification()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
