#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tushare gupiaoliebiaohuoqujiaoben

cong Tushare Pro huoqu Agu、ganggu、meiguliebiaoxinxi，baocunwei CSV wenjian

shiyongfangfa：
    python3 scripts/fetch_tushare_stock_list.py

huanjingyaoqiu：
    - xuyaozai .env zhongpeizhi TUSHARE_TOKEN
    - xuyaoanzhuang tushare: pip install tushare
    - zhanghaojifenyaoqiu：
        * Agu/ganggu：2000jifen
        * meigu：120jifenshiyong，5000jifenzhengshiquanxian

shuchuwenjian：
    - data/stock_list_a.csv      Aguliebiao
    - data/stock_list_hk.csv     gangguliebiao
    - data/stock_list_us.csv     meiguliebiao
    - data/README_stock_list.md  shujushuomingwendang
"""

import os
import sys
import time
import random
from pathlib import Path
from datetime import datetime
from typing import Optional

import pandas as pd
from dotenv import load_dotenv

# tianjiaxiangmugenmuludaolujing
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import tushare as ts
except ImportError:
    print("[cuowu] weianzhuang tushare ku")
    print("qingzhixing: pip install tushare")
    sys.exit(1)


# peizhi
load_dotenv()

TUSHARE_TOKEN = os.getenv('TUSHARE_TOKEN')
OUTPUT_DIR = Path(__file__).parent.parent / "data"
PAGE_SIZE = 5000  # meigumeiyeduqushuliang（API zuida6000，shezhi5000liuyuliang）
SLEEP_MIN = 5     # zuixiaoshuimianshijian（miao）
SLEEP_MAX = 10    # zuidashuimianshijian（miao）


def get_tushare_api() -> Optional[ts.pro_api]:
    """
    huoqu Tushare API shili

    Returns:
        Tushare API shili，shibaifanhui None
    """
    if not TUSHARE_TOKEN:
        print("[cuowu] weizhaodao TUSHARE_TOKEN")
        print("qingzai .env wenjianzhongpeizhi: TUSHARE_TOKEN=nidetoken")
        return None

    try:
        api = ts.pro_api(TUSHARE_TOKEN)
        # ceshilianjie
        api.trade_cal(exchange='SSE', start_date='20240101', end_date='20240101')
        print("✓ Tushare API lianjiechenggong")
        return api
    except Exception as e:
        print(f"[cuowu] Tushare API lianjieshibai: {e}")
        print("qingjiancha：")
        print("  1. TUSHARE_TOKEN shifouzhengque")
        print("  2. zhanghaojifenshifouzugou（Agu/gangguxuyao2000jifen）")
        return None


def random_sleep(min_seconds: int = SLEEP_MIN, max_seconds: int = SLEEP_MAX):
    """
    suijishuimian，bimianpinfanqingqiu

    Args:
        min_seconds: zuixiaoshuimianshijian
        max_seconds: zuidashuimianshijian
    """
    sleep_time = random.uniform(min_seconds, max_seconds)
    print(f"  ⏱  xiuxi {sleep_time:.1f} miao...")
    time.sleep(sleep_time)


def fetch_a_stock_list(api: ts.pro_api) -> Optional[pd.DataFrame]:
    """
    huoqu Aguliebiao

    jiekou：stock_basic
    xianliang：dancizuiduo6000xing（fugaiquanshichangAgu）

    Args:
        api: Tushare API shili

    Returns:
        Agushuju DataFrame，shibaifanhui None
    """
    print("\n[1/3] zhengzaihuoqu Aguliebiao...")

    try:
        # huoqusuoyouzhengchangshangshidegupiao
        df = api.stock_basic(
            exchange='',        # kong：quanbujiaoyisuo
            list_status='L',    # L: shangshi, D: tuishi, P: zantingshangshi
            fields='ts_code,symbol,name,area,industry,fullname,enname,cnspell,market,exchange,curr_type,list_status,list_date,delist_date,is_hs,act_name,act_ent_type'
        )

        if df is not None and len(df) > 0:
            print(f"✓ Aguliebiaohuoquchenggong，gong {len(df)} zhigupiao")
            print("  - jiaoyisuofenbu：")
            for exchange, count in df['exchange'].value_counts().items():
                print(f"    {exchange}: {count} zhi")
            return df
        else:
            print("[cuowu] Agushujuweikong")
            return None

    except Exception as e:
        print(f"[cuowu] huoqu Aguliebiaoshibai: {e}")
        return None


def fetch_hk_stock_list(api: ts.pro_api) -> Optional[pd.DataFrame]:
    """
    huoqugangguliebiao

    jiekou：hk_basic
    xianliang：danciketiququanbuzaijiaoyideganggu

    Args:
        api: Tushare API shili

    Returns:
        ganggushuju DataFrame，shibaifanhui None
    """
    print("\n[2/3] zhengzaihuoqugangguliebiao...")

    try:
        # huoqusuoyouzhengchangshangshideganggu
        df = api.hk_basic(
            list_status='L'    # L: shangshi, D: tuishi
        )

        if df is not None and len(df) > 0:
            print(f"✓ gangguliebiaohuoquchenggong，gong {len(df)} zhigupiao")
            return df
        else:
            print("[cuowu] ganggushujuweikong")
            return None

    except Exception as e:
        print(f"[cuowu] huoqugangguliebiaoshibai: {e}")
        return None


def fetch_us_stock_list(api: ts.pro_api) -> Optional[pd.DataFrame]:
    """
    huoqumeiguliebiao（fenyeduqu）

    jiekou：us_basic
    xianliang：dancizuida6000，xuyaofenyetiqu

    Args:
        api: Tushare API shili

    Returns:
        meigushuju DataFrame，shibaifanhui None
    """
    print("\n[3/3] zhengzaihuoqumeiguliebiao（fenyeduqu）...")

    all_data = []
    offset = 0
    page = 1

    try:
        while True:
            print(f"  di {page} ye（offset={offset}）...")

            df = api.us_basic(
                offset=offset,
                limit=PAGE_SIZE
            )

            if df is None or len(df) == 0:
                print(f"  ✓ di {page} yewushuju，duquwancheng")
                break

            all_data.append(df)
            print(f"  ✓ di {page} yehuoqu {len(df)} zhigupiao")

            # ruguofanhuishujushaoyuyedaxiao，shuomingyijingdaozuihouyiye
            if len(df) < PAGE_SIZE:
                break

            offset += PAGE_SIZE
            page += 1

            # suijixiuxi（zuihouyiyebuxuyaoxiuxi）
            random_sleep()

        if all_data:
            result_df = pd.concat(all_data, ignore_index=True)
            print(f"✓ meiguliebiaohuoquchenggong，gong {len(result_df)} zhigupiao（{page} ye）")

            # anfenleitongji
            if 'classify' in result_df.columns:
                print("  - fenleifenbu：")
                for classify, count in result_df['classify'].value_counts().items():
                    print(f"    {classify}: {count} zhi")

            return result_df
        else:
            print("[cuowu] meigushujuweikong")
            return None

    except Exception as e:
        print(f"[cuowu] huoqumeiguliebiaoshibai: {e}")
        return None


def save_to_csv(df: pd.DataFrame, filename: str, market_name: str) -> bool:
    """
    baocunshujudao CSV wenjian

    Args:
        df: shuju DataFrame
        filename: wenjianming
        market_name: shichangmingcheng（yongyurizhi）

    Returns:
        shifoubaocunchenggong
    """
    if df is None or len(df) == 0:
        print(f"[tiaoguo] {market_name} shujuweikong，bubaocunwenjian")
        return False

    try:
        output_path = OUTPUT_DIR / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        df.to_csv(output_path, index=False, encoding='utf-8-sig')

        file_size = output_path.stat().st_size / 1024  # KB
        print(f"✓ {market_name} shujuyibaocun：{output_path} ({file_size:.2f} KB)")
        return True

    except Exception as e:
        print(f"[cuowu] baocun {market_name} shujushibai: {e}")
        return False


def generate_data_documentation(
    a_df: Optional[pd.DataFrame],
    hk_df: Optional[pd.DataFrame],
    us_df: Optional[pd.DataFrame]
):
    """
    shengchengshujushuomingwendang

    Args:
        a_df: Agushuju
        hk_df: ganggushuju
        us_df: meigushuju
    """
    doc_path = OUTPUT_DIR / "README_stock_list.md"

    content = f"""# Tushare gupiaoliebiaoshujushuoming

> shujulaiyuan：[Tushare Pro](https://tushare.pro)
> shengchengshijian：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## wenjianshuoming

| wenjian | shuoming | jilushu |
|------|------|--------|
| `stock_list_a.csv` | Aguliebiao | {len(a_df) if a_df is not None else 0} |
| `stock_list_hk.csv` | gangguliebiao | {len(hk_df) if hk_df is not None else 0} |
| `stock_list_us.csv` | meiguliebiao | {len(us_df) if us_df is not None else 0} |

---

## Agushuju（stock_list_a.csv）

### shujujiekou
- **jiekoumingcheng**：`stock_basic`
- **shujuquanxian**：2000jifenqi，meifenzhongqingqiu50ci
- **shujuxianliang**：dancizuiduo6000xing（fugaiquanshichangAgu）

### ziduanshuoming

| ziduanming | leixing | shuoming | shili |
|--------|------|------|------|
| ts_code | str | TSdaima | 000001.SZ |
| symbol | str | gupiaodaima | 000001 |
| name | str | gupiaomingcheng | pinganyinhang |
| area | str | diyu | shenzhen |
| industry | str | suoshuhangye | yinhang |
| fullname | str | gupiaoquancheng | pinganyinhanggufenyouxiangongsi |
| enname | str | yingwenquancheng | Ping An Bank Co., Ltd. |
| cnspell | str | pinyinsuoxie | PAYH |
| market | str | shichangleixing | zhuban/chuangyeban/kechuangban/CDR |
| exchange | str | jiaoyisuodaima | SSEshangjiaosuo/SZSEshenjiaosuo/BSEbeijiaosuo |
| curr_type | str | jiaoyihuobi | CNY |
| list_status | str | shangshizhuangtai | Lshangshi/Dtuishi/Pzantingshangshi |
| list_date | str | shangshiriqi | 19910403 |
| delist_date | str | tuishiriqi | - |
| is_hs | str | shifouhushengangtongbiaodi | Nfou/Hhugutong/Sshengutong |
| act_name | str | shikongrenmingcheng | - |
| act_ent_type | str | shikongrenqiyexingzhi | - |

### shujuyangli
```csv
ts_code,symbol,name,area,industry,fullname,enname,cnspell,market,exchange,curr_type,list_status,list_date,delist_date,is_hs,act_name,act_ent_type
000001.SZ,000001,pinganyinhang,shenzhen,yinhang,pinganyinhanggufenyouxiangongsi,Ping An Bank Co., Ltd.,PAYH,zhuban,SZSE,CNY,L,19910403,,S,,
000002.SZ,000002,wankeA,shenzhen,quanguodichan,wankeqiyegufenyouxiangongsi,China Vanke Co., Ltd.,ZKA,zhuban,SZSE,CNY,L,19910129,,S,,
```

---

## ganggushuju（stock_list_hk.csv）

### shujujiekou
- **jiekoumingcheng**：`hk_basic`
- **shujuquanxian**：yonghuxuyaozhishao2000jifencaikeyidiaoqu
- **shujuxianliang**：danciketiququanbuzaijiaoyidegangguliebiaoshuju

### ziduanshuoming

| ziduanming | leixing | shuoming | shili |
|--------|------|------|------|
| ts_code | str | TSdaima | 00001.HK |
| name | str | gupiaojiancheng | zhanghe |
| fullname | str | gongsiquancheng | changjianghejishiyeyouxiangongsi |
| enname | str | yingwenmingcheng | CK Hutchison Holdings Ltd. |
| cn_spell | str | pinyin | ZH |
| market | str | shichangleibie | zhuban/chuangyeban |
| list_status | str | shangshizhuangtai | Lshangshi/Dtuishi/Pzantingshangshi |
| list_date | str | shangshiriqi | 19720731 |
| delist_date | str | tuishiriqi | - |
| trade_unit | float | jiaoyidanwei | 1000 |
| isin | str | ISINdaima | KYG217651051 |
| curr_type | str | huobidaima | HKD |

### shujuyangli
```csv
ts_code,name,fullname,enname,cn_spell,market,list_status,list_date,delist_date,trade_unit,isin,curr_type
00001.HK,zhanghe,changjianghejishiyeyouxiangongsi,CK Hutchison Holdings Ltd.,ZH,zhuban,L,19720731,,1000,KYG217651051,HKD
00002.HK,zhongdiankonggu,zhonghuadianliyouxiangongsi,CLP Holdings Ltd.,ZDKG,zhuban,L,19860125,,1000,HK0002007356,HKD
```

---

## meigushuju（stock_list_us.csv）

### shujujiekou
- **jiekoumingcheng**：`us_basic`
- **shujuquanxian**：120jifenkeyishiyong，5000jifenyouzhengshiquanxian
- **shujuxianliang**：dancizuida6000，kefenyetiqu

### ziduanshuoming

| ziduanming | leixing | shuoming | shili |
|--------|------|------|------|
| ts_code | str | meigudaima | AAPL |
| name | str | zhongwenmingcheng | pingguo |
| enname | str | yingwenmingcheng | Apple Inc. |
| classify | str | fenlei | ADR/GDR/EQT |
| list_date | str | shangshiriqi | 19801212 |
| delist_date | str | tuishiriqi | - |

### fenleishuoming
- **ADR**：meiguocuntuopingzheng（American Depositary Receipt）
- **GDR**：quanqiucuntuopingzheng（Global Depositary Receipt）
- **EQT**：putonggu（Equity）

### shujuyangli
```csv
ts_code,name,enname,classify,list_date,delist_date
AAPL,pingguo,Apple Inc.,EQT,19801212,
TSLA,tesila,Tesla Inc.,EQT,20100629,
BABA,alibaba,Alibaba Group Holding Ltd.,ADR,20140919,
```

---

## shiyongshuoming

### duqushuju

```python
import pandas as pd

# duqu Agushuju
a_stocks = pd.read_csv('data/stock_list_a.csv')

# duquganggushuju
hk_stocks = pd.read_csv('data/stock_list_hk.csv')

# duqumeigushuju
us_stocks = pd.read_csv('data/stock_list_us.csv')
```

### daimageshishuoming

**Agudaimageshi**：
- hushi：`600000.SH`（zhuban）、`688xxx.SH`（kechuangban）、`900xxx.SH`（Bgu）
- shenshi：`000001.SZ`（zhuban）、`300xxx.SZ`（chuangyeban）、`200xxx.SZ`（Bgu）
- beijiaosuo：`8xxxxx.BJ`、`4xxxxx.BJ`、`920xxx.BJ`

**ganggudaimageshi**：
- geshi：`xxxxx.HK`（5weishuzi + .HK）
- shili：`00700.HK`（tengxunkonggu）

**meigudaimageshi**：
- geshi：daimazimu（wuhouzhui）
- shili：`AAPL`（pingguo）、`TSLA`（tesila）

---

## zhuyishixiang

1. **shujugengxin**：jianyidingqigengxinshuju（rumeiyueyici）
2. **jifenyaoqiu**：
   - Agu/ganggu：xuyao2000jifen
   - meigu：120jifenshiyong，5000jifenzhengshiquanxian
3. **qingqiuxianzhi**：zhuyi API demeifenzhongqingqiucishuxianzhi
4. **shujuwanzhengxing**：benshujujinbaohanjichuxinxi，ruxugengduoshujuqingcankao Tushare guanfangwendang

---

## xiangguanlianjie

- [Tushare guanwang](https://tushare.pro)
- [Tushare wendang](https://tushare.pro/document/2)
- [jifenhuoqubanfa](https://tushare.pro/document/1)
- [API shujutiaoshi](https://tushare.pro/document/2)
"""

    try:
        with open(doc_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ shujushuomingwendangyishengcheng：{doc_path}")
    except Exception as e:
        print(f"[cuowu] shengchengshuomingwendangshibai: {e}")


def main():
    """zhuhanshu"""
    print("=" * 60)
    print("Tushare gupiaoliebiaohuoqugongju")
    print("=" * 60)

    # 1. huoqu API shili
    api = get_tushare_api()
    if not api:
        return 1

    # 2. huoqu Agushuju
    a_df = fetch_a_stock_list(api)
    if a_df is not None:
        save_to_csv(a_df, 'stock_list_a.csv', 'Agu')

    # 3. huoquganggushuju
    random_sleep()  # xiuxihouzaihuoquganggu
    hk_df = fetch_hk_stock_list(api)
    if hk_df is not None:
        save_to_csv(hk_df, 'stock_list_hk.csv', 'ganggu')

    # 4. huoqumeigushuju（fenye）
    random_sleep()  # xiuxihouzaihuoqumeigu
    us_df = fetch_us_stock_list(api)
    if us_df is not None:
        save_to_csv(us_df, 'stock_list_us.csv', 'meigu')

    # 5. shengchengshujushuomingwendang
    print("\nzhengzaishengchengshujushuomingwendang...")
    generate_data_documentation(a_df, hk_df, us_df)

    # 6. zongjie
    print("\n" + "=" * 60)
    print("renwuwancheng！")
    print("=" * 60)

    total_count = 0
    if a_df is not None:
        total_count += len(a_df)
        print(f"  ✓ Agu：{len(a_df)} zhi")
    if hk_df is not None:
        total_count += len(hk_df)
        print(f"  ✓ ganggu：{len(hk_df)} zhi")
    if us_df is not None:
        total_count += len(us_df)
        print(f"  ✓ meigu：{len(us_df)} zhi")

    print(f"\nzongji：{total_count} zhigupiao")
    print(f"shuchumulu：{OUTPUT_DIR}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n[zhongduan] yonghuquxiaocaozuo")
        sys.exit(1)
    except Exception as e:
        print(f"\n[cuowu] weiyuqideyichang: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
