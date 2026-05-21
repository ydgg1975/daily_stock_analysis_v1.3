# -*- coding: utf-8 -*-
"""
Batch analysis bot command.
"""

import logging
import threading
import uuid
from typing import List

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse

logger = logging.getLogger(__name__)


class BatchCommand(BotCommand):
    """Run analysis for the configured watchlist."""

    @property
    def name(self) -> str:
        return "batch"

    @property
    def aliases(self) -> List[str]:
        return ["b", "일괄", "전체"]

    @property
    def description(self) -> str:
        return "관심 종목을 일괄 분석합니다"

    @property
    def usage(self) -> str:
        return "/batch [개수]"

    @property
    def admin_only(self) -> bool:
        """Batch analysis can be restricted later if needed."""
        return False

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        """Execute the batch analysis command."""
        from src.config import get_config

        config = get_config()
        config.refresh_stock_list()

        stock_list = config.stock_list
        if not stock_list:
            return BotResponse.error_response("관심 종목 목록이 비어 있습니다. STOCK_LIST를 먼저 설정하세요.")

        limit = None
        if args:
            try:
                limit = int(args[0])
                if limit <= 0:
                    return BotResponse.error_response("개수는 1 이상이어야 합니다.")
            except ValueError:
                return BotResponse.error_response(f"유효하지 않은 개수입니다: {args[0]}")

        if limit:
            stock_list = stock_list[:limit]

        logger.info("[BatchCommand] %d개 종목 일괄 분석을 시작합니다", len(stock_list))

        thread = threading.Thread(
            target=self._run_batch_analysis,
            args=(stock_list, message),
            daemon=True,
        )
        thread.start()

        preview = ", ".join(stock_list[:5])
        suffix = "..." if len(stock_list) > 5 else ""
        return BotResponse.markdown_response(
            "✅ **일괄 분석 작업을 시작했습니다**\n\n"
            f"• 분석 개수: {len(stock_list)}개\n"
            f"• 종목 목록: {preview}{suffix}\n\n"
            "분석이 완료되면 요약 보고서를 자동으로 전송합니다."
        )

    def _run_batch_analysis(self, stock_list: List[str], message: BotMessage) -> None:
        """Run batch analysis in a background thread."""
        try:
            from src.config import get_config
            from main import StockAnalysisPipeline

            config = get_config()
            pipeline = StockAnalysisPipeline(
                config=config,
                source_message=message,
                query_id=uuid.uuid4().hex,
                query_source="bot",
            )

            results = pipeline.run(
                stock_codes=stock_list,
                dry_run=False,
                send_notification=True,
            )

            logger.info("[BatchCommand] 일괄 분석 완료: 성공 %d개", len(results))

        except Exception as e:
            logger.error("[BatchCommand] 일괄 분석 실패: %s", e)
            logger.exception(e)
