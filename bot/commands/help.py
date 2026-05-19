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

        return "xianshibangzhuxinxi"

    

    @property

    def usage(self) -> str:

        return "/help [minglingming]"

    

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

            "?뱴 **stockanalysiszhushou - minglingbangzhu**",

            "",

            "keyongmingling竊?",

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

            

            lines.append(f"??{prefix}{cmd.name}{aliases_str} - {cmd.description}")

            lines.append("")



        lines.extend([

            "",

            "---",

            f"?뮕 shuru {prefix}help <minglingming> viewxiangxiyongfa",

            "",

            "**shili竊?*",

            "",

            f"??{prefix}analyze 301023 - yifanchuandong",

            "",

            f"??{prefix}market - viewdapanfupan",

            "",

            f"??{prefix}batch - pilianganalysiswatchlistgu",

        ])

        

        return "\n".join(lines)

    

    def _format_command_help(self, command: BotCommand, prefix: str) -> str:

        """geshihuadangeminglingdexiangxibangzhu"""

        lines = [

            f"?뱰 **{prefix}{command.name}** - {command.description}",

            "",

            f"**yongfa竊?* `{command.usage}`",

            "",

        ]

        

        # bieming

        if command.aliases:

            aliases = [f"`{prefix}{a}`" if a.isascii() else f"`{a}`" for a in command.aliases]

            lines.append(f"**bieming竊?* {', '.join(aliases)}")

            lines.append("")

        

        # quanxian

        if command.admin_only:

            lines.append("?좑툘 **xuyaoguanliyuanquanxian**")

            lines.append("")

        

        return "\n".join(lines)


