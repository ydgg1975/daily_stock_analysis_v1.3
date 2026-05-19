# DingTalk Bot 설정

DingTalk 알림 또는 Bot 연동을 위한 기본 안내입니다.

## 1. 앱 생성

DingTalk 개발자 콘솔에서 내부 앱을 만들고 Bot 기능을 활성화합니다.

참고: https://open.dingtalk.com/document/dingstart/create-application

## 2. 환경 변수

필요한 값을 `.env` 또는 배포 환경 변수에 설정합니다.

```env
DINGTALK_CLIENT_ID=your_client_id
DINGTALK_CLIENT_SECRET=your_client_secret
```

Webhook 방식을 사용하는 경우 Webhook URL과 보안 설정을 함께 확인하세요.

## 3. 테스트

설정 후 테스트 메시지를 보내 Bot이 정상 응답하는지 확인합니다.

확인 항목:

- 앱 권한
- Webhook 보안 설정
- 네트워크 접근 가능 여부
- 로그 오류 메시지
