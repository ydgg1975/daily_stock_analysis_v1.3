# -*- coding: utf-8 -*-

"""

===================================

bangzhumingling

===================================



xianshikeyongminglingliebiaoheshiyongshuoming??
"""



from typing import List



from bot.commands.base import BotCommand

from bot.models import BotMessage, BotResponse





class HelpCommand(BotCommand):

    """

    bangzhumingling

    

    xianshisuoyoukeyongminglingdeliebiaoheshiyongshuoming??
    yekeyiviewtedingminglingdexiangxibangzhu??
    

    yongfa竊?
        /help         - xianshisuoyoumingling

        /help analyze - xianshi analyze minglingdexiangxibangzhu

    """

    

    @property

    def name(self) -> str:

        return "help"

    

    @property

    def aliases(self) -> List[str]:

        return ["h", "bangzhu", "?"]

    

    @property

    def description(self) -> str:

        return "도움말을 표시합니다"

    

    @property

    def usage(self) -> str:

        return "/help [명령명]"

    

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:

        """zhixingbangzhumingling"""

        # yanchidaorubimianxunhuanyilai

        from bot.dispatcher import get_dispatcher

        

        dispatcher = get_dispatcher()

        

        # ruguozhidingleminglingming竊똸ianshigaiminglingdexiangxibangzhu

        if args:

            cmd_name = args[0]

            command = dispatcher.get_command(cmd_name)

            

            if command is None:

                return BotResponse.error_response(f"weizhimingling: {cmd_name}")

            

            # goujianxiangxibangzhu

            help_text = self._format_command_help(command, dispatcher.command_prefix)

            return BotResponse.markdown_response(help_text)

        

        # xianshisuoyouminglingliebiao

        commands = dispatcher.list_commands(include_hidden=False)

        prefix = dispatcher.command_prefix

        

        help_text = self._format_help_list(commands, prefix)

        return BotResponse.markdown_response(help_text)

    

    def _format_help_list(self, commands: List[BotCommand], prefix: str) -> str:

        """geshihuaminglingliebiao"""

        lines = [

            "**주식 분석 도우미 - 명령 도움말**",

            "",

            "사용 가능한 명령:",

            "",

        ]

        

        for cmd in commands:

            # minglingminghebieming

            aliases_str = ""

            if cmd.aliases:

                # guolvdiaozhongwenbieming竊똺hixianshiyingwenbieming

                en_aliases = [a for a in cmd.aliases if a.isascii()]

                if en_aliases:

                    aliases_str = f" ({', '.join(prefix + a for a in en_aliases[:2])})"

            

            lines.append(f"- `{prefix}{cmd.name}`{aliases_str} - {cmd.description}")

            lines.append("")



        lines.extend([

            "",

            "---",

            f"`{prefix}help <명령명>`을 입력하면 자세한 사용법을 볼 수 있습니다.",

            "",

            "**예시**",

            "",

            f"- `{prefix}analyze 301023` - 종목 분석",

            "",

            f"- `{prefix}market` - 시장 리뷰 확인",

            "",

            f"- `{prefix}batch` - 관심 종목 일괄 분석",

        ])

        

        return "\n".join(lines)

    

    def _format_command_help(self, command: BotCommand, prefix: str) -> str:

        """geshihuadangeminglingdexiangxibangzhu"""

        lines = [

            f"**{prefix}{command.name}** - {command.description}",

            "",

            f"**사용법** `{command.usage}`",

            "",

        ]

        

        # bieming

        if command.aliases:

            aliases = [f"`{prefix}{a}`" if a.isascii() else f"`{a}`" for a in command.aliases]

            lines.append(f"**별칭** {', '.join(aliases)}")

            lines.append("")

        

        # quanxian

        if command.admin_only:

            lines.append("**관리자 권한이 필요합니다.**")

            lines.append("")

        

        return "\n".join(lines)


