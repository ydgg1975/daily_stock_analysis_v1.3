# -*- coding: utf-8 -*-
"""
Optimization Advisor - Analysis Feedback Loop
"""

import logging
from datetime import datetime
from typing import List, Optional

from src.analyzer import GeminiAnalyzer
from src.repositories.backtest_repo import BacktestRepository
from src.storage import AnalysisHistory, BacktestResult, get_db

logger = logging.getLogger(__name__)


class OptimizationAdvisor:
    """
    Analyzes failed backtests and generates optimization suggestions for the analysis logic.
    """

    def __init__(self):
        self.db = get_db()
        self.repo = BacktestRepository(self.db)
        self.analyzer = GeminiAnalyzer()

    def analyze_failures(self, limit: int = 5) -> str:
        """
        Fetches recent failed backtests and asks AI to analyze why.
        Returns a markdown report.
        """
        failures = self.repo.get_failed_results(limit=limit)
        if not failures:
            return "No recent failed backtests found (outcome='loss')."

        report = [
            "# 📉 Analysis Optimization Report",
            f"Generated at: {datetime.now()}",
            "",
            "## Summary",
            f"Found {len(failures)} recent failures (Loss outcome).",
            "",
        ]

        for fail in failures:
            # Fetch original analysis context
            history = self._get_history(fail.analysis_history_id)
            if not history:
                continue

            report.append(f"## Case: {fail.code} ({fail.analysis_date})")
            report.append(f"- **Prediction**: {fail.operation_advice} ({fail.direction_expected})")
            report.append(f"- **Actual**: {fail.outcome} (Return: {fail.stock_return_pct}%)")
            report.append(f"- **Reason**: {fail.simulated_exit_reason}")

            # Ask AI for post-mortem
            analysis = self._ask_ai_post_mortem(fail, history)
            report.append(f"\n### 🤖 AI Post-Mortem\n{analysis}\n")
            report.append("---\n")

        return "\n".join(report)

    def _get_history(self, history_id: int) -> Optional[AnalysisHistory]:
        with self.db.get_session() as session:
            return session.get(AnalysisHistory, history_id)

    def _ask_ai_post_mortem(self, fail: BacktestResult, history: AnalysisHistory) -> str:
        """
        Ask the LLM to analyze the failure.
        """
        if not self.analyzer.is_available():
            return "AI Analyzer not available."

        # Construct a prompt for the review
        prompt = f"""
        You are a senior stock analysis reviewer.
        
        **Objective**: Analyze why a previous prediction failed and suggest improvements.
        
        **Case Details**:
        - Stock: {fail.code}
        - Analysis Date: {fail.analysis_date}
        - Your Previous Advice: {fail.operation_advice}
        - Expected Direction: {fail.direction_expected}
        - Actual Return (10 days): {fail.stock_return_pct}%
        - Outcome: {fail.outcome.upper()} (Prediction Failed)
        
        **Original Analysis Summary**:
        {history.analysis_summary}
        
        **Original Key Points**:
        {history.trend_prediction}
        
        **Task**:
        1. **Root Cause Analysis**: Why was the prediction wrong? (e.g., ignored a bearish signal, market crash, unexpected news, technical breakdown).
        2. **Optimization Suggestion**: Propose ONE specific rule or check to add to the system prompt to avoid this mistake in the future.
        
        Keep it concise.
        """
        
        try:
            # Use the private _call_api_with_retry method or public analyze if we can trick it.
            # Since we are in the same package context, we can access the analyzer's methods.
            # We'll use a generation config similar to normal analysis.
            config = {"temperature": 0.5, "max_output_tokens": 1024}
            
            # Using _call_api_with_retry directly as it handles rotation and retries
            return self.analyzer._call_api_with_retry(prompt, config)
        except Exception as e:
            logger.error(f"Post-mortem analysis failed: {e}")
            return f"Error generating post-mortem: {e}"

if __name__ == "__main__":
    # Test run
    logging.basicConfig(level=logging.INFO)
    advisor = OptimizationAdvisor()
    print(advisor.analyze_failures(limit=3))
