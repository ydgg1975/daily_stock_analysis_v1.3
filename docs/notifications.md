# 알림 설정

Daily Stock Analysis는 분석 보고서, 이벤트 알림, 시스템 오류를 여러 채널로 전송할 수 있습니다. 한 채널이 실패하더라도 전체 분석 작업이 중단되지 않도록 구성하는 것을 권장합니다.

## 지원 채널

| 채널 | 주요 설정 |
| --- | --- |
| 이메일 | `EMAIL_SENDER`, `EMAIL_PASSWORD`, `EMAIL_RECEIVERS` |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| Discord | `DISCORD_WEBHOOK_URL`, `DISCORD_BOT_TOKEN`, `DISCORD_MAIN_CHANNEL_ID` |
| Slack | `SLACK_WEBHOOK_URL`, `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID` |
| Feishu | `FEISHU_WEBHOOK_URL`, `FEISHU_WEBHOOK_SECRET`, `FEISHU_WEBHOOK_KEYWORD` |
| WeChat Work | `WECHAT_WEBHOOK_URL`, `WECHAT_MSG_TYPE` |
| ntfy | `NTFY_URL`, `NTFY_TOKEN` |
| Gotify | `GOTIFY_URL`, `GOTIFY_TOKEN` |
| 사용자 지정 Webhook | `CUSTOM_WEBHOOK_URLS`, `CUSTOM_WEBHOOK_BEARER_TOKEN`, `CUSTOM_WEBHOOK_BODY_TEMPLATE` |

## Telegram

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

BotFather에서 Bot Token을 만들고, 대상 채팅의 ID를 확인해 설정합니다. Topic을 사용하는 그룹이라면 `TELEGRAM_MESSAGE_THREAD_ID`도 설정할 수 있습니다.

## Discord

Webhook만 사용할 때:

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

Bot API와 Slash Command를 사용할 때:

```env
DISCORD_BOT_TOKEN=your-discord-bot-token
DISCORD_MAIN_CHANNEL_ID=your-channel-id
```

자세한 내용은 [Discord Bot 설정 가이드](bot/discord-bot-config.md)를 참고하세요.

## Slack

Webhook 방식:

```env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

Bot Token 방식:

```env
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL_ID=C...
```

Bot이 대상 채널에 초대되어 있고 메시지 전송 권한이 있는지 확인합니다.

## 이메일

```env
EMAIL_SENDER=example@example.com
EMAIL_PASSWORD=app_password
EMAIL_RECEIVERS=user1@example.com,user2@example.com
```

Gmail 같은 서비스는 일반 비밀번호 대신 앱 비밀번호가 필요할 수 있습니다.

## Feishu

```env
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your_hook_token
FEISHU_WEBHOOK_SECRET=your_sign_secret
FEISHU_WEBHOOK_KEYWORD=주식일보
```

키워드나 서명 검증을 켰다면 Feishu 콘솔의 값과 `.env` 값을 맞춰야 합니다. 자세한 내용은 [Feishu 알림 설정 가이드](bot/feishu-bot-config.md)를 참고하세요.

## 전송 라우팅

보고서, 이벤트 알림, 시스템 오류를 서로 다른 채널로 나눌 수 있습니다.

```env
NOTIFICATION_REPORT_CHANNELS=telegram,discord
NOTIFICATION_ALERT_CHANNELS=telegram
NOTIFICATION_SYSTEM_ERROR_CHANNELS=email
```

비워두면 기본 알림 채널 설정을 사용합니다.

## 중복과 소음 제어

반복 알림을 줄이려면 다음 값을 설정합니다.

```env
NOTIFICATION_DEDUP_TTL_SECONDS=300
NOTIFICATION_COOLDOWN_SECONDS=600
NOTIFICATION_QUIET_HOURS=23:00-07:00
NOTIFICATION_TIMEZONE=Asia/Seoul
NOTIFICATION_MIN_SEVERITY=warning
NOTIFICATION_DAILY_DIGEST_ENABLED=false
```

## 점검 항목

- 채널별 인증 정보가 올바른지 확인합니다.
- 대상 채팅, 채널, 이메일 주소가 정확한지 확인합니다.
- 메시지 길이 제한에 걸리지 않는지 확인합니다.
- Markdown 또는 카드 렌더링이 깨지지 않는지 확인합니다.
- 한 채널 실패가 전체 분석을 중단시키지 않는지 확인합니다.
- API Key와 Webhook URL을 코드나 공개 로그에 노출하지 않습니다.

## GitHub Actions 환경 변수 기준

<!-- notification-actions-env-table:start -->

| Key | Tier | Channel / feature | Actions source | Default |
| --- | --- | --- | --- | --- |
| `WECHAT_WEBHOOK_URL` | minimal | wechat | Secret | - |
| `WECHAT_MSG_TYPE` | advanced | wechat | Variable or Secret | `markdown` |
| `FEISHU_WEBHOOK_URL` | minimal | feishu | Secret | - |
| `FEISHU_WEBHOOK_SECRET` | advanced | feishu | Secret | - |
| `FEISHU_WEBHOOK_KEYWORD` | advanced | feishu | Variable or Secret | - |
| `TELEGRAM_BOT_TOKEN` | minimal | telegram | Secret | - |
| `TELEGRAM_CHAT_ID` | minimal | telegram | Secret | - |
| `TELEGRAM_MESSAGE_THREAD_ID` | advanced | telegram | Secret | - |
| `EMAIL_SENDER` | minimal | email | Variable or Secret | - |
| `EMAIL_PASSWORD` | minimal | email | Secret | - |
| `EMAIL_RECEIVERS` | advanced | email | Variable or Secret | - |
| `EMAIL_SENDER_NAME` | advanced | email | Variable or Secret | `Daily Stock Analysis Assistant` |
| `PUSHOVER_USER_KEY` | minimal | pushover | Secret | - |
| `PUSHOVER_API_TOKEN` | minimal | pushover | Secret | - |
| `NTFY_URL` | minimal | ntfy | Secret | - |
| `NTFY_TOKEN` | advanced | ntfy | Secret | - |
| `GOTIFY_URL` | minimal | gotify | Secret | - |
| `GOTIFY_TOKEN` | minimal | gotify | Secret | - |
| `PUSHPLUS_TOKEN` | minimal | pushplus | Secret | - |
| `PUSHPLUS_TOPIC` | advanced | pushplus | Variable or Secret | - |
| `CUSTOM_WEBHOOK_URLS` | minimal | custom | Secret | - |
| `CUSTOM_WEBHOOK_BEARER_TOKEN` | advanced | custom | Secret | - |
| `CUSTOM_WEBHOOK_BODY_TEMPLATE` | advanced | custom | Variable or Secret | - |
| `WEBHOOK_VERIFY_SSL` | advanced | ntfy, gotify, custom, astrbot | Variable or Secret | `true` |
| `DISCORD_WEBHOOK_URL` | minimal | discord | Secret | - |
| `DISCORD_BOT_TOKEN` | minimal | discord | Secret | - |
| `DISCORD_MAIN_CHANNEL_ID` | minimal | discord | Secret | - |
| `ASTRBOT_URL` | minimal | astrbot | Secret | - |
| `ASTRBOT_TOKEN` | advanced | astrbot | Secret | - |
| `SERVERCHAN3_SENDKEY` | minimal | serverchan3 | Secret | - |
| `SLACK_WEBHOOK_URL` | minimal | slack | Secret | - |
| `SLACK_BOT_TOKEN` | minimal | slack | Secret | - |
| `SLACK_CHANNEL_ID` | minimal | slack | Secret | - |
| `NOTIFICATION_REPORT_CHANNELS` | advanced | routing | Variable or Secret | - |
| `NOTIFICATION_ALERT_CHANNELS` | advanced | routing | Variable or Secret | - |
| `NOTIFICATION_SYSTEM_ERROR_CHANNELS` | advanced | routing | Variable or Secret | - |
| `NOTIFICATION_DEDUP_TTL_SECONDS` | advanced | noise | Variable or Secret | `0` |
| `NOTIFICATION_COOLDOWN_SECONDS` | advanced | noise | Variable or Secret | `0` |
| `NOTIFICATION_QUIET_HOURS` | advanced | noise | Variable or Secret | - |
| `NOTIFICATION_TIMEZONE` | advanced | noise | Variable or Secret | - |
| `NOTIFICATION_MIN_SEVERITY` | advanced | noise | Variable or Secret | - |
| `NOTIFICATION_DAILY_DIGEST_ENABLED` | advanced | noise | Variable or Secret | `false` |

<!-- notification-actions-env-table:end -->
