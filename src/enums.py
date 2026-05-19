# -*- coding: utf-8 -*-
"""
===================================
meijuleixingdingyi
===================================

jizhongguanlixitongretryyongdemeijuleixing竊똳igongleixinganquanhedaimakeduxing??
"""

from enum import Enum


class ReportType(str, Enum):
    """
    baogaoleixingmeiju

    yongyu API chufaanalysisshixuanzetuisongdebaogaogeshi??
    jicheng str shiqikeyizhijieyuzifuchuanbijiaohexuliehua??
    """
    SIMPLE = "simple"  # jingjianbaogao竊쉝hiyong generate_single_stock_report
    FULL = "full"      # wanzhengbaogao竊쉝hiyong generate_dashboard_report
    BRIEF = "brief"    # jianjiemoshi竊?-5 juhuagaikuo竊똲hiheyidongduan/tuisong

    @classmethod
    def from_str(cls, value: str) -> "ReportType":
        """
        congzifuchuananquandizhuanhuanweimeijuzhi
        
        Args:
            value: zifuchuanzhi
            
        Returns:
            duiyingdemeijuzhi竊똷uxiaoshurufanhuimorenzhi SIMPLE
        """
        try:
            normalized = value.lower().strip()
            if normalized == "detailed":
                normalized = cls.FULL.value
            return cls(normalized)
        except (ValueError, AttributeError):
            return cls.SIMPLE
    
    @property
    def display_name(self) -> str:
        """huoquyongyuxianshidemingcheng"""
        return {
            ReportType.SIMPLE: "jingjianbaogao",
            ReportType.FULL: "wanzhengbaogao",
            ReportType.BRIEF: "jianjiebaogao",
        }.get(self, "jingjianbaogao")

