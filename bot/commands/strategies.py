# -*- coding: utf-8 -*-

"""

Strategies / Skills listing command.



Shows all available trading strategies and their activation status.

"""



import logging

from typing import List



from bot.commands.base import BotCommand

from bot.models import BotMessage, BotResponse



logger = logging.getLogger(__name__)





class StrategiesCommand(BotCommand):

    """

    List available trading strategies.



    Usage:

        /strategies         - List all strategies

        /strategies active  - Show only active strategies

    """



    @property

    def name(self) -> str:

        return "strategies"



    @property

    def aliases(self) -> List[str]:

        return ["skills", "celve", "celveliebiao"]



    @property

    def description(self) -> str:

        return "사용 가능한 거래 전략을 표시합니다"



    @property

    def usage(self) -> str:

        return "/strategies [active]"



    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:

        """Execute the strategies list command."""

        show_active_only = bool(args and args[0].lower() in ("active", "jihuo", "yijihuo"))



        try:

            from src.agent.factory import get_skill_manager

            from src.config import get_config



            config = get_config()

            sm = get_skill_manager(config)

            from src.agent.factory import DEFAULT_AGENT_SKILLS



            # Derive activation status from config without mutating the skill

            # manager ??this is a read-only listing command.

            configured_active: set = set(config.agent_skills or DEFAULT_AGENT_SKILLS)



            all_skills = sm.list_skills()

            if not all_skills:

                return BotResponse.text_response("No strategies are available. Please check the strategies directory.")



            skills = all_skills

            if show_active_only:

                skills = [s for s in all_skills if s.name in configured_active]

                if not skills:

                    return BotResponse.text_response("현재 활성화된 전략이 없습니다.")



            # Group by category

            categories = {"trend": "?뱢 qushilei", "pattern": "?뱤 xingtailei", "reversal": "?봽 fanzhuanlei", "framework": "?㎥ kuangjialei"}

            grouped = {}

            for skill in skills:

                cat = skill.category or "trend"

                grouped.setdefault(cat, []).append(skill)



            lines = ["**거래 전략 목록**", ""]



            ordered_keys = ["trend", "pattern", "reversal", "framework"]

            for cat_key in ordered_keys + [k for k in grouped if k not in ordered_keys]:

                cat_skills = grouped.get(cat_key)

                if not cat_skills:

                    continue

                cat_label = categories.get(cat_key, cat_key)

                lines.append(f"**{cat_label}**")

                for s in cat_skills:

                    status = "ON" if s.name in configured_active else "OFF"

                    source_tag = ""

                    if s.source and s.source != "builtin":

                        source_tag = " (사용자 정의)"

                    lines.append(f"  {status} `{s.name}` - {s.display_name}{source_tag}")

                    lines.append(f"      {s.description}")

                lines.append("")



            active_count = sum(1 for s in all_skills if s.name in configured_active)

            total_count = len(all_skills)

            lines.append(f"총 {total_count}개 전략, 활성화 {active_count}개")

            lines.append("\n`/ask <종목코드> <전략명>`으로 특정 전략 분석을 요청할 수 있습니다.")



            return BotResponse.markdown_response("\n".join(lines))



        except Exception as e:

            logger.error(f"Strategies command failed: {e}")

            logger.exception("Strategies error details:")

            return BotResponse.text_response(f"전략 목록 조회에 실패했습니다: {str(e)}")


