# -*- coding: utf-8 -*-
"""
===================================
qushijiaoyianalysisqi - jiyuyonghujiaoyilinian
===================================

jiaoyilinianhexinyuanze竊?
1. yanjincelve - buzhuigao竊똺huiqiumeibijiaoyichenggonglv
2. qushijiaoyi - MA5>MA10>MA20 duotoupailie竊똲hunshierwei
3. xiaolvyouxian - guanzhuchoumajiegouhaodestock
4. maidianpianhao - zai MA5/MA10 fujinhuicaimairu

jishubiaozhun竊?
- duotoupailie竊숸A5 > MA10 > MA20
- guaililv竊?Close - MA5) / MA5 < 5%竊늒uzhuigao竊?
- liangnengxingtai竊쉝uolianghuidiaoyouxian
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List
from enum import Enum

import pandas as pd
import numpy as np

from src.config import get_config

logger = logging.getLogger(__name__)


class TrendStatus(Enum):
    """qushizhuangtaimeiju"""
    STRONG_BULL = "qiangshiduotou"      # MA5 > MA10 > MA20竊똰iejianjukuoda
    BULL = "duotoupailie"             # MA5 > MA10 > MA20
    WEAK_BULL = "ruoshiduotou"        # MA5 > MA10竊똡an MA10 < MA20
    CONSOLIDATION = "panzheng"        # junxianchanrao
    WEAK_BEAR = "ruoshikongtou"        # MA5 < MA10竊똡an MA10 > MA20
    BEAR = "kongtoupailie"             # MA5 < MA10 < MA20
    STRONG_BEAR = "qiangshikongtou"      # MA5 < MA10 < MA20竊똰iejianjukuoda


class VolumeStatus(Enum):
    """liangnengzhuangtaimeiju"""
    HEAVY_VOLUME_UP = "fangliangshangzhang"       # liangjiaqisheng
    HEAVY_VOLUME_DOWN = "fangliangxiadie"     # fangliangshadie
    SHRINK_VOLUME_UP = "suoliangshangzhang"      # wuliangshangzhang
    SHRINK_VOLUME_DOWN = "suolianghuidiao"    # suolianghuidiao竊늜ao竊?
    NORMAL = "liangnengzhengchang"


class BuySignal(Enum):
    """mairuxinhaomeiju"""
    STRONG_BUY = "qiangliemairu"       # duotiaojianmanzu
    BUY = "mairu"                  # jibentiaojianmanzu
    HOLD = "chiyou"                 # yichiyoukejixu
    WAIT = "guanwang"                 # dengdaigenghaoshiji
    SELL = "maichu"                 # qushizhuanruo
    STRONG_SELL = "qiangliemaichu"      # qushipohuai


class MACDStatus(Enum):
    """MACDzhuangtaimeiju"""
    GOLDEN_CROSS_ZERO = "lingzhoushangjincha"      # DIFshangchuanDEA竊똰iezailingzhoushangfang
    GOLDEN_CROSS = "jincha"                # DIFshangchuanDEA
    BULLISH = "duotou"                    # DIF>DEA>0
    CROSSING_UP = "shangchuanlingzhou"             # DIFshangchuanlingzhou
    CROSSING_DOWN = "xiachuanlingzhou"           # DIFxiachuanlingzhou
    BEARISH = "kongtou"                    # DIF<DEA<0
    DEATH_CROSS = "sicha"                # DIFxiachuanDEA


class RSIStatus(Enum):
    """RSIzhuangtaimeiju"""
    OVERBOUGHT = "chaomai"        # RSI > 70
    STRONG_BUY = "qiangshimairu"    # 50 < RSI < 70
    NEUTRAL = "neutral"          # 40 <= RSI <= 60
    WEAK = "ruoshi"             # 30 < RSI < 40
    OVERSOLD = "chaomai"         # RSI < 30


@dataclass
class TrendAnalysisResult:
    """qushianalysisjieguo"""
    code: str
    
    # qushipanduan
    trend_status: TrendStatus = TrendStatus.CONSOLIDATION
    ma_alignment: str = ""           # junxianpailiemiaoshu
    trend_strength: float = 0.0      # qushiqiangdu 0-100
    
    # junxianshuju
    ma5: float = 0.0
    ma10: float = 0.0
    ma20: float = 0.0
    ma60: float = 0.0
    current_price: float = 0.0
    
    # guaililv竊늶u MA5 depianlidu竊?
    bias_ma5: float = 0.0            # (Close - MA5) / MA5 * 100
    bias_ma10: float = 0.0
    bias_ma20: float = 0.0
    
    # liangnenganalysis
    volume_status: VolumeStatus = VolumeStatus.NORMAL
    volume_ratio_5d: float = 0.0     # dangrichengjiaoliang/5rijunliang
    volume_trend: str = ""           # liangnengqushimiaoshu
    
    # zhichengyali
    support_ma5: bool = False        # MA5 shifougouchengzhicheng
    support_ma10: bool = False       # MA10 shifougouchengzhicheng
    resistance_levels: List[float] = field(default_factory=list)
    support_levels: List[float] = field(default_factory=list)

    # MACD zhibiao
    macd_dif: float = 0.0          # DIF kuaixian
    macd_dea: float = 0.0          # DEA manxian
    macd_bar: float = 0.0           # MACD zhuzhuangtu
    macd_status: MACDStatus = MACDStatus.BULLISH
    macd_signal: str = ""            # MACD xinhaomiaoshu

    # RSI zhibiao
    rsi_6: float = 0.0              # RSI(6) duanqi
    rsi_12: float = 0.0             # RSI(12) zhongqi
    rsi_24: float = 0.0             # RSI(24) changqi
    rsi_status: RSIStatus = RSIStatus.NEUTRAL
    rsi_signal: str = ""              # RSI xinhaomiaoshu

    # mairuxinhao
    buy_signal: BuySignal = BuySignal.WAIT
    signal_score: int = 0            # zonghepingfen 0-100
    signal_reasons: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'code': self.code,
            'trend_status': self.trend_status.value,
            'ma_alignment': self.ma_alignment,
            'trend_strength': self.trend_strength,
            'ma5': self.ma5,
            'ma10': self.ma10,
            'ma20': self.ma20,
            'ma60': self.ma60,
            'current_price': self.current_price,
            'bias_ma5': self.bias_ma5,
            'bias_ma10': self.bias_ma10,
            'bias_ma20': self.bias_ma20,
            'volume_status': self.volume_status.value,
            'volume_ratio_5d': self.volume_ratio_5d,
            'volume_trend': self.volume_trend,
            'support_ma5': self.support_ma5,
            'support_ma10': self.support_ma10,
            'buy_signal': self.buy_signal.value,
            'signal_score': self.signal_score,
            'signal_reasons': self.signal_reasons,
            'risk_factors': self.risk_factors,
            'macd_dif': self.macd_dif,
            'macd_dea': self.macd_dea,
            'macd_bar': self.macd_bar,
            'macd_status': self.macd_status.value,
            'macd_signal': self.macd_signal,
            'rsi_6': self.rsi_6,
            'rsi_12': self.rsi_12,
            'rsi_24': self.rsi_24,
            'rsi_status': self.rsi_status.value,
            'rsi_signal': self.rsi_signal,
        }


class StockTrendAnalyzer:
    """
    stockqushianalysisqi

    jiyuyonghujiaoyilinianshixian竊?
    1. qushipanduan - MA5>MA10>MA20 duotoupailie
    2. guaililvjiance - buzhuigao竊똯ianli MA5 chaoguo 5% bumai
    3. liangnenganalysis - pianhaosuolianghuidiao
    4. maidianshibie - huicai MA5/MA10 zhicheng
    5. MACD zhibiao - qushiconfirmhejinchasichaxinhao
    6. RSI zhibiao - chaomaichaomaipanduan
    """
    
    # jiaoyicanshuconfig竊뉰IAS_THRESHOLD cong Config duqu竊똨ian _generate_signal竊?
    VOLUME_SHRINK_RATIO = 0.7   # suoliangpanduanyuzhi竊늕angriliang/5rijunliang竊?
    VOLUME_HEAVY_RATIO = 1.5    # fangliangpanduanyuzhi
    MA_SUPPORT_TOLERANCE = 0.02  # MA zhichengpanduanrongrendu竊?%竊?

    # MACD canshu竊늒iaozhun12/26/9竊?
    MACD_FAST = 12              # kuaixianzhouqi
    MACD_SLOW = 26             # manxianzhouqi
    MACD_SIGNAL = 9             # xinhaoxianzhouqi

    # RSI canshu
    RSI_SHORT = 6               # duanqiRSIzhouqi
    RSI_MID = 12               # zhongqiRSIzhouqi
    RSI_LONG = 24              # changqiRSIzhouqi
    RSI_OVERBOUGHT = 70        # chaomaiyuzhi
    RSI_OVERSOLD = 30          # chaomaiyuzhi
    
    def __init__(self):
        """chushihuaanalysisqi"""
        pass
    
    def analyze(self, df: pd.DataFrame, code: str) -> TrendAnalysisResult:
        """
        analysisstockqushi
        
        Args:
            df: baohan OHLCV shujude DataFrame
            code: stockdaima
            
        Returns:
            TrendAnalysisResult analysisjieguo
        """
        result = TrendAnalysisResult(code=code)
        
        if df is None or df.empty or len(df) < 20:
            logger.warning(f"{code} shujubuzu竊똷ufajinxingqushianalysis")
            result.risk_factors.append("shujubuzu竊똷ufawanchenganalysis")
            return result
        
        # quebaoshujuanriqipaixu
        df = df.sort_values('date').reset_index(drop=True)
        
        # jisuanjunxian
        df = self._calculate_mas(df)

        # jisuan MACD he RSI
        df = self._calculate_macd(df)
        df = self._calculate_rsi(df)

        # huoquzuixinshuju
        latest = df.iloc[-1]
        result.current_price = float(latest['close'])
        result.ma5 = float(latest['MA5'])
        result.ma10 = float(latest['MA10'])
        result.ma20 = float(latest['MA20'])
        result.ma60 = float(latest.get('MA60', 0))

        # 1. qushipanduan
        self._analyze_trend(df, result)

        # 2. guaililvjisuan
        self._calculate_bias(result)

        # 3. liangnenganalysis
        self._analyze_volume(df, result)

        # 4. zhichengyalianalysis
        self._analyze_support_resistance(df, result)

        # 5. MACD analysis
        self._analyze_macd(df, result)

        # 6. RSI analysis
        self._analyze_rsi(df, result)

        # 7. shengchengmairuxinhao
        self._generate_signal(result)

        return result
    
    def _calculate_mas(self, df: pd.DataFrame) -> pd.DataFrame:
        """jisuanjunxian"""
        df = df.copy()
        df['MA5'] = df['close'].rolling(window=5).mean()
        df['MA10'] = df['close'].rolling(window=10).mean()
        df['MA20'] = df['close'].rolling(window=20).mean()
        if len(df) >= 60:
            df['MA60'] = df['close'].rolling(window=60).mean()
        else:
            df['MA60'] = df['MA20']  # shujubuzushishiyong MA20 tidai
        return df

    def _calculate_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        jisuan MACD zhibiao

        gongshi竊?
        - EMA(12)竊?2rizhishuyidongpingjun
        - EMA(26)竊?6rizhishuyidongpingjun
        - DIF = EMA(12) - EMA(26)
        - DEA = EMA(DIF, 9)
        - MACD = (DIF - DEA) * 2
        """
        df = df.copy()

        # jisuankuaimanxian EMA
        ema_fast = df['close'].ewm(span=self.MACD_FAST, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.MACD_SLOW, adjust=False).mean()

        # jisuankuaixian DIF
        df['MACD_DIF'] = ema_fast - ema_slow

        # jisuanxinhaoxian DEA
        df['MACD_DEA'] = df['MACD_DIF'].ewm(span=self.MACD_SIGNAL, adjust=False).mean()

        # jisuanzhuzhuangtu
        df['MACD_BAR'] = (df['MACD_DIF'] - df['MACD_DEA']) * 2

        return df

    def _calculate_rsi(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        jisuan RSI zhibiao

        gongshi竊?
        - RS = pingjunshangzhangfudu / pingjunxiadiefudu
        - RSI = 100 - (100 / (1 + RS))
        """
        df = df.copy()

        for period in [self.RSI_SHORT, self.RSI_MID, self.RSI_LONG]:
            # jisuanjiagebianhua
            delta = df['close'].diff()

            # fenlishangzhanghexiadie
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)

            # jisuanpingjunzhangdiefu
            avg_gain = gain.rolling(window=period).mean()
            avg_loss = loss.rolling(window=period).mean()

            # jisuan RS he RSI
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            # tianchong NaN zhi
            rsi = rsi.fillna(50)  # morenneutralzhi

            # adddao DataFrame
            col_name = f'RSI_{period}'
            df[col_name] = rsi

        return df
    
    def _analyze_trend(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """
        analysisqushizhuangtai
        
        hexinluoji竊쉚anduanjunxianpailiehequshiqiangdu
        """
        ma5, ma10, ma20 = result.ma5, result.ma10, result.ma20
        
        # panduanjunxianpailie
        if ma5 > ma10 > ma20:
            # jianchajianjushifouzaikuoda竊늫iangshi竊?
            prev = df.iloc[-5] if len(df) >= 5 else df.iloc[-1]
            prev_spread = (prev['MA5'] - prev['MA20']) / prev['MA20'] * 100 if prev['MA20'] > 0 else 0
            curr_spread = (ma5 - ma20) / ma20 * 100 if ma20 > 0 else 0
            
            if curr_spread > prev_spread and curr_spread > 5:
                result.trend_status = TrendStatus.STRONG_BULL
                result.ma_alignment = "qiangshiduotoupailie竊똨unxianfasanshanghang"
                result.trend_strength = 90
            else:
                result.trend_status = TrendStatus.BULL
                result.ma_alignment = "duotoupailie MA5>MA10>MA20"
                result.trend_strength = 75
                
        elif ma5 > ma10 and ma10 <= ma20:
            result.trend_status = TrendStatus.WEAK_BULL
            result.ma_alignment = "ruoshiduotou竊똌A5>MA10 dan MA10?짳A20"
            result.trend_strength = 55
            
        elif ma5 < ma10 < ma20:
            prev = df.iloc[-5] if len(df) >= 5 else df.iloc[-1]
            prev_spread = (prev['MA20'] - prev['MA5']) / prev['MA5'] * 100 if prev['MA5'] > 0 else 0
            curr_spread = (ma20 - ma5) / ma5 * 100 if ma5 > 0 else 0
            
            if curr_spread > prev_spread and curr_spread > 5:
                result.trend_status = TrendStatus.STRONG_BEAR
                result.ma_alignment = "qiangshikongtoupailie竊똨unxianfasanxiaxing"
                result.trend_strength = 10
            else:
                result.trend_status = TrendStatus.BEAR
                result.ma_alignment = "kongtoupailie MA5<MA10<MA20"
                result.trend_strength = 25
                
        elif ma5 < ma10 and ma10 >= ma20:
            result.trend_status = TrendStatus.WEAK_BEAR
            result.ma_alignment = "ruoshikongtou竊똌A5<MA10 dan MA10?쩗A20"
            result.trend_strength = 40
            
        else:
            result.trend_status = TrendStatus.CONSOLIDATION
            result.ma_alignment = "junxianchanrao竊똰ushibuming"
            result.trend_strength = 50
    
    def _calculate_bias(self, result: TrendAnalysisResult) -> None:
        """
        jisuanguaililv
        
        guaililv = (xianjia - junxian) / junxian * 100%
        
        yanjincelve竊쉍uaililvchaoguo 5% buzhuigao
        """
        price = result.current_price
        
        if result.ma5 > 0:
            result.bias_ma5 = (price - result.ma5) / result.ma5 * 100
        if result.ma10 > 0:
            result.bias_ma10 = (price - result.ma10) / result.ma10 * 100
        if result.ma20 > 0:
            result.bias_ma20 = (price - result.ma20) / result.ma20 * 100
    
    def _analyze_volume(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """
        analysisliangneng
        
        pianhao竊쉝uolianghuidiao > fangliangshangzhang > suoliangshangzhang > fangliangxiadie
        """
        if len(df) < 5:
            return
        
        latest = df.iloc[-1]
        vol_5d_avg = df['volume'].iloc[-6:-1].mean()
        
        if vol_5d_avg > 0:
            result.volume_ratio_5d = float(latest['volume']) / vol_5d_avg
        
        # panduanjiagebianhua
        prev_close = df.iloc[-2]['close']
        price_change = (latest['close'] - prev_close) / prev_close * 100
        
        # liangnengzhuangtaipanduan
        if result.volume_ratio_5d >= self.VOLUME_HEAVY_RATIO:
            if price_change > 0:
                result.volume_status = VolumeStatus.HEAVY_VOLUME_UP
                result.volume_trend = "거래량 증가와 함께 상승, 매수세가 강합니다."
            else:
                result.volume_status = VolumeStatus.HEAVY_VOLUME_DOWN
                result.volume_trend = "거래량 증가와 함께 하락, 주의가 필요합니다."
        elif result.volume_ratio_5d <= self.VOLUME_SHRINK_RATIO:
            if price_change > 0:
                result.volume_status = VolumeStatus.SHRINK_VOLUME_UP
                result.volume_trend = "거래량 감소 속 상승, 상승 동력이 부족할 수 있습니다."
            else:
                result.volume_status = VolumeStatus.SHRINK_VOLUME_DOWN
                result.volume_trend = "거래량 감소 속 조정, 매물 소화 흐름으로 볼 수 있습니다."
        else:
            result.volume_status = VolumeStatus.NORMAL
            result.volume_trend = "거래량은 정상 범위입니다."
    
    def _analyze_support_resistance(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """
        analysiszhichengyaliwei
        
        maidianpianhao竊쉎uicai MA5/MA10 huodezhicheng
        """
        price = result.current_price
        
        # jianchashifouzai MA5 fujinhuodezhicheng
        if result.ma5 > 0:
            ma5_distance = abs(price - result.ma5) / result.ma5
            if ma5_distance <= self.MA_SUPPORT_TOLERANCE and price >= result.ma5:
                result.support_ma5 = True
                result.support_levels.append(result.ma5)
        
        # jianchashifouzai MA10 fujinhuodezhicheng
        if result.ma10 > 0:
            ma10_distance = abs(price - result.ma10) / result.ma10
            if ma10_distance <= self.MA_SUPPORT_TOLERANCE and price >= result.ma10:
                result.support_ma10 = True
                if result.ma10 not in result.support_levels:
                    result.support_levels.append(result.ma10)
        
        # MA20 zuoweizhongyaozhicheng
        if result.ma20 > 0 and price >= result.ma20:
            result.support_levels.append(result.ma20)
        
        # jinqigaodianzuoweiyali
        if len(df) >= 20:
            recent_high = df['high'].iloc[-20:].max()
            if recent_high > price:
                result.resistance_levels.append(recent_high)

    def _analyze_macd(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """
        analysis MACD zhibiao

        hexinxinhao竊?
        - lingzhoushangjincha竊쉦uiqiangmairuxinhao
        - jincha竊숧IF shangchuan DEA
        - sicha竊숧IF xiachuan DEA
        """
        if len(df) < self.MACD_SLOW:
            result.macd_signal = "shujubuzu"
            return

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # huoqu MACD shuju
        result.macd_dif = float(latest['MACD_DIF'])
        result.macd_dea = float(latest['MACD_DEA'])
        result.macd_bar = float(latest['MACD_BAR'])

        # panduanjinchasicha
        prev_dif_dea = prev['MACD_DIF'] - prev['MACD_DEA']
        curr_dif_dea = result.macd_dif - result.macd_dea

        # jincha竊숧IF shangchuan DEA
        is_golden_cross = prev_dif_dea <= 0 and curr_dif_dea > 0

        # sicha竊숧IF xiachuan DEA
        is_death_cross = prev_dif_dea >= 0 and curr_dif_dea < 0

        # lingzhouchuanyue
        prev_zero = prev['MACD_DIF']
        curr_zero = result.macd_dif
        is_crossing_up = prev_zero <= 0 and curr_zero > 0
        is_crossing_down = prev_zero >= 0 and curr_zero < 0

        # panduan MACD zhuangtai
        if is_golden_cross and curr_zero > 0:
            result.macd_status = MACDStatus.GOLDEN_CROSS_ZERO
            result.macd_signal = "0선 위 골든크로스, 강한 매수 신호입니다."
        elif is_crossing_up:
            result.macd_status = MACDStatus.CROSSING_UP
            result.macd_signal = "DIF가 0선을 상향 돌파해 추세가 강해지고 있습니다."
        elif is_golden_cross:
            result.macd_status = MACDStatus.GOLDEN_CROSS
            result.macd_signal = "골든크로스, 추세가 위쪽입니다."
        elif is_death_cross:
            result.macd_status = MACDStatus.DEATH_CROSS
            result.macd_signal = "데드크로스, 추세가 아래쪽입니다."
        elif is_crossing_down:
            result.macd_status = MACDStatus.CROSSING_DOWN
            result.macd_signal = "DIF가 0선을 하향 돌파해 추세가 약해지고 있습니다."
        elif result.macd_dif > 0 and result.macd_dea > 0:
            result.macd_status = MACDStatus.BULLISH
            result.macd_signal = "MACD가 강세 배열을 유지하고 있습니다."
        elif result.macd_dif < 0 and result.macd_dea < 0:
            result.macd_status = MACDStatus.BEARISH
            result.macd_signal = "MACD가 약세 배열을 유지하고 있습니다."
        else:
            result.macd_status = MACDStatus.BULLISH
            result.macd_signal = "MACD는 중립 구간입니다."

    def _analyze_rsi(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """
        analysis RSI zhibiao

        hexinpanduan竊?
        - RSI > 70竊쉉haomai竊똨inshenzhuigao
        - RSI < 30竊쉉haomai竊똤uanzhufantan
        - 40-60竊쉦hongxingquyu
        """
        if len(df) < self.RSI_LONG:
            result.rsi_signal = "shujubuzu"
            return

        latest = df.iloc[-1]

        # huoqu RSI shuju
        result.rsi_6 = float(latest[f'RSI_{self.RSI_SHORT}'])
        result.rsi_12 = float(latest[f'RSI_{self.RSI_MID}'])
        result.rsi_24 = float(latest[f'RSI_{self.RSI_LONG}'])

        # yizhongqi RSI(12) weizhujinxingpanduan
        rsi_mid = result.rsi_12

        # panduan RSI zhuangtai
        if rsi_mid > self.RSI_OVERBOUGHT:
            result.rsi_status = RSIStatus.OVERBOUGHT
            result.rsi_signal = f"?좑툘 RSIchaomai({rsi_mid:.1f}>70)竊똡uanqihuidiaofengxiangao"
        elif rsi_mid > 60:
            result.rsi_status = RSIStatus.STRONG_BUY
            result.rsi_signal = f"??RSIqiangshi({rsi_mid:.1f})竊똡uotouliliangchongzu"
        elif rsi_mid >= 40:
            result.rsi_status = RSIStatus.NEUTRAL
            result.rsi_signal = f" RSIneutral({rsi_mid:.1f})竊똺hendangzhenglizhong"
        elif rsi_mid >= self.RSI_OVERSOLD:
            result.rsi_status = RSIStatus.WEAK
            result.rsi_signal = f"??RSIruoshi({rsi_mid:.1f})竊똤uanzhufantan"
        else:
            result.rsi_status = RSIStatus.OVERSOLD
            result.rsi_signal = f"狩?RSIchaomai({rsi_mid:.1f}<30)竊똣antanjihuida"

    def _generate_signal(self, result: TrendAnalysisResult) -> None:
        """
        shengchengmairuxinhao

        zonghepinganalysistong竊?
        - qushi竊?0fen竊됵폏duotoupailiedefengao
        - guaililv竊?0fen竊됵폏jiejin MA5 defengao
        - liangneng竊?5fen竊됵폏suolianghuidiaodefengao
        - zhicheng竊?0fen竊됵폏huodejunxianzhichengdefengao
        - MACD竊?5fen竊됵폏jinchaheduotoudefengao
        - RSI竊?0fen竊됵폏chaomaiheqiangshidefengao
        """
        score = 0
        reasons = []
        risks = []

        # === qushipingfen竊?0fen竊?==
        trend_scores = {
            TrendStatus.STRONG_BULL: 30,
            TrendStatus.BULL: 26,
            TrendStatus.WEAK_BULL: 18,
            TrendStatus.CONSOLIDATION: 12,
            TrendStatus.WEAK_BEAR: 8,
            TrendStatus.BEAR: 4,
            TrendStatus.STRONG_BEAR: 0,
        }
        trend_score = trend_scores.get(result.trend_status, 12)
        score += trend_score

        if result.trend_status in [TrendStatus.STRONG_BULL, TrendStatus.BULL]:
            reasons.append(f"??{result.trend_status.value}竊똲hunshizuoduo")
        elif result.trend_status in [TrendStatus.BEAR, TrendStatus.STRONG_BEAR]:
            risks.append(f"?좑툘 {result.trend_status.value}竊똟uyizuoduo")

        # === guaililvpingfen竊?0fen竊똰iangshiqushibuchang竊?==
        bias = result.bias_ma5
        if bias != bias or bias is None:  # NaN or None defense
            bias = 0.0
        base_threshold = get_config().bias_threshold

        # Strong trend compensation: relax threshold for STRONG_BULL with high strength
        trend_strength = result.trend_strength if result.trend_strength == result.trend_strength else 0.0
        if result.trend_status == TrendStatus.STRONG_BULL and (trend_strength or 0) >= 70:
            effective_threshold = base_threshold * 1.5
            is_strong_trend = True
        else:
            effective_threshold = base_threshold
            is_strong_trend = False

        if bias < 0:
            # Price below MA5 (pullback)
            if bias > -3:
                score += 20
                reasons.append(f"??jiagelvediyuMA5({bias:.1f}%)竊똦uicaimaidian")
            elif bias > -5:
                score += 16
                reasons.append(f"??jiagehuicaiMA5({bias:.1f}%)竊똤uanchazhicheng")
            else:
                score += 8
                risks.append(f"?좑툘 guaililvguoda({bias:.1f}%)竊똩enengpowei")
        elif bias < 2:
            score += 18
            reasons.append(f"가격이 MA5에 근접했습니다({bias:.1f}%). 진입 타이밍이 양호합니다.")
        elif bias < base_threshold:
            score += 14
            reasons.append(f"가격이 MA5보다 약간 높습니다({bias:.1f}%). 소량 진입을 검토할 수 있습니다.")
        elif bias > effective_threshold:
            score += 4
            risks.append(
                f"이격도가 높습니다({bias:.1f}%>{effective_threshold:.1f}%). 추격 매수는 피해야 합니다."
            )
        elif bias > base_threshold and is_strong_trend:
            score += 10
            reasons.append(
                f"강한 추세 속 이격도가 다소 높습니다({bias:.1f}%). 가벼운 비중으로 추적하세요."
            )
        else:
            score += 4
            risks.append(
                f"이격도가 높습니다({bias:.1f}%>{base_threshold:.1f}%). 추격 매수는 피해야 합니다."
            )

        # === liangnengpingfen竊?5fen竊?==
        volume_scores = {
            VolumeStatus.SHRINK_VOLUME_DOWN: 15,  # suolianghuidiaozuijia
            VolumeStatus.HEAVY_VOLUME_UP: 12,     # fangliangshangzhangcizhi
            VolumeStatus.NORMAL: 10,
            VolumeStatus.SHRINK_VOLUME_UP: 6,     # wuliangshangzhangjiaocha
            VolumeStatus.HEAVY_VOLUME_DOWN: 0,    # fangliangxiadiezuicha
        }
        vol_score = volume_scores.get(result.volume_status, 8)
        score += vol_score

        if result.volume_status == VolumeStatus.SHRINK_VOLUME_DOWN:
            reasons.append("??suolianghuidiao竊똺hulixipan")
        elif result.volume_status == VolumeStatus.HEAVY_VOLUME_DOWN:
            risks.append("?좑툘 fangliangxiadie竊똺huyifengxian")

        # === zhichengpingfen竊?0fen竊?==
        if result.support_ma5:
            score += 5
            reasons.append("??MA5zhichengyouxiao")
        if result.support_ma10:
            score += 5
            reasons.append("??MA10zhichengyouxiao")

        # === MACD pingfen竊?5fen竊?==
        macd_scores = {
            MACDStatus.GOLDEN_CROSS_ZERO: 15,  # lingzhoushangjinchazuiqiang
            MACDStatus.GOLDEN_CROSS: 12,      # jincha
            MACDStatus.CROSSING_UP: 10,       # shangchuanlingzhou
            MACDStatus.BULLISH: 8,            # duotou
            MACDStatus.BEARISH: 2,            # kongtou
            MACDStatus.CROSSING_DOWN: 0,       # xiachuanlingzhou
            MACDStatus.DEATH_CROSS: 0,        # sicha
        }
        macd_score = macd_scores.get(result.macd_status, 5)
        score += macd_score

        if result.macd_status in [MACDStatus.GOLDEN_CROSS_ZERO, MACDStatus.GOLDEN_CROSS]:
            reasons.append(f"??{result.macd_signal}")
        elif result.macd_status in [MACDStatus.DEATH_CROSS, MACDStatus.CROSSING_DOWN]:
            risks.append(f"?좑툘 {result.macd_signal}")
        else:
            reasons.append(result.macd_signal)

        # === RSI pingfen竊?0fen竊?==
        rsi_scores = {
            RSIStatus.OVERSOLD: 10,       # chaomaizuijia
            RSIStatus.STRONG_BUY: 8,     # qiangshi
            RSIStatus.NEUTRAL: 5,        # neutral
            RSIStatus.WEAK: 3,            # ruoshi
            RSIStatus.OVERBOUGHT: 0,       # chaomaizuicha
        }
        rsi_score = rsi_scores.get(result.rsi_status, 5)
        score += rsi_score

        if result.rsi_status in [RSIStatus.OVERSOLD, RSIStatus.STRONG_BUY]:
            reasons.append(f"??{result.rsi_signal}")
        elif result.rsi_status == RSIStatus.OVERBOUGHT:
            risks.append(f"?좑툘 {result.rsi_signal}")
        else:
            reasons.append(result.rsi_signal)

        # === zonghepanduan ===
        result.signal_score = score
        result.signal_reasons = reasons
        result.risk_factors = risks

        # shengchengmairuxinhao竊늯iaozhengyuzhiyishiyingxinde100fenzhi竊?
        if score >= 75 and result.trend_status in [TrendStatus.STRONG_BULL, TrendStatus.BULL]:
            result.buy_signal = BuySignal.STRONG_BUY
        elif score >= 60 and result.trend_status in [TrendStatus.STRONG_BULL, TrendStatus.BULL, TrendStatus.WEAK_BULL]:
            result.buy_signal = BuySignal.BUY
        elif score >= 45:
            result.buy_signal = BuySignal.HOLD
        elif score >= 30:
            result.buy_signal = BuySignal.WAIT
        elif result.trend_status in [TrendStatus.BEAR, TrendStatus.STRONG_BEAR]:
            result.buy_signal = BuySignal.STRONG_SELL
        else:
            result.buy_signal = BuySignal.SELL
    
    def format_analysis(self, result: TrendAnalysisResult) -> str:
        """
        geshihuaanalysisjieguoweiwenben

        Args:
            result: analysisjieguo

        Returns:
            geshihuadeanalysiswenben
        """
        lines = [
            f"=== {result.code} qushianalysis ===",
            f"",
            f"?뱤 qushipanduan: {result.trend_status.value}",
            f"   junxianpailie: {result.ma_alignment}",
            f"   qushiqiangdu: {result.trend_strength}/100",
            f"",
            f"?뱢 junxianshuju:",
            f"   xianjia: {result.current_price:.2f}",
            f"   MA5:  {result.ma5:.2f} (guaili {result.bias_ma5:+.2f}%)",
            f"   MA10: {result.ma10:.2f} (guaili {result.bias_ma10:+.2f}%)",
            f"   MA20: {result.ma20:.2f} (guaili {result.bias_ma20:+.2f}%)",
            f"",
            f"?뱤 liangnenganalysis: {result.volume_status.value}",
            f"   liangbi(vs5ri): {result.volume_ratio_5d:.2f}",
            f"   liangnengqushi: {result.volume_trend}",
            f"",
            f"?뱢 MACDzhibiao: {result.macd_status.value}",
            f"   DIF: {result.macd_dif:.4f}",
            f"   DEA: {result.macd_dea:.4f}",
            f"   MACD: {result.macd_bar:.4f}",
            f"   xinhao: {result.macd_signal}",
            f"",
            f"?뱤 RSIzhibiao: {result.rsi_status.value}",
            f"   RSI(6): {result.rsi_6:.1f}",
            f"   RSI(12): {result.rsi_12:.1f}",
            f"   RSI(24): {result.rsi_24:.1f}",
            f"   xinhao: {result.rsi_signal}",
            f"",
            f"?렞 caozuojianyi: {result.buy_signal.value}",
            f"   zonghepingfen: {result.signal_score}/100",
        ]

        if result.signal_reasons:
            lines.append(f"")
            lines.append(f"??mairuliyou:")
            for reason in result.signal_reasons:
                lines.append(f"   {reason}")

        if result.risk_factors:
            lines.append(f"")
            lines.append(f"?좑툘 fengxianyinsu:")
            for risk in result.risk_factors:
                lines.append(f"   {risk}")

        return "\n".join(lines)


def analyze_stock(df: pd.DataFrame, code: str) -> TrendAnalysisResult:
    """
    bianjiehanshu竊쉌enxidanzhistock
    
    Args:
        df: baohan OHLCV shujude DataFrame
        code: stockdaima
        
    Returns:
        TrendAnalysisResult analysisjieguo
    """
    analyzer = StockTrendAnalyzer()
    return analyzer.analyze(df, code)


if __name__ == "__main__":
    # testdaima
    logging.basicConfig(level=logging.INFO)
    
    # monishujutest
    import numpy as np
    
    dates = pd.date_range(start='2025-01-01', periods=60, freq='D')
    np.random.seed(42)
    
    # moniduotoupailiedeshuju
    base_price = 10.0
    prices = [base_price]
    for i in range(59):
        change = np.random.randn() * 0.02 + 0.003  # qingweishangzhangqushi
        prices.append(prices[-1] * (1 + change))
    
    df = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': [p * (1 + np.random.uniform(0, 0.02)) for p in prices],
        'low': [p * (1 - np.random.uniform(0, 0.02)) for p in prices],
        'close': prices,
        'volume': [np.random.randint(1000000, 5000000) for _ in prices],
    })
    
    analyzer = StockTrendAnalyzer()
    result = analyzer.analyze(df, '000001')
    print(analyzer.format_analysis(result))

