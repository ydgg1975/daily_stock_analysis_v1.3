---
name: "stock_analyzer"
description: "fenxigupiaoheshichang。dangyonghuxiangyaofenxidangehuoduogegupiao，huojinhangshichangfupanshidiaoyong。"
---

# gupiaofenxiqi

benjinengjiyu `src/services/analyzer_service.py` deluoji，tigongfenxigupiaohezhengtishichangdegongneng。

## shuchujiegou (`AnalysisResult`)

fenxihanshufanhuiyige `AnalysisResult` duixiang（huoqiliebiao），gaiduixiangjuyoufengfudejiegou。yixiashiqiguanjianzujiandejianyaogaishu，bingfuyouzhenshideshuchushili：

`dashboard` shuxingbaohanhexinfenxi，fenweisigezhuyaobufen：
1.  **`core_conclusion`**: yijuhuazongjie、xinhaoleixinghecangweijianyi。
2.  **`data_perspective`**: jishushuju，baokuoqushizhuangtai、jiageweizhi、liangnengfenxihechoumajiegou。
3.  **`intelligence`**: dingxingxinxi，ruxinwen、fengxianjingbaohejijicuihuaji。
4.  **`battle_plan`**: kecaozuodecelve，baokuojujidian（mai/maimubiao）、cangweicelvehefengxiankongzhiqingdan。

## peizhi (`Config`)

suoyoufenxihanshudoukeyijieshouyigekexuande `config` duixiang。gaiduixiangbaohanyingyongchengxudesuoyoupeizhi，liru API miyao、tongzhishezhihefenxicanshu。

ruguoweitigong `config` duixiang，hanshujiangzidongshiyongcong `.env` wenjianjiazaidequanjudanlishili。

**cankao:** [`Config`](src/config.py)

## hanshu

### 1. fenxidanzhigupiao

**miaoshu:** fenxidanzhigupiaobingfanhuifenxijieguo。

**heshishiyong:** dangyonghuyaoqiufenxitedinggupiaoshi。

**shuru:**
- `stock_code` (str): yaofenxidegupiaodaima。
- `config` (Config, kexuan): peizhiduixiang。morenwei `None`。
- `full_report` (bool, kexuan): shifoushengchengwanzhengbaogao。morenwei `False`。
- `notifier` (NotificationService, kexuan): tongzhifuwuduixiang。morenwei `None`。

**shuchu:** `Optional[AnalysisResult]`
yigebaohanfenxijieguode `AnalysisResult` duixiang，ruguofenxishibaizewei `None`。

**shili:**

```python
from src.services.analyzer_service import analyze_stock

# fenxidanzhigupiao
result = analyze_stock("600989")
if result:
    print(f"gupiao: {result.name} ({result.code})")
    print(f"qingxudefen: {result.sentiment_score}")
    print(f"caozuojianyi: {result.operation_advice}")
```

**cankao:** [`analyze_stock`](src/services/analyzer_service.py)

### 2. fenxiduozhigupiao

**miaoshu:** fenxiyigegupiaoliebiaobingfanhuifenxijieguoliebiao。

**heshishiyong:** dangyonghuxiangyaoyicifenxiduozhigupiaoshi。

**shuru:**
- `stock_codes` (List[str]): yaofenxidegupiaodaimaliebiao。
- `config` (Config, kexuan): peizhiduixiang。morenwei `None`。
- `full_report` (bool, kexuan): shifouweimeizhigupiaoshengchengwanzhengbaogao。morenwei `False`。
- `notifier` (NotificationService, kexuan): tongzhifuwuduixiang。morenwei `None`。

**shuchu:** `List[AnalysisResult]`
yige `AnalysisResult` duixiangliebiao。

**shili:**

```python
from src.services.analyzer_service import analyze_stocks

# fenxiduozhigupiao
results = analyze_stocks(["600989", "000001"])
for result in results:
    print(f"gupiao: {result.name}, caozuojianyi: {result.operation_advice}")
```

**cankao:** [`analyze_stocks`](src/services/analyzer_service.py)


### 3. zhixingdapanfupan

**miaoshu:** duizhengtishichangjinxingfupanbingfanhuiyifenbaogao。

**heshishiyong:** dangyonghuyaoqiushichanggailan、zhaiyaohuofupanshi。

**shuru:**
- `config` (Config, kexuan): peizhiduixiang。morenwei `None`。
- `notifier` (NotificationService, kexuan): tongzhifuwuduixiang。morenwei `None`。

**shuchu:** `Optional[str]`
yigebaohanshichangfupanbaogaodezifuchuan，ruguoshibaizewei `None`。

**shili:**

```python
from src.services.analyzer_service import perform_market_review

# zhixingdapanfupan
report = perform_market_review()
if report:
    print(report)
```

**cankao:** [`perform_market_review`](src/services/analyzer_service.py)
