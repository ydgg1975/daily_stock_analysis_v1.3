# -*- coding: utf-8 -*-
"""
Single-stock analysis bot command.
"""

import logging
import re
from typing import List, Optional

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse
from data_provider.base import canonical_stock_code

logger = logging.getLogger(__name__)


class AnalyzeCommand(BotCommand):
    """Submit an analysis task for one stock."""

    @property
    def name(self) -> str:
        return "analyze"

    @property
    def aliases(self) -> List[str]:
        return ["a", "분석", "조회"]

    @property
    def description(self) -> str:
        return "지정한 종목을 분석합니다"

    @property
    def usage(self) -> str:
        return "/analyze <종목코드> [full]"

    def validate_args(self, args: List[str]) -> Optional[str]:
        """Validate command arguments."""
        if not args:
            return "종목 코드를 입력하세요."

        code = args[0].upper()
        is_a_stock = re.match(r"^\d{6}$", code)
        is_hk_stock = re.match(r"^HK\d{5}$", code)
        is_us_stock = re.match(r"^[A-Z]{1,5}(\.[A-Z]{1,2})?$", code)

        if not (is_a_stock or is_hk_stock or is_us_stock):
            return f"유효하지 않은 종목 코드입니다: {code} (A주 6자리 숫자 / 홍콩 HK+5자리 / 미국 1-5자리 영문)"

        return None

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        """Execute the analysis command."""
        code = canonical_stock_code(args[0])

        report_type = "simple"
        if len(args) > 1 and args[1].lower() in ["full", "전체", "상세"]:
            report_type = "full"
        logger.info("[AnalyzeCommand] 분석 요청: code=%s, report_type=%s", code, report_type)

        try:
            from src.enums import ReportType
            from src.services.task_service import get_task_service

            service = get_task_service()
            report_type_enum = ReportType.from_str(report_type)
            result = service.submit_analysis(
                code=code,
                report_type=report_type_enum,
                source_message=message,
            )

            if result.get("success"):
                task_id = result.get("task_id", "")
                return BotResponse.markdown_response(
                    "✅ **분석 작업이 제출되었습니다**\n\n"
                    f"• 종목 코드: `{code}`\n"
                    f"• 보고서 유형: {report_type_enum.display_name}\n"
                    f"• 작업 ID: `{task_id[:20]}...`\n\n"
                    "분석이 완료되면 결과를 자동으로 전송합니다."
                )

            error = result.get("error", "알 수 없는 오류")
            return BotResponse.error_response(f"분석 작업 제출 실패: {error}")

        except Exception as e:
            logger.error("[AnalyzeCommand] 실행 실패: %s", e)
            return BotResponse.error_response(f"분석 실패: {str(e)[:100]}")
