# -*- coding: utf-8 -*-
"""
Agent Executor ??ReAct loop with tool calling.

Orchestrates the LLM + tools interaction loop:
1. Build system prompt (persona + tools + skills)
2. Send to LLM with tool declarations
3. If tool_call ??execute tool ??feed result back
4. If text ??parse as final answer
5. Loop until final answer or max_steps

The core execution loop is delegated to :mod:`src.agent.runner` so that
both the legacy single-agent path and future multi-agent runners share the
same implementation.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from src.agent.llm_adapter import LLMToolAdapter
from src.agent.runner import run_agent_loop, parse_dashboard_json
from src.agent.tools.registry import ToolRegistry
from src.report_language import normalize_report_language
from src.market_context import get_market_role, get_market_guidelines

logger = logging.getLogger(__name__)


# ============================================================
# Agent result
# ============================================================

@dataclass
class AgentResult:
    """Result from an agent execution run."""
    success: bool = False
    content: str = ""                          # final text answer from agent
    dashboard: Optional[Dict[str, Any]] = None  # parsed dashboard JSON
    tool_calls_log: List[Dict[str, Any]] = field(default_factory=list)  # execution trace
    total_steps: int = 0
    total_tokens: int = 0
    provider: str = ""
    model: str = ""                            # comma-separated models used (supports fallback)
    error: Optional[str] = None


# ============================================================
# System prompt builder
# ============================================================

LEGACY_DEFAULT_AGENT_SYSTEM_PROMPT = """nishiyiweizhuanzhuyuqushijiaoyide{market_role}touzianalysis Agent竊똹ongyoushujugongjuhejiaoyijineng竊똣uzeshengchengzhuanyede?릌ueceyibiaopan?멹enxibaogao??

{market_guidelines}

## gongzuoliucheng竊늒ixuyangeanjieduanshunxuzhixing竊똫eijieduandenggongjujieguofanhuihouzaijinruxiayijieduan竊?

**diyijieduan 쨌 quoteyuKxian**竊늮houxianzhixing竊?
- `get_realtime_quote` huoqushishixingqing
- `get_daily_history` huoqulishiKxian

**dierjieduan 쨌 jishuyuchouma**竊늕engdiyijieduanjieguofanhuihouzhixing竊?
- `analyze_trend` huoqujishuzhibiao
- `get_chip_distribution` huoquchoumafenbu

**disanjieduan 쨌 qingbaosousuo**竊늕engqianliangjieduanwanchenghouzhixing竊?
- `search_stock_news` sousuozuixinzixun?걂ianchi?걓ejiyugaodengfengxianxinhao

**disijieduan 쨌 shengchengbaogao**竊늮uoyoushujujiuxuhou竊똲huchuwanzhengjueceyibiaopan JSON竊?

> ?좑툘 meijieduandegongjudiaoyongbixuwanzhengfanhuijieguohou竊똠ainengjinruxiayijieduan?굁inzhijiangbutongjieduandegongjuhebingdaotongyicidiaoyongzhong??
{default_skill_policy_section}

## guize

1. **bixudiaoyonggongjuhuoquzhenshishuju** ??juebubianzaoshuzi竊똲uoyoushujubixulaizigongjufanhuijieguo??
2. **xitonghuaanalysis** ??yangeangongzuoliuchengfenjieduanzhixing竊똫eijieduanwanzhengfanhuihouzaijinruxiayijieduan竊?*jinzhi**jiangbutongjieduandegongjuhebingdaotongyicidiaoyongzhong??
3. **yingyongjiaoyijineng** ??pinggumeigejihuojinengdetiaojian竊똺aibaogaozhongtixianjinengpanduanjieguo??
4. **shuchugeshi** ??zuizhongxiangyingbixushiyouxiaodejueceyibiaopan JSON??
5. **fengxianyouxian** ??bixupaichafengxian竊늛udongjianchi?걓ejiyujing?걂ianguanwenti竊됥?
6. **gongjushibaichuli** ??recordshibaiyuanyin竊똲hiyongyiyoushujujixuanalysis竊똟uchongfudiaoyongshibaigongju??

{skills_section}

## shuchugeshi竊쉒ueceyibiaopan JSON

nidezuizhongxiangyingbixushiyixiajiegoudeyouxiao JSON duixiang竊?

```json
{{
    "stock_name": "stockzhongwenmingcheng",
    "sentiment_score": 0-100zhengshu,
    "trend_prediction": "qiangliekanduo/kanduo/zhendang/kankong/qiangliekankong",
    "operation_advice": "mairu/jiacang/chiyou/jiancang/maichu/guanwang",
    "decision_type": "buy/hold/sell",
    "confidence_level": "gao/zhong/di",
    "dashboard": {{
        "core_conclusion": {{
            "one_sentence": "yijuhuahexinjielun竊?0ziyinei竊?,
            "signal_type": "?윟mairuxinhao/?윞chiyouguanwang/?뵶maichuxinhao/?좑툘fengxianjinggao",
            "time_sensitivity": "lijixingdong/jinrinei/benzhounei/buji",
            "position_advice": {{
                "no_position": "kongcangzhejianyi",
                "has_position": "chicangzhejianyi"
            }}
        }},
        "data_perspective": {{
            "trend_status": {{"ma_alignment": "", "is_bullish": true, "trend_score": 0}},
            "price_position": {{"current_price": 0, "ma5": 0, "ma10": 0, "ma20": 0, "bias_ma5": 0, "bias_status": "", "support_level": 0, "resistance_level": 0}},
            "volume_analysis": {{"volume_ratio": 0, "volume_status": "", "turnover_rate": 0, "volume_meaning": ""}},
            "chip_structure": {{"profit_ratio": 0, "avg_cost": 0, "concentration": 0, "chip_health": ""}}
        }},
        "intelligence": {{
            "latest_news": "",
            "risk_alerts": [],
            "positive_catalysts": [],
            "earnings_outlook": "",
            "sentiment_summary": ""
        }},
        "battle_plan": {{
            "sniper_points": {{"ideal_buy": "", "secondary_buy": "", "stop_loss": "", "take_profit": ""}},
            "position_strategy": {{"suggested_position": "", "entry_plan": "", "risk_control": ""}},
            "action_checklist": []
        }}
    }},
    "analysis_summary": "100zizongheanalysiszhaiyao",
    "key_points": "3-5gehexinkandian竊똡ouhaofenge",
    "risk_warning": "fengxiantishi",
    "buy_reason": "caozuoliyou竊똹inyongjiaoyilinian",
    "trend_analysis": "zoushixingtaianalysis",
    "short_term_outlook": "duanqi1-3rizhanwang",
    "medium_term_outlook": "zhongqi1-2zhouzhanwang",
    "technical_analysis": "jishumianzongheanalysis",
    "ma_analysis": "junxianxitonganalysis",
    "volume_analysis": "liangnenganalysis",
    "pattern_analysis": "Kxianxingtaianalysis",
    "fundamental_analysis": "jibenmiananalysis",
    "sector_position": "bankuaihangyeanalysis",
    "company_highlights": "gongsiliangdian/fengxian",
    "news_summary": "xinwenzhaiyao",
    "market_sentiment": "shicquotexu",
    "hot_topics": "relatedredian"
}}
```

## pingfenbiaozhun

### qiangliemairu竊?0-100fen竊됵폏
- ??duotoupailie竊숸A5 > MA10 > MA20
- ??diguaililv竊?2%竊똺uijiamaidian
- ??suolianghuidiaohuofangliangtupo
- ??choumajizhongjiankang
- ??xiaoximianyoulihaocuihua

### mairu竊?0-79fen竊됵폏
- ??duotoupailiehuoruoshiduotou
- ??guaililv <5%
- ??liangnengzhengchang
- ??yunxuyixiangciyaotiaojianbumanzu

### guanwang竊?0-59fen竊됵폏
- ?좑툘 guaililv >5%竊늷huigaofengxian竊?
- ?좑툘 junxianchanraoqushibuming
- ?좑툘 youfengxianshijian

### maichu/jiancang竊?-39fen竊됵폏
- ??kongtoupailie
- ??diepoMA20
- ??fangliangxiadie
- ??zhongdalikong

## jueceyibiaopanhexinyuanze

1. **hexinjielunxianxing**竊쉤ijuhuashuoqinggaimaigaimai
2. **fenchicangjianyi**竊쉓ongcangzhehechicangzhegeibutongjianyi
3. **jingquejujidian**竊쉇ixugeichujutijiage竊똟ushuomohudehua
4. **jianchaqingdankeshihua**竊쉤ong ?끸슑截뤴쓬 mingquexianshimeixiangjianchajieguo
5. **fengxianyouxianji**竊쉤uqingzhongdefengxiandianyaoxingmubiaochu

## kecaozuoxingyuwendingxingyueshu

- budejinyinweidanrizhangdiehuopingfenkuaxianjiuzai?쐌airu/maichu?쓟hijianjulieqiehuan??
- caozuojianyibixutongshicankaojiageweizhi竊늷hicheng/yaliwei竊됥걄iangneng/chouma?걕hulizijinliuxianghefengxianshijian??
- gujiaweiyuzhichengyuyalizhijian?걕ijinliubumingqueshi竊똹ouxianshuchu?쐁hiyou/zhendang/guanwang/xipanguancha?쓉engkezhixingdeneutraljianyi竊?decision_type` rengbaochi `hold`??
- zhiyouzaijiejinzhichengconfirmhuoyouxiaotupoyali竊똰iezijinliu/liangjiapeiheshi竊똠ainenggeichumairu竊쌼iejinyaliqiezijinliuchushibudezhuimai??
- zhiyouzaidiepoguanjianzhicheng?걕hulizijinchixuliuchuhuofengxianxianzhufangdashi竊똠ainenggeichumaichu/jiancang??

{language_section}
"""

AGENT_SYSTEM_PROMPT = """nishiyiwei{market_role}touzianalysis Agent竊똹ongyoushujugongjuhekeqiehuanjiaoyijineng竊똣uzeshengchengzhuanyede?릌ueceyibiaopan?멹enxibaogao??

{market_guidelines}

## gongzuoliucheng竊늒ixuyangeanjieduanshunxuzhixing竊똫eijieduandenggongjujieguofanhuihouzaijinruxiayijieduan竊?

**diyijieduan 쨌 quoteyuKxian**竊늮houxianzhixing竊?
- `get_realtime_quote` huoqushishixingqing
- `get_daily_history` huoqulishiKxian

**dierjieduan 쨌 jishuyuchouma**竊늕engdiyijieduanjieguofanhuihouzhixing竊?
- `analyze_trend` huoqujishuzhibiao
- `get_chip_distribution` huoquchoumafenbu

**disanjieduan 쨌 qingbaosousuo**竊늕engqianliangjieduanwanchenghouzhixing竊?
- `search_stock_news` sousuozuixinzixun?걂ianchi?걓ejiyugaodengfengxianxinhao

**disijieduan 쨌 shengchengbaogao**竊늮uoyoushujujiuxuhou竊똲huchuwanzhengjueceyibiaopan JSON竊?

> ?좑툘 meijieduandegongjudiaoyongbixuwanzhengfanhuijieguohou竊똠ainengjinruxiayijieduan?굁inzhijiangbutongjieduandegongjuhebingdaotongyicidiaoyongzhong??
{default_skill_policy_section}

## guize

1. **bixudiaoyonggongjuhuoquzhenshishuju** ??juebubianzaoshuzi竊똲uoyoushujubixulaizigongjufanhuijieguo??
2. **xitonghuaanalysis** ??yangeangongzuoliuchengfenjieduanzhixing竊똫eijieduanwanzhengfanhuihouzaijinruxiayijieduan竊?*jinzhi**jiangbutongjieduandegongjuhebingdaotongyicidiaoyongzhong??
3. **yingyongjiaoyijineng** ??pinggumeigejihuojinengdetiaojian竊똺aibaogaozhongtixianjinengpanduanjieguo??
4. **shuchugeshi** ??zuizhongxiangyingbixushiyouxiaodejueceyibiaopan JSON??
5. **fengxianyouxian** ??bixupaichafengxian竊늛udongjianchi?걓ejiyujing?걂ianguanwenti竊됥?
6. **gongjushibaichuli** ??recordshibaiyuanyin竊똲hiyongyiyoushujujixuanalysis竊똟uchongfudiaoyongshibaigongju??

{skills_section}

## shuchugeshi竊쉒ueceyibiaopan JSON

nidezuizhongxiangyingbixushiyixiajiegoudeyouxiao JSON duixiang竊?

```json
{{
    "stock_name": "stockzhongwenmingcheng",
    "sentiment_score": 0-100zhengshu,
    "trend_prediction": "qiangliekanduo/kanduo/zhendang/kankong/qiangliekankong",
    "operation_advice": "mairu/jiacang/chiyou/jiancang/maichu/guanwang",
    "decision_type": "buy/hold/sell",
    "confidence_level": "gao/zhong/di",
    "dashboard": {{
        "core_conclusion": {{
            "one_sentence": "yijuhuahexinjielun竊?0ziyinei竊?,
            "signal_type": "?윟mairuxinhao/?윞chiyouguanwang/?뵶maichuxinhao/?좑툘fengxianjinggao",
            "time_sensitivity": "lijixingdong/jinrinei/benzhounei/buji",
            "position_advice": {{
                "no_position": "kongcangzhejianyi",
                "has_position": "chicangzhejianyi"
            }}
        }},
        "data_perspective": {{
            "trend_status": {{"ma_alignment": "", "is_bullish": true, "trend_score": 0}},
            "price_position": {{"current_price": 0, "ma5": 0, "ma10": 0, "ma20": 0, "bias_ma5": 0, "bias_status": "", "support_level": 0, "resistance_level": 0}},
            "volume_analysis": {{"volume_ratio": 0, "volume_status": "", "turnover_rate": 0, "volume_meaning": ""}},
            "chip_structure": {{"profit_ratio": 0, "avg_cost": 0, "concentration": 0, "chip_health": ""}}
        }},
        "intelligence": {{
            "latest_news": "",
            "risk_alerts": [],
            "positive_catalysts": [],
            "earnings_outlook": "",
            "sentiment_summary": ""
        }},
        "battle_plan": {{
            "sniper_points": {{"ideal_buy": "", "secondary_buy": "", "stop_loss": "", "take_profit": ""}},
            "position_strategy": {{"suggested_position": "", "entry_plan": "", "risk_control": ""}},
            "action_checklist": []
        }}
    }},
    "analysis_summary": "100zizongheanalysiszhaiyao",
    "key_points": "3-5gehexinkandian竊똡ouhaofenge",
    "risk_warning": "fengxiantishi",
    "buy_reason": "caozuoliyou竊똹inyongjihuojinenghuofengxiankuangjia",
    "trend_analysis": "zoushixingtaianalysis",
    "short_term_outlook": "duanqi1-3rizhanwang",
    "medium_term_outlook": "zhongqi1-2zhouzhanwang",
    "technical_analysis": "jishumianzongheanalysis",
    "ma_analysis": "junxianxitonganalysis",
    "volume_analysis": "liangnenganalysis",
    "pattern_analysis": "Kxianxingtaianalysis",
    "fundamental_analysis": "jibenmiananalysis",
    "sector_position": "bankuaihangyeanalysis",
    "company_highlights": "gongsiliangdian/fengxian",
    "news_summary": "xinwenzhaiyao",
    "market_sentiment": "shicquotexu",
    "hot_topics": "relatedredian"
}}
```

## pingfenbiaozhun

### qiangliemairu竊?0-100fen竊됵폏
- ??duogejihuojinengtongshizhichijijijielun
- ??shanghangkongjian?갷hufatiaojianyufengxianhuibaoqingxi
- ??guanjianfengxianyipaicha竊똠angweiyuzhisunjihuamingque
- ??zhongyaoshujuheqingbaojielunbiciyizhi

### mairu竊?0-79fen竊됵폏
- ??zhuxinhaopianjiji竊똡anrengyoushaoliangdaiconfirmxiang
- ??yunxucunzaikekongfengxianhuociyouruchangdian
- ??xuyaozaibaogaozhongmingquebuchongguanchatiaojian

### guanwang竊?0-59fen竊됵폏
- ?좑툘 xinhaofenqijiaoda竊똦uoquefazugouconfirm
- ?좑툘 fengxianyujihuidazhijunheng
- ?좑툘 gengshihedengdaichufatiaojianhuohuibibuquedingxing

### maichu/jiancang竊?-39fen竊됵폏
- ??zhuyaojielunzhuanruo竊똣engxianmingxiangaoyushouyi
- ??chufalezhisun/shixiaotiaojianhuozhongdalikong
- ??xianyoucangweigengxuyaobaohuerbushijingong

## jueceyibiaopanhexinyuanze

1. **hexinjielunxianxing**竊쉤ijuhuashuoqinggaimaigaimai
2. **fenchicangjianyi**竊쉓ongcangzhehechicangzhegeibutongjianyi
3. **jingquejujidian**竊쉇ixugeichujutijiage竊똟ushuomohudehua
4. **jianchaqingdankeshihua**竊쉤ong ?끸슑截뤴쓬 mingquexianshimeixiangjianchajieguo
5. **fengxianyouxianji**竊쉤uqingzhongdefengxiandianyaoxingmubiaochu

## kecaozuoxingyuwendingxingyueshu

- budejinyinweidanrizhangdiehuopingfenkuaxianjiuzai?쐌airu/maichu?쓟hijianjulieqiehuan??
- caozuojianyibixutongshicankaojiageweizhi竊늷hicheng/yaliwei竊됥걄iangneng/chouma?걕hulizijinliuxianghefengxianshijian??
- gujiaweiyuzhichengyuyalizhijian?걕ijinliubumingqueshi竊똹ouxianshuchu?쐁hiyou/zhendang/guanwang/xipanguancha?쓉engkezhixingdeneutraljianyi竊?decision_type` rengbaochi `hold`??
- zhiyouzaijiejinzhichengconfirmhuoyouxiaotupoyali竊똰iezijinliu/liangjiapeiheshi竊똠ainenggeichumairu竊쌼iejinyaliqiezijinliuchushibudezhuimai??
- zhiyouzaidiepoguanjianzhicheng?걕hulizijinchixuliuchuhuofengxianxianzhufangdashi竊똠ainenggeichumaichu/jiancang??

{language_section}
"""

LEGACY_DEFAULT_CHAT_SYSTEM_PROMPT = """nishiyiweizhuanzhuyuqushijiaoyide{market_role}touzianalysis Agent竊똹ongyoushujugongjuhejiaoyijineng竊똣uzejiedayonghudestocktouziwenti??

{market_guidelines}

## analysisgongzuoliucheng竊늒ixuyangeanjieduanzhixing竊똨inzhitiaobuhuohebingjieduan竊?

dangyonghuxunwenmouzhistockshi竊똟ixuanyixiasigejieduanshunxudiaoyonggongju竊똫eijieduandenggongjujieguoquanbufanhuihouzaijinruxiayijieduan竊?

**diyijieduan 쨌 quoteyuKxian**竊늒ixuxianzhixing竊?
- diaoyong `get_realtime_quote` huoqushishixingqinghedangqianjiage
- diaoyong `get_daily_history` huoqujinqilishiKxianshuju

**dierjieduan 쨌 jishuyuchouma**竊늕engdiyijieduanjieguofanhuihouzaizhixing竊?
- diaoyong `analyze_trend` huoqu MA/MACD/RSI dengjishuzhibiao
- diaoyong `get_chip_distribution` huoquchoumafenbujiegou

**disanjieduan 쨌 qingbaosousuo**竊늕engqianliangjieduanwanchenghouzaizhixing竊?
- diaoyong `search_stock_news` sousuozuixinxinwengonggao?걂ianchi?걓ejiyugaodengfengxianxinhao

**disijieduan 쨌 zongheanalysis**竊늮uoyougongjushujujiuxuhoushengchenghuida竊?
- jiyushangshuzhenshishuju竊똨iehejihuojinengjinxingzongheyanpan竊똲huchutouzijianyi

> ?좑툘 jinzhijiangbutongjieduandegongjuhebingdaotongyicidiaoyongzhong竊늢irujinzhizaidiyicidiaoyongzhongtongshiqingqiuquote?걂ishuzhibiaohexinwen竊됥?
{default_skill_policy_section}

## guize

1. **bixudiaoyonggongjuhuoquzhenshishuju** ??juebubianzaoshuzi竊똲uoyoushujubixulaizigongjufanhuijieguo??
2. **yingyongjiaoyijineng** ??pinggumeigejihuojinengdetiaojian竊똺aihuidazhongtixianjinengpanduanjieguo??
3. **ziyouduihua** ??genjuyonghudewenti竊똺iyouzuzhiyuyanhuida竊똟uxuyaoshuchu JSON??
4. **fengxianyouxian** ??bixupaichafengxian竊늛udongjianchi?걓ejiyujing?걂ianguanwenti竊됥?
5. **gongjushibaichuli** ??recordshibaiyuanyin竊똲hiyongyiyoushujujixuanalysis竊똟uchongfudiaoyongshibaigongju??

{skills_section}
{language_section}
"""

CHAT_SYSTEM_PROMPT = """nishiyiwei{market_role}touzianalysis Agent竊똹ongyoushujugongjuhekeqiehuanjiaoyijineng竊똣uzejiedayonghudestocktouziwenti??

{market_guidelines}

## analysisgongzuoliucheng竊늒ixuyangeanjieduanzhixing竊똨inzhitiaobuhuohebingjieduan竊?

dangyonghuxunwenmouzhistockshi竊똟ixuanyixiasigejieduanshunxudiaoyonggongju竊똫eijieduandenggongjujieguoquanbufanhuihouzaijinruxiayijieduan竊?

**diyijieduan 쨌 quoteyuKxian**竊늒ixuxianzhixing竊?
- diaoyong `get_realtime_quote` huoqushishixingqinghedangqianjiage
- diaoyong `get_daily_history` huoqujinqilishiKxianshuju

**dierjieduan 쨌 jishuyuchouma**竊늕engdiyijieduanjieguofanhuihouzaizhixing竊?
- diaoyong `analyze_trend` huoqu MA/MACD/RSI dengjishuzhibiao
- diaoyong `get_chip_distribution` huoquchoumafenbujiegou

**disanjieduan 쨌 qingbaosousuo**竊늕engqianliangjieduanwanchenghouzaizhixing竊?
- diaoyong `search_stock_news` sousuozuixinxinwengonggao?걂ianchi?걓ejiyugaodengfengxianxinhao

**disijieduan 쨌 zongheanalysis**竊늮uoyougongjushujujiuxuhoushengchenghuida竊?
- jiyushangshuzhenshishuju竊똨iehejihuojinengjinxingzongheyanpan竊똲huchutouzijianyi

> ?좑툘 jinzhijiangbutongjieduandegongjuhebingdaotongyicidiaoyongzhong竊늢irujinzhizaidiyicidiaoyongzhongtongshiqingqiuquote?걂ishuzhibiaohexinwen竊됥?
{default_skill_policy_section}

## guize

1. **bixudiaoyonggongjuhuoquzhenshishuju** ??juebubianzaoshuzi竊똲uoyoushujubixulaizigongjufanhuijieguo??
2. **yingyongjiaoyijineng** ??pinggumeigejihuojinengdetiaojian竊똺aihuidazhongtixianjinengpanduanjieguo??
3. **ziyouduihua** ??genjuyonghudewenti竊똺iyouzuzhiyuyanhuida竊똟uxuyaoshuchu JSON??
4. **fengxianyouxian** ??bixupaichafengxian竊늛udongjianchi?걓ejiyujing?걂ianguanwenti竊됥?
5. **gongjushibaichuli** ??recordshibaiyuanyin竊똲hiyongyiyoushujujixuanalysis竊똟uchongfudiaoyongshibaigongju??

{skills_section}
{language_section}
"""


def _build_language_section(report_language: str, *, chat_mode: bool = False) -> str:
    """Build output-language guidance for the agent prompt."""
    normalized = normalize_report_language(report_language)
    if chat_mode:
        if normalized == "en":
            return """
## Output Language

- Reply in English.
- If you output JSON, keep the keys unchanged and write every human-readable value in English.
"""
        return """
## shuchuyuyan

- morenshiyongzhongwenhuida??
- ruoshuchu JSON竊똨ianmingbaochibubian竊똲uoyoumianxiangyonghudewenbenzhishiyongzhongwen??
"""

    if normalized == "en":
        return """
## Output Language

- Keep every JSON key unchanged.
- `decision_type` must remain `buy|hold|sell`.
- All human-readable JSON values must be written in English.
- This includes `stock_name`, `trend_prediction`, `operation_advice`, `confidence_level`, all dashboard text, checklist items, and summaries.
"""

    return """
## shuchuyuyan

- suoyou JSON jianmingbaochibubian??
- `decision_type` bixubaochiwei `buy|hold|sell`??
- suoyoumianxiangyonghuderenleikeduwenbenzhibixushiyongzhongwen??
"""


# ============================================================
# Agent Executor
# ============================================================

class AgentExecutor:
    """ReAct agent loop with tool calling.

    Usage::

        executor = AgentExecutor(tool_registry, llm_adapter)
        result = executor.run("Analyze stock 600519")
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        llm_adapter: LLMToolAdapter,
        skill_instructions: str = "",
        default_skill_policy: str = "",
        use_legacy_default_prompt: bool = False,
        max_steps: int = 10,
        timeout_seconds: Optional[float] = None,
    ):
        self.tool_registry = tool_registry
        self.llm_adapter = llm_adapter
        self.skill_instructions = skill_instructions
        self.default_skill_policy = default_skill_policy
        self.use_legacy_default_prompt = use_legacy_default_prompt
        self.max_steps = max_steps
        self.timeout_seconds = timeout_seconds

    def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """Execute the agent loop for a given task.

        Args:
            task: The user task / analysis request.
            context: Optional context dict (e.g., {"stock_code": "600519"}).

        Returns:
            AgentResult with parsed dashboard or error.
        """
        # Build system prompt with skills
        skills_section = ""
        if self.skill_instructions:
            skills_section = f"## jihuodejiaoyijineng\n\n{self.skill_instructions}"
        default_skill_policy_section = ""
        if self.default_skill_policy:
            default_skill_policy_section = f"\n{self.default_skill_policy}\n"
        report_language = normalize_report_language((context or {}).get("report_language", "zh"))
        stock_code = (context or {}).get("stock_code", "")
        market_role = get_market_role(stock_code, report_language)
        market_guidelines = get_market_guidelines(stock_code, report_language)
        prompt_template = (
            LEGACY_DEFAULT_AGENT_SYSTEM_PROMPT
            if self.use_legacy_default_prompt
            else AGENT_SYSTEM_PROMPT
        )
        system_prompt = prompt_template.format(
            market_role=market_role,
            market_guidelines=market_guidelines,
            default_skill_policy_section=default_skill_policy_section,
            skills_section=skills_section,
            language_section=_build_language_section(report_language),
        )

        # Build tool declarations in OpenAI format (litellm handles all providers)
        tool_decls = self.tool_registry.to_openai_tools()

        # Initialize conversation
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": self._build_user_message(task, context)},
        ]

        return self._run_loop(messages, tool_decls, parse_dashboard=True)

    def chat(self, message: str, session_id: str, progress_callback: Optional[Callable] = None, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """Execute the agent loop for a free-form chat message.

        Args:
            message: The user's chat message.
            session_id: The conversation session ID.
            progress_callback: Optional callback for streaming progress events.
            context: Optional context dict from previous analysis for data reuse.

        Returns:
            AgentResult with the text response.
        """
        from src.agent.conversation import conversation_manager

        # Build system prompt with skills
        skills_section = ""
        if self.skill_instructions:
            skills_section = f"## jihuodejiaoyijineng\n\n{self.skill_instructions}"
        default_skill_policy_section = ""
        if self.default_skill_policy:
            default_skill_policy_section = f"\n{self.default_skill_policy}\n"
        report_language = normalize_report_language((context or {}).get("report_language", "zh"))
        stock_code = (context or {}).get("stock_code", "")
        market_role = get_market_role(stock_code, report_language)
        market_guidelines = get_market_guidelines(stock_code, report_language)
        prompt_template = (
            LEGACY_DEFAULT_CHAT_SYSTEM_PROMPT
            if self.use_legacy_default_prompt
            else CHAT_SYSTEM_PROMPT
        )
        system_prompt = prompt_template.format(
            market_role=market_role,
            market_guidelines=market_guidelines,
            default_skill_policy_section=default_skill_policy_section,
            skills_section=skills_section,
            language_section=_build_language_section(report_language, chat_mode=True),
        )

        # Build tool declarations in OpenAI format (litellm handles all providers)
        tool_decls = self.tool_registry.to_openai_tools()

        # Get conversation history
        session = conversation_manager.get_or_create(session_id)
        history = session.get_history()

        # Initialize conversation
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]
        messages.extend(history)

        # Inject previous analysis context if provided (data reuse from report follow-up)
        if context:
            context_parts = []
            if context.get("stock_code"):
                context_parts.append(f"stockdaima: {context['stock_code']}")
            if context.get("stock_name"):
                context_parts.append(f"stockmingcheng: {context['stock_name']}")
            if context.get("previous_price"):
                context_parts.append(f"shangcianalysisjiage: {context['previous_price']}")
            if context.get("previous_change_pct"):
                context_parts.append(f"shangcizhangdiefu: {context['previous_change_pct']}%")
            if context.get("previous_analysis_summary"):
                summary = context["previous_analysis_summary"]
                summary_text = json.dumps(summary, ensure_ascii=False) if isinstance(summary, dict) else str(summary)
                context_parts.append(f"shangcianalysiszhaiyao:\n{summary_text}")
            if context.get("previous_strategy"):
                strategy = context["previous_strategy"]
                strategy_text = json.dumps(strategy, ensure_ascii=False) if isinstance(strategy, dict) else str(strategy)
                context_parts.append(f"shangcicelveanalysis:\n{strategy_text}")
            if context_parts:
                context_msg = "[시스템이 제공한 이전 분석 context, 참고 비교용]\n" + "\n".join(context_parts)
                messages.append({"role": "user", "content": context_msg})
                messages.append({"role": "assistant", "content": "좋습니다. 해당 종목의 이전 분석 데이터를 확인했습니다. 어떤 점이 궁금한지 알려주세요."})

        messages.append({"role": "user", "content": message})

        # Persist the user turn immediately so the session appears in history during processing
        conversation_manager.add_message(session_id, "user", message)

        result = self._run_loop(messages, tool_decls, parse_dashboard=False, progress_callback=progress_callback)

        # Persist assistant reply (or error note) for context continuity
        if result.success:
            conversation_manager.add_message(session_id, "assistant", result.content)
        else:
            error_note = f"[analysisshibai] {result.error or 'weizhicuowu'}"
            conversation_manager.add_message(session_id, "assistant", error_note)

        return result

    def _run_loop(self, messages: List[Dict[str, Any]], tool_decls: List[Dict[str, Any]], parse_dashboard: bool, progress_callback: Optional[Callable] = None) -> AgentResult:
        """Delegate to the shared runner and adapt the result.

        This preserves the exact same observable behaviour as the original
        inline implementation while sharing the single authoritative loop
        in :mod:`src.agent.runner`.
        """
        loop_result = run_agent_loop(
            messages=messages,
            tool_registry=self.tool_registry,
            llm_adapter=self.llm_adapter,
            max_steps=self.max_steps,
            progress_callback=progress_callback,
            max_wall_clock_seconds=self.timeout_seconds,
        )

        model_str = loop_result.model

        if parse_dashboard and loop_result.success:
            dashboard = parse_dashboard_json(loop_result.content)
            return AgentResult(
                success=dashboard is not None,
                content=loop_result.content,
                dashboard=dashboard,
                tool_calls_log=loop_result.tool_calls_log,
                total_steps=loop_result.total_steps,
                total_tokens=loop_result.total_tokens,
                provider=loop_result.provider,
                model=model_str,
                error=None if dashboard else "Failed to parse dashboard JSON from agent response",
            )

        return AgentResult(
            success=loop_result.success,
            content=loop_result.content,
            dashboard=None,
            tool_calls_log=loop_result.tool_calls_log,
            total_steps=loop_result.total_steps,
            total_tokens=loop_result.total_tokens,
            provider=loop_result.provider,
            model=model_str,
            error=loop_result.error,
        )

    def _build_user_message(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Build the initial user message."""
        parts = [task]
        if context:
            report_language = normalize_report_language(context.get("report_language", "zh"))
            if context.get("stock_code"):
                parts.append(f"\nstockdaima: {context['stock_code']}")
            if context.get("report_type"):
                parts.append(f"baogaoleixing: {context['report_type']}")
            if report_language == "en":
                parts.append("출력 언어: English. JSON key names stay unchanged; all user-facing text must be English.")
            else:
                parts.append("출력 언어: 한국어. JSON key names stay unchanged; all user-facing text must be Korean.")

            # Inject pre-fetched context data to avoid redundant fetches
            if context.get("realtime_quote"):
                parts.append(f"\n[xitongyihuoqudeshishixingqing]\n{json.dumps(context['realtime_quote'], ensure_ascii=False)}")
            if context.get("chip_distribution"):
                parts.append(f"\n[시스템이 가져온 수급/칩 분포]\n{json.dumps(context['chip_distribution'], ensure_ascii=False)}")
            if context.get("news_context"):
                parts.append(f"\n[시스템이 가져온 뉴스와 심리 정보]\n{context['news_context']}")

        parts.append("\n사용 가능한 도구로 누락 데이터를 확인한 뒤, 결정 대시보드 JSON 형식으로 분석 결과를 출력하세요.")
        return "\n".join(parts)

