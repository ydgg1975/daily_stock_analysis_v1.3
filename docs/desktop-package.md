# 데스크톱 패키징

데스크톱 앱은 `apps/dsa-desktop`에서 관리하며, Web UI 빌드 결과를 함께 사용합니다.

## 1. 빌드 순서

```bash
cd apps/dsa-web
npm ci
npm run build

cd ../dsa-desktop
npm install
npm run build
```

## 2. 설정 파일

데스크톱 앱은 사용자 설정과 데이터 파일을 앱 실행 위치 또는 지정된 데이터 디렉터리에 저장합니다.

중요 파일:

- `.env`
- `data/`
- `logs/`

업데이트 전에는 `.env`를 백업하는 것을 권장합니다.

## 3. Windows 확인

Windows 패키지는 NSIS 설치 결과물, `latest.yml`, `*.blockmap` 파일을 함께 확인합니다.

검증 항목:

- 설치 가능 여부
- 실행 가능 여부
- 설정 파일 유지 여부
- 업데이트 후 기존 데이터 유지 여부
- Web UI 접근 가능 여부

## 4. macOS 주의

macOS에서는 `.app` 교체 과정에서 앱 내부 파일이 바뀔 수 있습니다. 업데이트 전 설정 백업을 먼저 내보내세요.

## 5. 문제 해결

- `logs/desktop.log` 확인
- `.env` 존재 여부 확인
- Web 빌드 결과 확인
- 백엔드 포트 충돌 확인
- 보안 프로그램이 실행 파일을 차단하지 않는지 확인
