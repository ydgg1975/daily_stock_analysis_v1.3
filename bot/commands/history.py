# -*- coding: utf-8 -*-

"""

History command ??view recent Agent conversation sessions.



**User isolation**: each user can only see sessions whose ``session_id``

starts with their own ``{platform}_{user_id}`` prefix.

"""



import logging

from typing import List, Optional



from bot.commands.base import BotCommand

from bot.models import BotMessage, BotResponse, ChatType



logger = logging.getLogger(__name__)





def _user_prefix(message: BotMessage) -> str:

    """Canonical session-id prefix for a given user.



    Session IDs follow the pattern ``{platform}_{user_id}:{scope}``.

    The colon delimiter prevents prefix-collision between user IDs

    (e.g. user '123' vs '1234').

    """

    return f"{message.platform}_{message.user_id}:"





def _legacy_chat_session_id(message: BotMessage) -> str:

    """Legacy chat session id used before the colon-scoped format."""

    return f"{message.platform}_{message.user_id}"





def _current_chat_session_id(message: BotMessage) -> str:

    """Current chat session id for the active conversation scope."""

    prefix = _user_prefix(message)

    if message.chat_type == ChatType.GROUP and message.chat_id:

        return f"{prefix}{message.chat_id}:chat"

    return f"{prefix}chat"





class HistoryCommand(BotCommand):

    """

    View recent agent conversation history (scoped to current user).



    Usage:

        /history          - List your recent sessions

        /history <id>     - View messages in one of your sessions

        /history clear    - Clear your current session

    """



    @property

    def name(self) -> str:

        return "history"



    @property

    def aliases(self) -> List[str]:

        return ["lishi", "huihua"]



    @property

    def description(self) -> str:

        return "Agent 대화 기록을 조회합니다"



    @property

    def usage(self) -> str:

        return "/history [session_id | clear]"



    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:

        """Execute the history command."""

        try:

            from src.storage import get_db

            db = get_db()

        except Exception as e:

            logger.error(f"History: storage unavailable: {e}")

            return BotResponse.text_response("Storage is unavailable. Conversation history cannot be queried.")



        prefix = _user_prefix(message)

        legacy_chat_session_id = _legacy_chat_session_id(message)

        current_chat_session_id = _current_chat_session_id(message)



        # /history clear ??clear current user's chat session

        if args and args[0].lower() in ("clear", "qingchu"):

            try:

                deleted = db.delete_conversation_session(current_chat_session_id)

                if current_chat_session_id == f"{prefix}chat":

                    deleted += db.delete_conversation_session(legacy_chat_session_id)

                return BotResponse.text_response(

                    f"현재 대화를 삭제했습니다. 삭제된 메시지: {deleted}개"

                )

            except Exception as e:

                logger.error(f"History clear failed: {e}")

                return BotResponse.text_response(f"대화 삭제에 실패했습니다: {str(e)}")



        # /history <session_id> ??show messages for a specific session

        # Only allow access if the session belongs to the requesting user.

        if args and not args[0].isdigit():

            session_id = args[0]

            if not (session_id.startswith(prefix) or session_id == legacy_chat_session_id):

                return BotResponse.text_response("본인의 대화 기록만 볼 수 있습니다.")

            try:

                messages_list = db.get_conversation_messages(session_id, limit=20)

                if not messages_list:

                    return BotResponse.text_response(f"대화 `{session_id}`에 메시지 기록이 없습니다.")



                lines = [f"**대화 상세**: `{session_id}`", ""]

                for msg in messages_list:

                    role_icon = "?뫀" if msg["role"] == "user" else "?쨼"

                    content_preview = msg["content"][:200]

                    if len(msg["content"]) > 200:

                        content_preview += "..."

                    time_str = msg.get("created_at", "")[:16] if msg.get("created_at") else ""

                    lines.append(f"{role_icon} {time_str}")

                    lines.append(f"  {content_preview}")

                    lines.append("")



                return BotResponse.markdown_response("\n".join(lines))

            except Exception as e:

                logger.error(f"History detail failed: {e}")

                return BotResponse.text_response(f"대화 상세 조회에 실패했습니다: {str(e)}")



        # /history [count] ??list recent sessions for this user only

        limit = 10

        if args and args[0].isdigit():

            limit = min(int(args[0]), 50)



        try:

            sessions = db.get_chat_sessions(

                limit=limit,

                session_prefix=prefix,

                extra_session_ids=[legacy_chat_session_id],

            )

            if not sessions:

                return BotResponse.text_response("대화 기록이 없습니다.")



            lines = ["**최근 대화 기록**", ""]

            for i, sess in enumerate(sessions, 1):

                title = sess.get("title", "새 대화")

                msg_count = sess.get("message_count", 0)

                last_active = sess.get("last_active", "")[:16] if sess.get("last_active") else ""

                sid = sess["session_id"]

                lines.append(f"**{i}.** {title}")

                lines.append(f"   메시지 {msg_count}개 | {last_active}")

                lines.append(f"   ID: `{sid}`")

                lines.append("")



            lines.append("`/history <session_id>`로 특정 대화 내용을 볼 수 있습니다.")

            return BotResponse.markdown_response("\n".join(lines))



        except Exception as e:

            logger.error(f"History list failed: {e}")

            return BotResponse.text_response(f"대화 목록 조회에 실패했습니다: {str(e)}")


