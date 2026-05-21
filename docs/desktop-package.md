# 데스크톱 앱 패키징 가이드

이 문서는 Electron 데스크톱 앱과 React Web UI를 함께 빌드하고 배포하는 흐름을 정리합니다. 데스크톱 앱은 `apps/dsa-web`에서 빌드한 정적 UI와 로컬 FastAPI 백엔드를 Electron 셸로 감싸는 구조입니다.

## 구조

- React UI는 Vite로 빌드되어 루트 `static/` 디렉터리에 배치됩니다.
- Electron 앱은 백엔드 실행 파일을 시작한 뒤 `/api/health` 응답을 기다리고 UI를 표시합니다.
- 데스크톱 실행 환경에서는 `.env`, SQLite DB, 로그 파일을 실행 파일 주변 경로에 두는 portable 모드를 지원합니다.
- 설치형 Windows 빌드는 per-user 설치를 기본으로 하며, 보호된 시스템 디렉터리 설치는 피하는 것을 권장합니다.

## 로컬 개발

가장 간단한 실행 방법은 PowerShell 스크립트를 사용하는 것입니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-desktop.ps1
```

수동으로 실행하려면 Web UI를 먼저 빌드한 뒤 Electron 개발 서버를 시작합니다.

```bash
cd apps/dsa-web
npm install
npm run build
```

```bash
cd apps/dsa-desktop
npm install
npm run dev
```

첫 실행 전에는 루트 `.env.example`을 참고해 `.env`를 준비합니다. LLM API 키가 없으면 일부 분석 기능은 제한될 수 있지만, 기본 UI와 설정 화면은 확인할 수 있습니다.

## Windows 패키징

### 사전 요구 사항

- Node.js 18 이상
- Python 3.10 이상
- Windows 개발자 모드 또는 electron-builder 실행에 필요한 권한
- Python 의존성 설치가 가능한 네트워크 환경

### 전체 빌드

루트에서 다음 명령을 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-all.ps1
```

스크립트는 다음 순서로 실행됩니다.

1. React UI 빌드
2. Python 의존성 설치
3. PyInstaller로 백엔드 실행 파일 생성
4. electron-builder로 데스크톱 설치 파일 생성

Windows NSIS 설치 파일은 사용자별 설치를 기본으로 합니다. 설치 후 `.env`, `data/stock_analysis.db`, `data/stock_analysis.db-wal`, `data/stock_analysis.db-shm`, `logs/desktop.log`는 설치 경로 또는 portable 실행 경로에 생성될 수 있습니다.

## GitHub Release 패키징

데스크톱 릴리스는 `.github/workflows/desktop-release.yml`에서 관리합니다.

트리거 방식은 다음 두 가지입니다.

- `v3.2.12` 같은 semantic tag 푸시
- GitHub Actions 수동 실행 시 `release_tag` 입력

주요 산출물은 다음과 같습니다.

| 플랫폼 | 산출물 |
| --- | --- |
| Windows 설치형 | `daily-stock-analysis-windows-installer-<tag>.exe` |
| Windows 자동 업데이트 메타데이터 | `latest.yml`, `*.blockmap` |
| Windows 무설치 | `daily-stock-analysis-windows-noinstall-<tag>.zip` |
| macOS Intel | `daily-stock-analysis-macos-x64-<tag>.dmg` |
| macOS Apple Silicon | `daily-stock-analysis-macos-arm64-<tag>.dmg` |

권장 릴리스 흐름은 다음과 같습니다.

1. 변경 사항을 `main`에 병합합니다.
2. semantic tag를 생성하고 푸시합니다.
3. `desktop-release` 워크플로가 GitHub Release에 산출물을 첨부하는지 확인합니다.

## 릴리스 전 검증

Web UI 변경이 포함된 경우 다음을 실행합니다.

```bash
cd apps/dsa-web
npm ci
npm run lint
npm run build
```

데스크톱 변경이 포함된 경우 다음을 실행합니다.

```bash
cd ../dsa-desktop
npm ci
npm test
npm run build
```

Windows 자동 업데이트 산출물을 확인하려면 다음 스크립트를 사용합니다.

```powershell
./scripts/verify-desktop-updater-artifacts.ps1 -ReleaseTag v$(node -p "require('./apps/dsa-desktop/package.json').version")
```

Release 페이지에서는 최소한 다음을 확인합니다.

- 설치 파일, `latest.yml`, `*.blockmap`이 같은 tag 기준으로 생성되었는지
- `latest.yml`의 `version`, `path`, `files.url`이 실제 파일명과 일치하는지
- Windows 설치형과 무설치 zip이 함께 업로드되었는지
- macOS x64와 arm64 산출물이 필요한 릴리스에 포함되었는지

## 수동 패키징

스크립트 대신 직접 패키징해야 할 때는 다음 순서로 진행합니다.

```bash
cd apps/dsa-web
npm install
npm run build
```

```bash
pip install pyinstaller
pip install -r requirements.txt
python -m PyInstaller --name stock_analysis --onefile --noconsole --add-data "static;static" --hidden-import=multipart --hidden-import=multipart.multipart main.py
```

```powershell
mkdir dist\backend
copy dist\stock_analysis.exe dist\backend\stock_analysis.exe
```

```bash
cd apps/dsa-desktop
npm install
npm run build
```

최종 산출물은 `apps/dsa-desktop/dist/` 아래에 생성됩니다.

## 무설치 배포 구조

Windows 무설치 빌드는 대략 다음 구조를 가집니다.

```text
win-unpacked/
  Daily Stock Analysis.exe
  .env
  data/
    stock_analysis.db
    stock_analysis.db-wal
    stock_analysis.db-shm
  logs/
    desktop.log
  resources/
    .env.example
    backend/
      stock_analysis.exe
```

`.env`가 없으면 앱은 `.env.example`을 참고해 기본 설정을 준비합니다. API 키, 분석 대상 종목, 알림 설정은 사용자 환경에 맞게 `.env` 또는 설정 화면에서 조정합니다.

## 설정 백업과 복원

Web UI와 데스크톱 앱은 설정 백업과 복원을 지원합니다. 운영 중인 환경에서는 다음 파일을 주기적으로 백업하는 것이 좋습니다.

- `.env`
- `data/stock_analysis.db`
- `data/stock_analysis.db-wal`
- `data/stock_analysis.db-shm`
- `logs/desktop.log`

데스크톱 업데이트 전에는 앱을 종료한 뒤 위 파일을 백업하고, 업데이트 후 설정 화면에서 API 키와 분석 대상 종목이 유지되는지 확인합니다.

## 문제 해결

| 증상 | 확인할 항목 |
| --- | --- |
| 백엔드 준비 상태에서 멈춤 | `logs/desktop.log`와 `/api/health` 응답을 확인합니다. |
| `ModuleNotFoundError` 발생 | `requirements.txt` 설치와 PyInstaller hidden import 설정을 확인합니다. |
| UI가 빈 화면으로 표시됨 | `apps/dsa-web` 빌드 산출물이 루트 `static/`에 반영되었는지 확인합니다. |
| 업데이트 후 설정이 사라짐 | `.env`와 `data/` 경로가 설치 경로 기준으로 유지되는지 확인합니다. |
| Windows 설치가 실패함 | 관리자 권한이 필요한 보호 디렉터리가 아닌 사용자 디렉터리에 설치합니다. |

문제가 재현되면 `logs/desktop.log`, 설치 방식, 실행 경로, 사용한 tag를 함께 기록해 원인을 좁힙니다.
