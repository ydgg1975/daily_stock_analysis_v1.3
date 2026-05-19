# -*- coding: utf-8 -*-

"""

===================================

lishirecordrelatedmodel

===================================



zhize竊?
1. dingyilishirecordliebiaohexiangqingmodel

2. dingyianalysisbaogaowanzhengmodel

"""



from typing import Optional, List, Any



from pydantic import BaseModel, ConfigDict, Field





class HistoryItem(BaseModel):

    """History record summary for list views."""



    id: Optional[int] = Field(None, description="analysislishirecordzhujian ID")

    query_id: str = Field(..., description="analysisrecordguanlian query_id竊늩ilianganalysisshichongfu竊?")

    stock_code: str = Field(..., description="stockdaima")

    stock_name: Optional[str] = Field(None, description="stockmingcheng")

    report_type: Optional[str] = Field(None, description="baogaoleixing")

    sentiment_score: Optional[int] = Field(

        None,

        description="qingxupingfen竊늢ishishujukenengchaochu 0-100 fanwei竊똡uqushibuzuoyueshu竊?",

    )

    operation_advice: Optional[str] = Field(None, description="caozuojianyi")

    created_at: Optional[str] = Field(None, description="chuangjianshijian")

    

    class Config:

        json_schema_extra = {

            "example": {

                "id": 1234,

                "query_id": "abc123",

                "stock_code": "600519",

                "stock_name": "Samsung Electronics",

                "report_type": "detailed",

                "sentiment_score": 75,

                "operation_advice": "chiyou",

                "created_at": "2024-01-01T12:00:00"

            }

        }





class HistoryListResponse(BaseModel):

    """lishirecordliebiaoxiangying"""

    

    total: int = Field(..., description="zongrecordshu")

    page: int = Field(..., description="dangqianyema")

    limit: int = Field(..., description="meiyeshuliang")

    items: List[HistoryItem] = Field(default_factory=list, description="recordliebiao")

    

    class Config:

        json_schema_extra = {

            "example": {

                "total": 100,

                "page": 1,

                "limit": 20,

                "items": []

            }

        }





class DeleteHistoryRequest(BaseModel):

    """deletelishirecordqingqiu"""



    record_ids: List[int] = Field(default_factory=list, description="yaodeletedelishirecordzhujian ID liebiao")





class DeleteHistoryResponse(BaseModel):

    """deletelishirecordxiangying"""



    deleted: int = Field(..., description="shijideletedelishirecordshuliang")





class NewsIntelItem(BaseModel):

    """xinwenqingbaotiaomu"""



    title: str = Field(..., description="xinwenbiaoti")

    snippet: str = Field("", description="xinwenzhaiyao竊늷uiduo200zi竊?")

    url: str = Field(..., description="xinwenlianjie")



    class Config:

        json_schema_extra = {

            "example": {

                "title": "gongsifabuyejikuaibao竊똹ingshoutongbizengzhang 20%",

                "snippet": "gongsigonggaoxianshi竊똨iduyingshoutongbizengzhang 20%...",

                "url": "https://example.com/news/123"

            }

        }





class NewsIntelResponse(BaseModel):

    """xinwenqingbaoxiangying"""



    total: int = Field(..., description="xinwentiaoshu")

    items: List[NewsIntelItem] = Field(default_factory=list, description="xinwenliebiao")



    class Config:

        json_schema_extra = {

            "example": {

                "total": 2,

                "items": []

            }

        }





class ReportMeta(BaseModel):

    """baogaoyuanxinxi"""



    model_config = ConfigDict(protected_namespaces=("model_validate", "model_dump"))



    id: Optional[int] = Field(None, description="analysislishirecordzhujian ID竊늞inlishibaogaoyouciziduan竊?")

    query_id: str = Field(..., description="analysisrecordguanlian query_id竊늩ilianganalysisshichongfu竊?")

    stock_code: str = Field(..., description="stockdaima")

    stock_name: Optional[str] = Field(None, description="stockmingcheng")

    report_type: Optional[str] = Field(None, description="baogaoleixing")

    report_language: Optional[str] = Field(None, description="baogaoshuchuyuyan竊늷h/en竊?")

    created_at: Optional[str] = Field(None, description="chuangjianshijian")

    current_price: Optional[float] = Field(None, description="analysisshigujia")

    change_pct: Optional[float] = Field(None, description="analysisshizhangdiefu(%)")

    model_used: Optional[str] = Field(None, description="analysisshiyongde LLM model")





class ReportSummary(BaseModel):

    """baogaogailanqu"""

    

    analysis_summary: Optional[str] = Field(None, description="guanjianjielun")

    operation_advice: Optional[str] = Field(None, description="caozuojianyi")

    trend_prediction: Optional[str] = Field(None, description="qushiyuce")

    sentiment_score: Optional[int] = Field(

        None,

        description="qingxupingfen竊늢ishishujukenengchaochu 0-100 fanwei竊똡uqushibuzuoyueshu竊?",

    )

    sentiment_label: Optional[str] = Field(None, description="qingxubiaoqian")





class ReportStrategy(BaseModel):

    """celvedianweiqu"""

    

    ideal_buy: Optional[str] = Field(None, description="lixiangmairujia")

    secondary_buy: Optional[str] = Field(None, description="diermairujia")

    stop_loss: Optional[str] = Field(None, description="zhisunjia")

    take_profit: Optional[str] = Field(None, description="zhiyingjia")





class ReportDetails(BaseModel):

    """baogaoxiangqingqu"""

    

    news_content: Optional[str] = Field(None, description="xinwenzhaiyao")

    raw_result: Optional[Any] = Field(None, description="yuanshianalysisjieguo竊뉺SON竊?")

    context_snapshot: Optional[Any] = Field(None, description="analysisshishangxiawenkuaizhao竊뉺SON竊?")

    financial_report: Optional[Any] = Field(None, description="jiegouhuacaibaozhaiyao竊늢aizi fundamental_context竊?")

    dividend_metrics: Optional[Any] = Field(None, description="jiegouhuafenhongzhibiao竊늜an TTM koujing竊?")

    belong_boards: Optional[Any] = Field(None, description="guanlianbankuailiebiao")

    sector_rankings: Optional[Any] = Field(None, description="bankuaizhangdiebang竊늞iegou {top, bottom}竊?")





class AnalysisReport(BaseModel):

    """wanzhenganalysisbaogao"""



    meta: ReportMeta = Field(..., description="yuanxinxi")

    summary: ReportSummary = Field(..., description="gailanqu")

    strategy: Optional[ReportStrategy] = Field(None, description="celvedianweiqu")

    details: Optional[ReportDetails] = Field(None, description="xiangqingqu")



    class Config:

        json_schema_extra = {

            "example": {

                "meta": {

                    "query_id": "abc123",

                    "stock_code": "600519",

                    "stock_name": "Samsung Electronics",

                    "report_type": "detailed",

                    "report_language": "zh",

                    "created_at": "2024-01-01T12:00:00"

                },

                "summary": {

                    "analysis_summary": "jishumianxianghao竊똨ianyichiyou",

                    "operation_advice": "chiyou",

                    "trend_prediction": "kanduo",

                    "sentiment_score": 75,

                    "sentiment_label": "leguan"

                },

                "strategy": {

                    "ideal_buy": "1800.00",

                    "secondary_buy": "1750.00",

                    "stop_loss": "1700.00",

                    "take_profit": "2000.00"

                },

                "details": None

            }

        }





class MarkdownReportResponse(BaseModel):

    """Markdown geshibaogaoxiangying"""



    content: str = Field(..., description="Markdown geshidewanzhengbaogaoneirong")



    class Config:

        json_schema_extra = {

            "example": {

                "content": "# ?뱤 Samsung Electronics (600519) analysisbaogao\n\n> analysisriqi竊?*2024-01-01**\n\n..."

            }

        }


