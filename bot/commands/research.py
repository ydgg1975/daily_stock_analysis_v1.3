# -*- coding: utf-8 -*-
"""
Deep research bot command for a stock or market topic.
"""

import logging
import re
import time
from typing import List, Optional

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse
from src.config import get_config

logger = logging.getLogger(__name__)

_RESEARCH_STOCK_CODE_RE = re.compile(
    r"^\d{6}$|^HK\d{5}$|^[A-Z]{1,5}(?:\.[A-Z]{1,2})?$"
)


class ResearchCommand(BotCommand):
    """Invoke the deep research agent."""

    @property
    def name(self) -> str:
        return "research"

    @property
    def aliases(self) -> List[str]:
        return ["심층", "deepsearch"]

    @property
    def description(self) -> str:
        return "종목 또는 시장 주제에 대한 심층 조사를 실행합니다"

    @property
    def usage(self) -> str:
        return "/research <종목코드|주제> [구체적인 질문]"

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        if not args:
            return BotResponse.text_response(
                f"사용법: {self.usage}\n"
                "예시: /research AAPL 최근 실적 리스크\n"
                "예시: /research 반도체 업종 전망"
            )

        config = get_config()
        if not config.agent_mode:
            return BotResponse.text_response(
                "⚠️ Agent 모드가 꺼져 있어 심층 조사 기능을 사용할 수 없습니다.\n"
                "설정에서 `AGENT_MODE=true`를 지정하세요."
            )

        query_parts = list(args)
        stock_code: Optional[str] = None

        first = query_parts[0].upper().replace("，", ",")
        if _RESEARCH_STOCK_CODE_RE.match(first):
            stock_code = first
            query_parts = query_parts[1:]

        if query_parts:
            question = " ".join(query_parts)
        elif stock_code:
            question = f"Comprehensive deep research on stock {stock_code}: fundamentals, technicals, news sentiment, and risk factors"
        else:
            question = " ".join(args)

        if stock_code:
            question = f"[Stock: {stock_code}] {question}"

        try:
            from src.agent.factory import get_tool_registry
            from src.agent.llm_adapter import LLMToolAdapter
            from src.agent.research import ResearchAgent

            registry = get_tool_registry()
            llm_adapter = LLMToolAdapter(config)
            budget = getattr(config, "agent_deep_research_budget", 30000)

            agent = ResearchAgent(
                tool_registry=registry,
                llm_adapter=llm_adapter,
                token_budget=budget,
            )

            research_timeout = getattr(config, "agent_deep_research_timeout", 180)
            logger.info("[ResearchCommand] Starting deep research (timeout=%ds): %s", research_timeout, question[:100])
            started_at = time.time()
            result = agent.research(
                question,
                {"stock_code": stock_code, "stock_name": ""} if stock_code else None,
                timeout_seconds=research_timeout,
            )
            duration = result.duration_s or round(time.time() - started_at, 1)

            if getattr(result, "timed_out", False):
                logger.warning("[ResearchCommand] Deep research timed out after %ss", duration)
                return BotResponse.text_response(
                    f"⏳ 심층 조사 시간이 초과되었습니다({duration}s / {research_timeout}s). "
                    "잠시 후 다시 시도하거나 조사 범위를 줄여 주세요."
                )

            if result.success:
                header = "🔎 **Deep Research Report / 심층 조사 보고서**\n"
                if stock_code:
                    header += f"종목: {stock_code}\n"
                header += f"하위 질문: {len(result.sub_questions)}개 | 출처: {result.findings_count}개\n"
                header += f"소요 시간: {duration}s | 토큰: {result.total_tokens:,}\n"
                header += "-" * 40 + "\n\n"

                report = header + result.report
                max_len = 4000
                if len(report) > max_len:
                    report = report[:max_len] + "\n\n... (보고서가 길어 일부만 표시했습니다. 전체 보고서는 API에서 확인하세요.)"

                return BotResponse.markdown_response(report)

            return BotResponse.text_response(
                "⚠️ 심층 조사가 정상 완료되지 않았습니다.\n"
                f"수집된 결과: {result.findings_count}개\n"
                f"소요 시간: {duration}s"
            )

        except Exception as exc:
            logger.error("[ResearchCommand] Error: %s", exc, exc_info=True)
            return BotResponse.text_response(f"⚠️ 심층 조사 실패: {exc}")
