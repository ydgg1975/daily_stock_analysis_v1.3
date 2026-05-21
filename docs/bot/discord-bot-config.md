# Discord Bot 설정 가이드

이 문서는 Discord로 분석 알림을 보내거나 Slash Command로 분석을 실행하기 위한 설정 방법을 설명합니다.

Discord 연동은 두 가지 방식으로 사용할 수 있습니다.

1. Webhook 모드: 설정이 간단하며, 분석 결과를 특정 채널로 보내는 데 적합합니다.
2. Bot API 모드: Slash Command와 메시지 수신 등 상호작용 기능이 필요할 때 사용합니다.

## Discord 애플리케이션 만들기

### 1. Developer Portal 접속

[Discord Developer Portal](https://discord.com/developers/applications)에 Discord 계정으로 로그인합니다.

### 2. 애플리케이션 생성

`New Application`을 누르고 애플리케이션 이름을 입력한 뒤 `Create`를 선택합니다.

### 3. Bot 추가

왼쪽 메뉴에서 `Bot`을 선택하고 `Add Bot`을 누릅니다.

### 4. Bot Token 발급

Bot 화면에서 `Reset Token` 또는 `View Token`을 통해 Token을 확인합니다. 이 값이 `DISCORD_BOT_TOKEN`입니다.

> Bot Token은 비밀값입니다. 저장소, 이슈, 로그에 노출하지 마세요.

### 5. 권한 설정

Slash Command와 메시지 처리를 사용하려면 Bot 화면의 `Privileged Gateway Intents`에서 필요한 항목을 켭니다.

- Presence Intent
- Server Members Intent
- Message Content Intent

Webhook 전송만 사용할 경우 이 항목이 필요하지 않을 수 있습니다.

### 6. 서버에 Bot 추가

1. 왼쪽 메뉴에서 `OAuth2 -> URL Generator`를 엽니다.
2. `Scopes`에서 다음 항목을 선택합니다.
   - `bot`
   - `applications.commands`
3. `Bot Permissions`에서 필요한 권한을 선택합니다.
   - Send Messages
   - Embed Links
   - Attach Files
   - Read Message History
   - Use Slash Commands
4. 생성된 URL을 브라우저에서 열고 Bot을 추가할 서버를 선택합니다.

### 7. 채널 ID 확인

1. Discord 클라이언트에서 개발자 모드를 켭니다.
   - 사용자 설정 -> 고급 -> 개발자 모드
2. 메시지를 보낼 채널을 오른쪽 클릭하고 `Copy ID`를 선택합니다.
3. 복사한 값이 `DISCORD_MAIN_CHANNEL_ID`입니다.

## 환경 변수

`.env` 파일에 필요한 값을 추가합니다.

```env
# Discord Bot API 모드
DISCORD_BOT_TOKEN=your-discord-bot-token
DISCORD_MAIN_CHANNEL_ID=your-channel-id

# Webhook 모드
DISCORD_WEBHOOK_URL=your-webhook-url

# Discord Interaction/Webhook 입장 콜백 검증용
DISCORD_INTERACTIONS_PUBLIC_KEY=your-public-key

# Bot 상태 메시지
DISCORD_BOT_STATUS=Daily Stock Analysis | /help
```

Discord Interaction 또는 Webhook 입장 콜백을 받는 경우, Developer Portal의 `General Information -> Public Key` 값을 `DISCORD_INTERACTIONS_PUBLIC_KEY`에 설정해야 합니다. 서버는 이 공개키로 Ed25519 서명을 검증하며, 검증에 실패한 요청은 거부합니다.

## Webhook 모드

분석 결과를 채널로 보내기만 한다면 Webhook 모드가 가장 간단합니다.

1. Discord에서 대상 채널을 오른쪽 클릭합니다.
2. `채널 편집 -> 연동 -> Webhooks`로 이동합니다.
3. 새 Webhook을 만들고 이름과 아이콘을 설정합니다.
4. Webhook URL을 복사해 `DISCORD_WEBHOOK_URL`에 넣습니다.

Webhook 모드만 사용할 때는 `DISCORD_BOT_TOKEN` 없이도 전송할 수 있습니다.

## 지원 명령

Bot API 모드는 다음 Slash Command를 지원합니다.

| 명령 | 설명 |
| --- | --- |
| `/analyze <stock_code> [full_report]` | 지정한 종목을 분석합니다. |
| `/market_review` | 시장 리뷰 보고서를 생성합니다. |
| `/help` | 사용 가능한 명령을 표시합니다. |

예시:

```text
/analyze AAPL
/analyze 600519 true
/market_review
```

## 테스트

1. Bot이 대상 서버에 추가되어 있는지 확인합니다.
2. 대상 채널에서 `/help`를 실행합니다.
3. `/analyze AAPL` 또는 `/analyze 600519`로 단일 종목 분석을 테스트합니다.
4. `/market_review`로 시장 리뷰 명령을 테스트합니다.

Webhook 모드는 앱의 알림 테스트 기능 또는 분석 완료 알림으로 확인할 수 있습니다.

## 문제 해결

### Bot이 명령에 반응하지 않습니다.

- `DISCORD_BOT_TOKEN`이 올바른지 확인합니다.
- Bot이 서버와 채널에 추가되어 있는지 확인합니다.
- Slash Command 권한과 `applications.commands` scope가 설정되어 있는지 확인합니다.

### 메시지를 보낼 수 없습니다.

- `DISCORD_MAIN_CHANNEL_ID`가 올바른지 확인합니다.
- Bot에 Send Messages, Embed Links, Attach Files 권한이 있는지 확인합니다.
- 채널별 권한에서 Bot 발언이 막혀 있지 않은지 확인합니다.

### Webhook 전송이 실패합니다.

- `DISCORD_WEBHOOK_URL`이 완전한 URL인지 확인합니다.
- Webhook이 삭제되었거나 다른 채널로 이동되지 않았는지 확인합니다.
- Discord API 제한이나 네트워크 오류가 있는지 로그를 확인합니다.

## 참고 링크

- [Discord Developer Portal](https://discord.com/developers/applications)
- [Discord Application Commands](https://discord.com/developers/docs/interactions/application-commands)
- [Discord Webhooks](https://discord.com/developers/docs/resources/webhook)
