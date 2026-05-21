# -*- coding: utf-8 -*-
"""
Strategies / skills listing command.
"""

import logging
from typing import List

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse

logger = logging.getLogger(__name__)


class StrategiesCommand(BotCommand):
    """List available trading strategies."""

    @property
    def name(self) -> str:
        return "strategies"

    @property
    def aliases(self) -> List[str]:
        return ["skills", "전략", "전략목록"]

    @property
    def description(self) -> str:
        return "사용 가능한 거래 전략을 표시합니다"

    @property
    def usage(self) -> str:
        return "/strategies [active]"

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        """Execute the strategies list command."""
        show_active_only = bool(args and args[0].lower() in ("active", "활성", "활성화"))

        try:
            from src.agent.factory import DEFAULT_AGENT_SKILLS, get_skill_manager
            from src.config import get_config

            config = get_config()
            skill_manager = get_skill_manager(config)
            configured_active: set = set(config.agent_skills or DEFAULT_AGENT_SKILLS)

            all_skills = skill_manager.list_skills()
            if not all_skills:
                return BotResponse.text_response("📋 사용 가능한 전략이 없습니다. strategies/ 디렉터리를 확인하세요.")

            skills = all_skills
            if show_active_only:
                skills = [s for s in all_skills if s.name in configured_active]
                if not skills:
                    return BotResponse.text_response("📋 현재 활성화된 전략이 없습니다.")

            categories = {
                "trend": "📈 추세형",
                "pattern": "📊 패턴형",
                "reversal": "🔄 반전형",
                "framework": "🧩 프레임워크형",
            }
            grouped = {}
            for skill in skills:
                cat = skill.category or "trend"
                grouped.setdefault(cat, []).append(skill)

            lines = ["📋 **거래 전략 목록**", ""]
            ordered_keys = ["trend", "pattern", "reversal", "framework"]
            for cat_key in ordered_keys + [k for k in grouped if k not in ordered_keys]:
                cat_skills = grouped.get(cat_key)
                if not cat_skills:
                    continue
                cat_label = categories.get(cat_key, f"📌 {cat_key}")
                lines.append(f"**{cat_label}**")
                for skill in cat_skills:
                    status = "✅" if skill.name in configured_active else "⬜"
                    source_tag = " (사용자 정의)" if skill.source and skill.source != "builtin" else ""
                    lines.append(f"  {status} `{skill.name}` - {skill.display_name}{source_tag}")
                    lines.append(f"      {skill.description}")
                lines.append("")

            active_count = sum(1 for s in all_skills if s.name in configured_active)
            total_count = len(all_skills)
            lines.append(f"총 {total_count}개 전략, 활성화 {active_count}개")
            lines.append("\n💡 `/ask <종목코드> <전략명>` 형식으로 특정 전략 분석을 요청할 수 있습니다.")

            return BotResponse.markdown_response("\n".join(lines))

        except Exception as e:
            logger.error("Strategies command failed: %s", e)
            logger.exception("Strategies error details:")
            return BotResponse.text_response(f"⚠️ 전략 목록 조회 실패: {str(e)}")
