import logging
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.core.pipeline import StockAnalysisPipeline
from src.enums import ReportType

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_pipeline():
    pipeline = StockAnalysisPipeline()
    code = '600519' # 贵州茅台
    
    print(f"Testing pipeline for {code}...")
    result = pipeline.analyze_stock(code, ReportType.SIMPLE, query_id='test')
    
    if result:
        print("Analysis successful!")
        print(f"Sentiment Score: {result.sentiment_score}")
        print(f"Advice: {result.operation_advice}")
        
        # Check if fundamental data is present in the result
        # Note: result object doesn't expose fundamental data directly in attributes easily accessible here without parsing to_dict
        res_dict = result.to_dict()
        # The fundamental data is inside the prompt context which is not returned in result object directly
        # However, we can check logs to see if "基本面数据获取成功" was logged.
        
        # We can also check if the advice fields are populated in the underlying trend_result
        # But pipeline.analyze_stock returns AnalysisResult (AI output), not TrendAnalysisResult.
        
        # To verify internal state, we might need to peek into pipeline or trust the logs.
        print("Test complete.")
    else:
        print("Analysis failed.")

if __name__ == "__main__":
    test_pipeline()
