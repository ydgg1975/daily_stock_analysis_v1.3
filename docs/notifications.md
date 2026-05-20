# 알림 설정

분석 결과는 여러 채널로 전송할 수 있습니다. 한 채널이 실패하더라도 전체 분석 작업은 계속 진행되는 구조를 권장합니다.

## 지원 채널

| 채널 | 주요 설정 |
| --- | --- |
| 이메일 | `EMAIL_SENDER`, `EMAIL_PASSWORD`, `EMAIL_RECEIVERS` |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| Discord | `DISCORD_WEBHOOK_URL` |
| Slack | `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID` |
| Webhook | 채널별 Webhook URL |

## Telegram

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

BotFather에서 Bot Token을 만들고, 수신할 채팅 ID를 확인한 뒤 설정합니다.

## Discord

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

채널 설정에서 Webhook을 생성한 뒤 URL을 등록합니다.

## Slack

```env
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL_ID=C...
```

Bot 권한과 채널 초대 상태를 함께 확인하세요.

## 이메일

```env
EMAIL_SENDER=example@example.com
EMAIL_PASSWORD=app_password
EMAIL_RECEIVERS=user1@example.com,user2@example.com
```

Gmail 같은 서비스는 일반 비밀번호 대신 앱 비밀번호가 필요할 수 있습니다.

## 점검 방법

알림 설정 후 다음을 확인합니다.

- 채널별 인증 정보가 맞는지
- 수신 대상 ID가 올바른지
- 메시지 길이 제한에 걸리지 않는지
- Markdown 렌더링이 깨지지 않는지
- 실패한 채널이 전체 분석을 중단시키지 않는지

## 운영 원칙

- 알림 문구는 한국어를 기본으로 유지합니다.
- 깨진 문자나 중국어 원문이 알림에 포함되지 않아야 합니다.
- 민감한 API 키와 Webhook URL은 코드에 직접 쓰지 않습니다.

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
