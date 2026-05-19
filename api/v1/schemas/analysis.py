# -*- coding: utf-8 -*-

"""

===================================

analysisrelatedmodel

===================================



zhize竊?
1. dingyianalysisqingqiuhexiangyingmodel

2. dingyirenwuzhuangtaimodel

3. dingyiyiburenwuduilierelatedmodel

"""



from typing import Optional, List, Any

from enum import Enum



from pydantic import AliasChoices, BaseModel, Field

from src.utils.analysis_metadata import SELECTION_SOURCE_PATTERN





class TaskStatusEnum(str, Enum):

    """renwuzhuangtaimeiju"""

    PENDING = "pending"

    PROCESSING = "processing"

    COMPLETED = "completed"

    FAILED = "failed"





class AnalyzeRequest(BaseModel):

    """Analysis request parameters"""

    

    stock_code: Optional[str] = Field(

        None, 

        description="danzhistockdaima", 

        example="600519"

    )

    stock_codes: Optional[List[str]] = Field(

        None, 

        description="duozhistockdaima竊늶u stock_code erxuanyi竊?",

        example=["600519", "000858"]

    )

    report_type: str = Field(

        "detailed",

        description="baogaoleixing竊쉝imple(jingjian) / detailed(wanzheng) / full(wanzheng) / brief(jianjie)",

        pattern="^(simple|detailed|full|brief)$",

    )

    force_refresh: bool = Field(

        False,

        description="shifouqiangzhirefresh竊늜ulvehuancun竊?"

    )

    async_mode: bool = Field(

        False,

        description="shifoushiyongyibumoshi"

    )

    stock_name: Optional[str] = Field(

        None,

        description="yonghuxuanzhongdestockmingcheng竊늷idongbuquanshitigong竊?",

        example="Samsung Electronics"

    )

    original_query: Optional[str] = Field(

        None,

        description="yonghuyuanshishuru竊늭uSamsung?갾zmt??00519竊?",

        example="Samsung"

    )

    selection_source: Optional[str] = Field(

        None,

        description="stockxuanzelaiyuan竊쉖anual(shoudongshuru) | autocomplete(zidongbuquan) | import(daoru) | image(tupianshibie)",

        pattern=SELECTION_SOURCE_PATTERN,

        example="autocomplete"

    )

    notify: bool = Field(

        True,

        description="shifousendtuisongnotification竊늇elegram/qiyeweixindeng竊?"

    )

    skills: Optional[List[str]] = Field(

        None,

        validation_alias=AliasChoices("skills", "strategies"),

        description="bencianalysisshiyongdecelve skill ID liebiao竊쌼ianrong legacy strategies ziduan",

        example=["bull_trend", "growth_quality"]

    )



    class Config:

        json_schema_extra = {

            "example": {

                "stock_code": "600519",

                "report_type": "detailed",

                "force_refresh": False,

                "async_mode": False,

                "stock_name": "Samsung Electronics",

                "original_query": "Samsung",

                "selection_source": "autocomplete",

                "notify": True,

                "skills": ["bull_trend"]

            }

        }





class MarketReviewRequest(BaseModel):

    """Market review trigger parameters."""



    send_notification: bool = Field(

        True,

        description="shifouzaidapanfupanwanchenghousendtuisongnotification",

    )





class MarketReviewAccepted(BaseModel):

    """Market review background task accepted response."""



    status: str = Field("accepted", description="tijiaozhuangtai")

    message: str = Field(..., description="tishixinxi")

    send_notification: bool = Field(..., description="shifousendnotification")

    task_id: Optional[str] = Field(

        None,

        description="renwu ID竊늞indangrenwushijitijiaoshifanhui竊?",

    )





class AnalysisResultResponse(BaseModel):

    """analysisjieguoxiangyingmodel"""

    

    query_id: str = Field(..., description="analysisrecordweiyibiaoshi")

    stock_code: str = Field(..., description="stockdaima")

    stock_name: Optional[str] = Field(None, description="stockmingcheng")

    report: Optional[Any] = Field(None, description="analysisbaogao")

    created_at: str = Field(..., description="chuangjianshijian")

    

    class Config:

        json_schema_extra = {

            "example": {

                "query_id": "abc123def456",

                "stock_code": "600519",

                "stock_name": "Samsung Electronics",

                "report": {

                    "summary": {

                        "sentiment_score": 75,

                        "operation_advice": "chiyou"

                    }

                },

                "created_at": "2024-01-01T12:00:00"

            }

        }





class TaskAccepted(BaseModel):

    """yiburenwujieshouxiangying"""

    

    task_id: str = Field(..., description="renwu ID竊똹ongyuchaxunzhuangtai")

    status: str = Field(

        ..., 

        description="renwuzhuangtai",

        pattern="^(pending|processing)$"

    )

    message: Optional[str] = Field(None, description="tishixinxi")

    

    class Config:

        json_schema_extra = {

            "example": {

                "task_id": "task_abc123",

                "status": "pending",

                "message": "Analysis task accepted"

            }

        }





class BatchTaskAcceptedItem(BaseModel):

    """Accepted item in an async batch task."""



    task_id: str = Field(..., description="renwu ID竊똹ongyuchaxunzhuangtai")

    stock_code: str = Field(..., description="stockdaima")

    status: str = Field(

        ...,

        description="renwuzhuangtai",

        pattern="^(pending|processing)$"

    )

    message: Optional[str] = Field(None, description="tishixinxi")



    class Config:

        json_schema_extra = {

            "example": {

                "task_id": "task_abc123",

                "stock_code": "600519",

                "status": "pending",

                "message": "analysisrenwuyijiaruduilie: 600519"

            }

        }





class BatchDuplicateTaskItem(BaseModel):

    """Duplicate item in an async batch task."""



    stock_code: str = Field(..., description="stockdaima")

    existing_task_id: str = Field(..., description="yicunzaiderenwu ID")

    message: str = Field(..., description="cuowuxinxi")



    class Config:

        json_schema_extra = {

            "example": {

                "stock_code": "600519",

                "existing_task_id": "task_existing_123",

                "message": "stock 600519 in_progressanalysiszhong (task_id: task_existing_123)"

            }

        }





class BatchTaskAcceptedResponse(BaseModel):

    """Response for accepted async batch tasks."""



    accepted: List[BatchTaskAcceptedItem] = Field(default_factory=list, description="chenggongtijiaoderenwuliebiao")

    duplicates: List[BatchDuplicateTaskItem] = Field(default_factory=list, description="chongfuertiaoguoderenwuliebiao")

    message: str = Field(..., description="huizongxinxi")



    class Config:

        json_schema_extra = {

            "example": {

                "accepted": [

                    {

                        "task_id": "task_abc123",

                        "stock_code": "600519",

                        "status": "pending",

                        "message": "analysisrenwuyijiaruduilie: 600519"

                    }

                ],

                "duplicates": [

                    {

                        "stock_code": "000858",

                        "existing_task_id": "task_existing_456",

                        "message": "stock 000858 in_progressanalysiszhong (task_id: task_existing_456)"

                    }

                ],

                "message": "yitijiao 1 gerenwu竊? gechongfutiaoguo"

            }

        }





class TaskStatus(BaseModel):

    """Task status model"""

    

    task_id: str = Field(..., description="renwu ID")

    status: str = Field(

        ..., 

        description="renwuzhuangtai",

        pattern="^(pending|processing|completed|failed)$"

    )

    progress: Optional[int] = Field(

        None, 

        description="jindubaifenbi (0-100)",

        ge=0,

        le=100

    )

    result: Optional[AnalysisResultResponse] = Field(

        None, 

        description="analysisjieguo竊늞inzai completed shicunzai竊?"

    )

    market_review_report: Optional[str] = Field(

        None,

        description="dapanfupanrenwufanhuidebaogaowenben竊늞indapanfupanrenwu竊?",

    )

    error: Optional[str] = Field(

        None, 

        description="cuowuxinxi竊늞inzai failed shicunzai竊?"

    )

    stock_name: Optional[str] = Field(None, description="stockmingcheng")

    original_query: Optional[str] = Field(None, description="yonghuyuanshishuru")

    selection_source: Optional[str] = Field(

        None,

        description="xuanzelaiyuan",

        pattern=SELECTION_SOURCE_PATTERN,

    )

    skills: Optional[List[str]] = Field(None, description="bencirenwushiyongdecelve skill ID liebiao")

    

    class Config:

        json_schema_extra = {

            "example": {

                "task_id": "task_abc123",

                "status": "completed",

                "progress": 100,

                "result": None,

                "market_review_report": None,

                "error": None,

                "stock_name": "Samsung Electronics",

                "original_query": "Samsung",

                "selection_source": "autocomplete",

                "skills": ["bull_trend"]

            }

        }





class TaskInfo(BaseModel):

    """

    Task details model



    Used for task list and SSE event delivery

    """

    

    task_id: str = Field(..., description="renwu ID")

    stock_code: str = Field(..., description="stockdaima")

    stock_name: Optional[str] = Field(None, description="stockmingcheng")

    status: TaskStatusEnum = Field(..., description="renwuzhuangtai")

    progress: int = Field(0, description="jindubaifenbi (0-100)", ge=0, le=100)

    message: Optional[str] = Field(None, description="zhuangtaixiaoxi")

    report_type: str = Field("detailed", description="baogaoleixing")

    created_at: str = Field(..., description="chuangjianshijian")

    started_at: Optional[str] = Field(None, description="kaishizhixingshijian")

    completed_at: Optional[str] = Field(None, description="wanchengshijian")

    error: Optional[str] = Field(None, description="cuowuxinxi竊늞inzai failed shicunzai竊?")

    original_query: Optional[str] = Field(None, description="yonghuyuanshishuru")

    selection_source: Optional[str] = Field(

        None,

        description="xuanzelaiyuan",

        pattern=SELECTION_SOURCE_PATTERN,

    )

    skills: Optional[List[str]] = Field(None, description="bencirenwushiyongdecelve skill ID liebiao")

    

    class Config:

        json_schema_extra = {

            "example": {

                "task_id": "abc123def456",

                "stock_code": "600519",

                "stock_name": "Samsung Electronics",

                "status": "processing",

                "progress": 50,

                "message": "in_progressanalysiszhong...",

                "report_type": "detailed",

                "created_at": "2026-02-05T10:30:00",

                "started_at": "2026-02-05T10:30:01",

                "completed_at": None,

                "error": None,

                "original_query": "Samsung",

                "selection_source": "autocomplete",

                "skills": ["bull_trend"]

            }

        }





class TaskListResponse(BaseModel):

    """renwuliebiaoxiangyingmodel"""

    

    total: int = Field(..., description="renwuzongshu")

    pending: int = Field(..., description="dengdaizhongderenwushu")

    processing: int = Field(..., description="chulizhongderenwushu")

    tasks: List[TaskInfo] = Field(..., description="renwuliebiao")

    

    class Config:

        json_schema_extra = {

            "example": {

                "total": 3,

                "pending": 1,

                "processing": 2,

                "tasks": []

            }

        }





class DuplicateTaskErrorResponse(BaseModel):

    """chongfurenwucuowuxiangyingmodel"""

    

    error: str = Field("duplicate_task", description="cuowuleixing")

    message: str = Field(..., description="cuowuxinxi")

    stock_code: str = Field(..., description="stockdaima")

    existing_task_id: str = Field(..., description="yicunzaiderenwu ID")

    

    class Config:

        json_schema_extra = {

            "example": {

                "error": "duplicate_task",

                "message": "stock 600519 in_progressanalysiszhong",

                "stock_code": "600519",

                "existing_task_id": "abc123def456"

            }

        }


