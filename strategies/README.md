# jiaoyicelvemulu / Trading Strategies

benmulucunfang **ziranyuyanjiaoyicelvewenjian**（YAML geshi）。xitongqidongshizidongjiazaicimuluxiasuoyou `.yaml` wenjian。

duiyonghuhewendang，womenjixubazhexienenglichengwei“celve”；zaidaima、peizhihe API ziduanli，tamentongyimingmingwei `skill`，nikeyibatalijiewei“kefuyongdecelvenenglibao”。

## ruhebianxiezidingyicelve（Strategy Skill）

zhixuchuangjianyige `.yaml` wenjian，yongzhongwen（huorenyiyuyan）miaoshunidejiaoyicelvejike，**wuxubianxierenhedaima**。

### zuijianmuban

```yaml
name: my_strategy          # weiyibiaoshi（yingwen，xiahuaxianlianjie）
display_name: wodecelve      # xianshimingcheng（zhongwen）
description: jianduanmiaoshucelveyongtu

instructions: |
  nidecelvemiaoshu...
  yongziranyuyanxiechupanduanbiaozhun、ruchangtiaojian、chuchangtiaojiandeng。
  keyiyinyonggongjumingcheng（ru get_daily_history、analyze_trend）laizhidao AI shiyongnaxieshuju。
```

### wanzhengmuban

```yaml
name: my_strategy
display_name: wodecelve
description: jianduanmiaoshucelveshiyongdeshichangchangjing

# celvefenlei：trend（qushi）、pattern（xingtai）、reversal（fanzhuan）、framework（kuangjia）
category: trend

# guanliandehexinjiaoyilinianbianhao（1-7），kexuan
core_rules: [1, 2]

# celvexuyaoshiyongdegongjuliebiao，kexuan
# keyonggongju：get_daily_history, analyze_trend, get_realtime_quote,
#           get_sector_rankings, search_stock_news, get_stock_info
required_tools:
  - get_daily_history
  - analyze_trend

# kexuanbieming（yongyu /ask dengziranyuyanjinengxuanze）
aliases: [wodezhanfa, wodemoxing]

# yixiayuanshujuyongyuqudongmorenxingwei（kexuan）
# default_active: shifoushuyumorenjihuojinengji
# default_router: shifoushuyuluyou fallback jinengji
# default_priority: morenzhanshi/paixuyouxianji，shuzhiyuexiaoyuekaoqian
# market_regimes: gaijinengyouxianshipeideshichangzhuangtaibiaoqian
default_active: true
default_router: false
default_priority: 100
market_regimes: [trending_up]

# celvexiangxishuoming（ziranyuyan，zhichi Markdown geshi）
instructions: |
  **wodecelvemingcheng**

  panduanbiaozhun：

  1. **tiaojianyi**：
     - shiyong `analyze_trend` jianchajunxianpailie。
     - miaoshuniqiwangkandaodequshitezheng...

  2. **tiaojianer**：
     - miaoshuliangnengyaoqiu...

  pingfentiaozheng：
  - manzutiaojianshijianyide sentiment_score tiaozheng
  - zai `buy_reason` zhongzhumingcelvemingcheng
```

### hexinjiaoyiliniancankao

| bianhao | linian |
|------|------|
| 1 | yanjincelve：guaililv < 5% caikaolvruchang |
| 2 | qushijiaoyi：MA5 > MA10 > MA20 duotoupailie |
| 3 | xiaolvyouxian：liangnengquerenqushiyouxiaoxing |
| 4 | maidianpianhao：youxianhuicaijunxianzhicheng |
| 5 | fengxianpaicha：likongxinwenyipiaofoujue |
| 6 | liangjiapeihe：chengjiaoliangyanzhengjiageyundong |
| 7 | qiangshiqushigufangkuan：longtougukeshidangfangkuanbiaozhun |

## zidingyicelvemulu

chulebenmulu（neizhicelve），nihaikeyitongguohuanjingbianliangzhidingewaidezidingyicelvemulu：

```env
AGENT_SKILL_DIR=./my_skills
```

xitonghuitongshijiazaineizhicelvehezidingyicelve。ruguomingchengchongtu，zidingyicelvefugaineizhicelve。

huanjingbianliangmingrengranshi `AGENT_SKILL_DIR`，zheshineibutongyimingminghoudepeizhirukou；zaichanpinyuyishang，tayiranbiaoshi“zidingyicelvemulu”。
