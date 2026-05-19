# Discord Bot 설정

Discord는 Webhook 방식과 Bot API 방식을 사용할 수 있습니다.

## 1. Webhook 방식

알림만 필요하면 Webhook 방식이 가장 간단합니다.

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

## 2. Bot API 방식

명령 수신이 필요하면 Bot Token과 채널 ID를 설정합니다.

```env
DISCORD_BOT_TOKEN=your_bot_token
DISCORD_CHANNEL_ID=your_channel_id
DISCORD_BOT_STATUS=Daily Stock Analysis | /help
```

Interaction 검증을 사용하는 경우 Discord Developer Portal의 Public Key를 설정합니다.

```env
DISCORD_INTERACTIONS_PUBLIC_KEY=your_public_key
```

## 3. 주요 명령

- `/analyze <stock_code>`: 지정 종목 분석
- `/market_review`: 시장 요약
- `/help`: 도움말

## 4. 보안

- Bot Token을 공개하지 않습니다.
- 필요한 권한만 부여합니다.
- 채널 ID와 권한을 함께 확인합니다.
