# -*- coding: utf-8 -*-
"""
===================================
shishixingqingtongyileixingdingyi & rongduanjizhi
===================================

shejimubiao：
1. tongyigeshujuyuandeshishixingqingfanhuijiegou
2. shixianrongduan/lengquejizhi，bimianlianxushibaishifanfuqingqiu
3. zhichiduoshujuyuanguzhangqiehuan

shiyongfangshi：
- suoyou Fetcher de get_realtime_quote() tongyifanhui UnifiedRealtimeQuote
- CircuitBreaker guanligeshujuyuanderongduanzhuangtai
"""

import logging
import time
from threading import RLock
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Union
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================
# tongyongleixingzhuanhuangongjuhanshu
# ============================================
# shejishuoming：
# geshujuyuanfanhuideyuanshishujuleixingbuyizhi（str/float/int/NaN），
# shiyongzhexiehanshutongyizhuanhuan，bimianzaige Fetcher zhongchongfudingyi。

def safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
    """
    anquanzhuanhuanweifudianshu
    
    chulichangjing：
    - None / kongzifuchuan → default
    - pandas NaN / numpy NaN → default
    - shuzhizifuchuan → float
    - yishishuzhi → float
    
    Args:
        val: daizhuanhuandezhi
        default: zhuanhuanshibaishidemorenzhi
        
    Returns:
        zhuanhuanhoudefudianshu，huomorenzhi
    """
    try:
        if val is None:
            return default
        
        # chulizifuchuan
        if isinstance(val, str):
            val = val.strip()
            if val == "" or val == "-" or val == "--":
                return default
        
        # chuli pandas/numpy NaN
        # shiyong math.isnan erbushi pd.isna，bimianqiangzhiyilai pandas
        import math
        try:
            if math.isnan(float(val)):
                return default
        except (ValueError, TypeError):
            pass
        
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val: Any, default: Optional[int] = None) -> Optional[int]:
    """
    anquanzhuanhuanweizhengshu
    
    xianzhuanhuanwei float，zaiquzheng，chuli "123.0" zheleiqingkuang
    
    Args:
        val: daizhuanhuandezhi
        default: zhuanhuanshibaishidemorenzhi
        
    Returns:
        zhuanhuanhoudezhengshu，huomorenzhi
    """
    f_val = safe_float(val, default=None)
    if f_val is not None:
        return int(f_val)
    return default


class RealtimeSource(Enum):
    """shishixingqingshujuyuan"""
    EFINANCE = "efinance"           # dongfangcaifu（efinanceku）
    AKSHARE_EM = "akshare_em"       # dongfangcaifu（akshareku）
    AKSHARE_SINA = "akshare_sina"   # xinlangcaijing
    AKSHARE_QQ = "akshare_qq"       # tengxuncaijing
    TUSHARE = "tushare"             # Tushare Pro
    TENCENT = "tencent"             # tengxunzhilian
    SINA = "sina"                   # xinlangzhilian
    STOOQ = "stooq"                 # Stooq meigudoudi
    LONGBRIDGE = "longbridge"       # zhangqiao（meigu/ganggudoudi）
    FALLBACK = "fallback"           # jiangjidoudi


@dataclass
class UnifiedRealtimeQuote:
    """
    tongyishishixingqingshujujiegou
    
    shejiyuanze：
    - geshujuyuanfanhuideziduankenengbutong，queshiziduanyong None biaoshi
    - zhuliuchengshiyong getattr(quote, field, None) huoqu，baozhengjianrongxing
    - source ziduanbiaojishujulaiyuan，bianyutiaoshi
    """
    code: str
    name: str = ""
    source: RealtimeSource = RealtimeSource.FALLBACK
    
    # === hexinjiageshuju（jihusuoyouyuandouyou）===
    price: Optional[float] = None           # zuixinjia
    change_pct: Optional[float] = None      # zhangdiefu(%)
    change_amount: Optional[float] = None   # zhangdiee
    
    # === liangjiazhibiao（bufenyuankenengqueshi）===
    volume: Optional[int] = None            # chengjiaoliang（shou）
    amount: Optional[float] = None          # chengjiaoe（yuan）
    volume_ratio: Optional[float] = None    # liangbi
    turnover_rate: Optional[float] = None   # huanshoulv(%)
    amplitude: Optional[float] = None       # zhenfu(%)
    
    # === jiagequjian ===
    open_price: Optional[float] = None      # kaipanjia
    high: Optional[float] = None            # zuigaojia
    low: Optional[float] = None             # zuidijia
    pre_close: Optional[float] = None       # zuoshoujia
    
    # === guzhizhibiao（jindongcaidengquanliangjiekouyou）===
    pe_ratio: Optional[float] = None        # shiyinglv(dongtai)
    pb_ratio: Optional[float] = None        # shijinglv
    total_mv: Optional[float] = None        # zongshizhi(yuan)
    circ_mv: Optional[float] = None         # liutongshizhi(yuan)
    
    # === qitazhibiao ===
    change_60d: Optional[float] = None      # 60rizhangdiefu(%)
    high_52w: Optional[float] = None        # 52zhouzuigao
    low_52w: Optional[float] = None         # 52zhouzuidi
    
    def to_dict(self) -> Dict[str, Any]:
        """zhuanhuanweizidian（guolv None zhi）"""
        result = {
            'code': self.code,
            'name': self.name,
            'source': self.source.value,
        }
        # zhitianjiafei None deziduan
        optional_fields = [
            'price', 'change_pct', 'change_amount', 'volume', 'amount',
            'volume_ratio', 'turnover_rate', 'amplitude',
            'open_price', 'high', 'low', 'pre_close',
            'pe_ratio', 'pb_ratio', 'total_mv', 'circ_mv',
            'change_60d', 'high_52w', 'low_52w'
        ]
        for f in optional_fields:
            val = getattr(self, f, None)
            if val is not None:
                result[f] = val
        return result
    
    def has_basic_data(self) -> bool:
        """jianchashifouyoujibendejiageshuju"""
        return self.price is not None and self.price > 0
    
    def has_volume_data(self) -> bool:
        """jianchashifouyouliangjiashuju"""
        return self.volume_ratio is not None or self.turnover_rate is not None


@dataclass
class ChipDistribution:
    """
    choumafenbushuju
    
    fanyingchicangchengbenfenbuhehuoliqingkuang
    """
    code: str
    date: str = ""
    source: str = "akshare"
    
    # huoliqingkuang
    profit_ratio: float = 0.0     # huolibili(0-1)
    avg_cost: float = 0.0         # pingjunchengben
    
    # choumajizhongdu
    cost_90_low: float = 0.0      # 90%choumachengbenxiaxian
    cost_90_high: float = 0.0     # 90%choumachengbenshangxian
    concentration_90: float = 0.0  # 90%choumajizhongdu（yuexiaoyuejizhong）
    
    cost_70_low: float = 0.0      # 70%choumachengbenxiaxian
    cost_70_high: float = 0.0     # 70%choumachengbenshangxian
    concentration_70: float = 0.0  # 70%choumajizhongdu
    
    def to_dict(self) -> Dict[str, Any]:
        """zhuanhuanweizidian"""
        return {
            'code': self.code,
            'date': self.date,
            'source': self.source,
            'profit_ratio': self.profit_ratio,
            'avg_cost': self.avg_cost,
            'cost_90_low': self.cost_90_low,
            'cost_90_high': self.cost_90_high,
            'concentration_90': self.concentration_90,
            'concentration_70': self.concentration_70,
        }
    
    def get_chip_status(self, current_price: float) -> str:
        """
        huoquchoumazhuangtaimiaoshu
        
        Args:
            current_price: dangqiangujia
            
        Returns:
            choumazhuangtaimiaoshu
        """
        status_parts = []
        
        # huolibilifenxi
        if self.profit_ratio >= 0.9:
            status_parts.append("huolipanjigao(huolipan>90%)")
        elif self.profit_ratio >= 0.7:
            status_parts.append("huolipanjiaogao(huolipan70-90%)")
        elif self.profit_ratio >= 0.5:
            status_parts.append("huolipanzhongdeng(huolipan50-70%)")
        elif self.profit_ratio >= 0.3:
            status_parts.append("taolaopanzhongdeng(taolaopan50-70%)")
        elif self.profit_ratio >= 0.1:
            status_parts.append("taolaopanjiaogao(taolaopan70-90%)")
        else:
            status_parts.append("taolaopanjigao(taolaopan>90%)")
        
        # choumajizhongdufenxi (90%jizhongdu < 10% biaoshijizhong)
        if self.concentration_90 < 0.08:
            status_parts.append("choumagaodujizhong")
        elif self.concentration_90 < 0.15:
            status_parts.append("choumajiaojizhong")
        elif self.concentration_90 < 0.25:
            status_parts.append("choumafensanduzhongdeng")
        else:
            status_parts.append("choumajiaofensan")
        
        # chengbenyuxianjiaguanxi
        if current_price > 0 and self.avg_cost > 0:
            cost_diff = (current_price - self.avg_cost) / self.avg_cost * 100
            if cost_diff > 20:
                status_parts.append(f"xianjiagaoyupingjunchengben{cost_diff:.1f}%")
            elif cost_diff > 5:
                status_parts.append(f"xianjialvegaoyuchengben{cost_diff:.1f}%")
            elif cost_diff > -5:
                status_parts.append("xianjiajiejinpingjunchengben")
            else:
                status_parts.append(f"xianjiadiyupingjunchengben{abs(cost_diff):.1f}%")
        
        return "，".join(status_parts)


class CircuitBreaker:
    """
    rongduanqi - guanlishujuyuanderongduan/lengquezhuangtai
    
    celve：
    - lianxushibai N cihoujinrurongduanzhuangtai
    - rongduanqijiantiaoguogaishujuyuan
    - lengqueshijianhouzidonghuifubankaizhuangtai
    - bankaizhuangtaixiadancichenggongzewanquanhuifu，shibaizejixurongduan
    
    zhuangtaiji：
    CLOSED（zhengchang） --shibaiNci--> OPEN（rongduan）--lengqueshijiandao--> HALF_OPEN（bankai）
    HALF_OPEN --chenggong--> CLOSED
    HALF_OPEN --shibai--> OPEN
    """
    
    # zhuangtaichangliang
    CLOSED = "closed"      # zhengchangzhuangtai
    OPEN = "open"          # rongduanzhuangtai（bukeyong）
    HALF_OPEN = "half_open"  # bankaizhuangtai（shitanxingqingqiu）
    
    def __init__(
        self,
        failure_threshold: int = 3,       # lianxushibaicishuyuzhi
        cooldown_seconds: float = 300.0,  # lengqueshijian（miao），moren5fenzhong
        half_open_max_calls: int = 1      # bankaizhuangtaizuidachangshicishu
    ):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.half_open_max_calls = half_open_max_calls
        
        # geshujuyuanzhuangtai {source_name: {state, failures, last_failure_time, half_open_calls}}
        self._states: Dict[str, Dict[str, Any]] = {}
        self._lock = RLock()
    
    def _get_state_locked(self, source: str) -> Dict[str, Any]:
        """huoquhuochushihuashujuyuanzhuangtai（diaoyongfangxuchiyousuo）。"""
        if source not in self._states:
            self._states[source] = {
                'state': self.CLOSED,
                'failures': 0,
                'last_failure_time': 0.0,
                'half_open_calls': 0
            }
        return self._states[source]
    
    def is_available(self, source: str) -> bool:
        """
        jianchashujuyuanshifoukeyong
        
        fanhui True biaoshikeyichangshiqingqiu
        fanhui False biaoshiyingtiaoguogaishujuyuan
        """
        with self._lock:
            state = self._get_state_locked(source)
            current_time = time.time()

            if state['state'] == self.CLOSED:
                return True

            if state['state'] == self.OPEN:
                # jianchalengqueshijian
                time_since_failure = current_time - state['last_failure_time']
                if time_since_failure >= self.cooldown_seconds:
                    # lengquewancheng，jinrubankaizhuangtai（buyuzhanminge，you HALF_OPEN fenzhitongyiguanli）
                    state['state'] = self.HALF_OPEN
                    state['half_open_calls'] = 0
                    state['last_failure_time'] = current_time
                    logger.info(f"[rongduanqi] {source} lengquewancheng，jinrubankaizhuangtai")
                    # Fall through to HALF_OPEN check below
                else:
                    remaining = self.cooldown_seconds - time_since_failure
                    logger.debug(f"[rongduanqi] {source} chuyurongduanzhuangtai，shengyulengqueshijian: {remaining:.0f}s")
                    return False

            if state['state'] == self.HALF_OPEN:
                if state['half_open_calls'] < self.half_open_max_calls:
                    state['half_open_calls'] += 1
                    return True
                # suoyoutancemingeyiyongwan；ruolengqueshijianzaicidaoqirengweishoudao
                # record_success/record_failure huidiao，zhongzhimingeyunxuchongxintance，
                # bimianyongjiukazai HALF_OPEN。
                time_since_failure = current_time - state['last_failure_time']
                if time_since_failure >= self.cooldown_seconds:
                    state['half_open_calls'] = 1
                    state['last_failure_time'] = current_time
                    logger.info(f"[rongduanqi] {source} bankaizhuangtaitancechaoshi，chongxintance")
                    return True
                return False

            return True
    
    def record_inconclusive(self, source: str) -> None:
        """jilubuquedingdetancejieguo（rufanhui None）。

        jinyingxiang HALF_OPEN zhuangtai：jiangqizhuanhui OPEN yibianlengquehouchongxintance。
        CLOSED zhuangtaixiaweikongcaozuo，buyingxiangshibaijishu。
        """
        with self._lock:
            state = self._get_state_locked(source)
            if state['state'] == self.HALF_OPEN:
                state['state'] = self.OPEN
                state['half_open_calls'] = 0
                state['last_failure_time'] = time.time()
                logger.info(f"[rongduanqi] {source} bankaitancejieguobuqueding，chongxinjinrulengque")

    def record_success(self, source: str) -> None:
        """jiluchenggongqingqiu"""
        with self._lock:
            state = self._get_state_locked(source)

            if state['state'] == self.HALF_OPEN:
                # bankaizhuangtaixiachenggong，wanquanhuifu
                logger.info(f"[rongduanqi] {source} bankaizhuangtaiqingqiuchenggong，huifuzhengchang")

            # zhongzhizhuangtai
            state['state'] = self.CLOSED
            state['failures'] = 0
            state['half_open_calls'] = 0
    
    def record_failure(self, source: str, error: Optional[str] = None) -> None:
        """jilushibaiqingqiu"""
        with self._lock:
            state = self._get_state_locked(source)
            current_time = time.time()

            state['failures'] += 1
            state['last_failure_time'] = current_time

            if state['state'] == self.HALF_OPEN:
                # bankaizhuangtaixiashibai，jixurongduan
                state['state'] = self.OPEN
                state['half_open_calls'] = 0
                logger.warning(f"[rongduanqi] {source} bankaizhuangtaiqingqiushibai，jixurongduan {self.cooldown_seconds}s")
            elif state['failures'] >= self.failure_threshold:
                # dadaoyuzhi，jinrurongduan
                state['state'] = self.OPEN
                logger.warning(f"[rongduanqi] {source} lianxushibai {state['failures']} ci，jinrurongduanzhuangtai "
                              f"(lengque {self.cooldown_seconds}s)")
                if error:
                    logger.warning(f"[rongduanqi] zuihoucuowu: {error}")
    
    def get_status(self) -> Dict[str, str]:
        """huoqusuoyoushujuyuanzhuangtai"""
        with self._lock:
            return {source: info['state'] for source, info in self._states.items()}
    
    def reset(self, source: Optional[str] = None) -> None:
        """zhongzhirongduanqizhuangtai"""
        with self._lock:
            if source:
                if source in self._states:
                    del self._states[source]
            else:
                self._states.clear()


# quanjurongduanqishili（shishixingqingzhuanyong）
_realtime_circuit_breaker = CircuitBreaker(
    failure_threshold=3,      # lianxushibai3cirongduan
    cooldown_seconds=300.0,   # lengque5fenzhong
    half_open_max_calls=1
)

# choumajiekourongduanqi（gengbaoshoudecelve，yinweigaijiekougengbuwending）
_chip_circuit_breaker = CircuitBreaker(
    failure_threshold=2,      # lianxushibai2cirongduan
    cooldown_seconds=600.0,   # lengque10fenzhong
    half_open_max_calls=1
)


def get_realtime_circuit_breaker() -> CircuitBreaker:
    """huoqushishixingqingrongduanqi"""
    return _realtime_circuit_breaker


def get_chip_circuit_breaker() -> CircuitBreaker:
    """huoquchoumajiekourongduanqi"""
    return _chip_circuit_breaker
