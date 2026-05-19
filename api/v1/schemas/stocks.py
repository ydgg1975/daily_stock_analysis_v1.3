# -*- coding: utf-8 -*-

"""

===================================

stockshujurelatedmodel

===================================



zhize竊?
1. dingyistockshishixingqingmodel

2. dingyilishi K xianshujumodel

"""



from typing import Optional, List



from pydantic import BaseModel, Field





class StockQuote(BaseModel):

    """stockshishixingqing"""

    

    stock_code: str = Field(..., description="stockdaima")

    stock_name: Optional[str] = Field(None, description="stockmingcheng")

    current_price: float = Field(..., description="dangqianjiage")

    change: Optional[float] = Field(None, description="zhangdiee")

    change_percent: Optional[float] = Field(None, description="zhangdiefu (%)")

    open: Optional[float] = Field(None, description="kaipanjia")

    high: Optional[float] = Field(None, description="zuigaojia")

    low: Optional[float] = Field(None, description="zuidijia")

    prev_close: Optional[float] = Field(None, description="zuoshoujia")

    volume: Optional[float] = Field(None, description="chengjiaoliang竊늛u竊?")

    amount: Optional[float] = Field(None, description="chengjiaoe竊늶uan竊?")

    update_time: Optional[str] = Field(None, description="gengxinshijian")

    

    class Config:

        json_schema_extra = {

            "example": {

                "stock_code": "600519",

                "stock_name": "Samsung Electronics",

                "current_price": 1800.00,

                "change": 15.00,

                "change_percent": 0.84,

                "open": 1785.00,

                "high": 1810.00,

                "low": 1780.00,

                "prev_close": 1785.00,

                "volume": 10000000,

                "amount": 18000000000,

                "update_time": "2024-01-01T15:00:00"

            }

        }





class KLineData(BaseModel):

    """K xianshujudian"""

    

    date: str = Field(..., description="riqi")

    open: float = Field(..., description="kaipanjia")

    high: float = Field(..., description="zuigaojia")

    low: float = Field(..., description="zuidijia")

    close: float = Field(..., description="shoupanjia")

    volume: Optional[float] = Field(None, description="chengjiaoliang")

    amount: Optional[float] = Field(None, description="chengjiaoe")

    change_percent: Optional[float] = Field(None, description="zhangdiefu (%)")

    

    class Config:

        json_schema_extra = {

            "example": {

                "date": "2024-01-01",

                "open": 1785.00,

                "high": 1810.00,

                "low": 1780.00,

                "close": 1800.00,

                "volume": 10000000,

                "amount": 18000000000,

                "change_percent": 0.84

            }

        }





class ExtractItem(BaseModel):

    """Single extracted stock result."""



    code: Optional[str] = Field(None, description="stockdaima竊똍one biaoshijiexishibai")

    name: Optional[str] = Field(None, description="stockmingcheng竊늭uyou竊?")

    confidence: str = Field("medium", description="zhixindu竊쉎igh/medium/low")





class ExtractFromImageResponse(BaseModel):

    """tupianstockdaimatiquxiangying"""



    codes: List[str] = Field(..., description="tiqudestockdaima竊늶iquzhong竊똸ianghoujianrong竊?")

    items: List[ExtractItem] = Field(default_factory=list, description="tiqujieguomingxi竊늕aima+mingcheng+zhixindu竊?")

    raw_text: Optional[str] = Field(None, description="yuanshi LLM xiangying竊늯iaoshiyong竊?")





class StockHistoryResponse(BaseModel):

    """stocklishiquotexiangying"""

    

    stock_code: str = Field(..., description="stockdaima")

    stock_name: Optional[str] = Field(None, description="stockmingcheng")

    period: str = Field(..., description="K xianzhouqi")

    data: List[KLineData] = Field(default_factory=list, description="K xianshujuliebiao")

    

    class Config:

        json_schema_extra = {

            "example": {

                "stock_code": "600519",

                "stock_name": "Samsung Electronics",

                "period": "daily",

                "data": []

            }

        }


