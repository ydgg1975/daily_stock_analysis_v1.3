# Feishu 알림 설정

Feishu는 Webhook 방식과 앱/Bot 방식을 사용할 수 있습니다.

## 1. Webhook 방식

분석 결과를 Feishu 그룹으로 보내는 가장 간단한 방식입니다.

```env
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/...
FEISHU_WEBHOOK_SECRET=your_secret
FEISHU_WEBHOOK_KEYWORD=stock-report
```

그룹 Bot 보안 설정에서 키워드, 서명, IP 제한을 켰다면 프로젝트 설정에도 같은 값을 입력해야 합니다.

## 2. 앱/Bot 방식

양방향 Bot, 문서 연동, 고급 자동화가 필요하면 Feishu 앱 방식을 사용합니다.

필요 값:

- App ID
- App Secret
- Bot 권한
- 이벤트 구독 설정

## 3. 점검 순서

1. `FEISHU_WEBHOOK_URL`이 설정되어 있는지 확인합니다.
2. 보안 키워드 또는 서명이 일치하는지 확인합니다.
3. 그룹에 Bot이 추가되어 있는지 확인합니다.
4. 로그에서 Feishu 응답 코드를 확인합니다.

## 4. 최소 권장 설정

알림만 필요하다면 Webhook URL만 먼저 연결하고, 필요한 경우 Secret 또는 Keyword를 추가하세요.
