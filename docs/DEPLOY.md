# 배포 가이드

이 문서는 Daily Stock Analysis를 서버, Docker, systemd, GitHub Actions 환경에 배포하는 방법을 설명합니다.

## 배포 방식 비교

| 방식 | 장점 | 단점 | 권장 상황 |
| --- | --- | --- | --- |
| Docker Compose | 실행 환경 격리, 재배포와 이전이 쉬움 | Docker 설치 필요 | 대부분의 서버 배포 |
| 직접 실행 | 구조가 단순함 | Python/Node 의존성을 직접 관리해야 함 | 임시 테스트, 소규모 운영 |
| systemd | 서버 부팅 시 자동 실행, 재시작 관리 | 서비스 파일 관리 필요 | 장기 운영 |
| GitHub Actions | 별도 서버 없이 정기 실행 가능 | HTTP API/WebUI 제공 불가, 무상태 실행 | 알림용 일일 분석 |

일반적인 서버 운영은 Docker Compose를 권장합니다.

## Docker Compose 배포

### 1. Docker 설치

```bash
# Ubuntu / Debian
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# CentOS / RHEL 계열
sudo yum install -y docker docker-compose
sudo systemctl start docker
sudo systemctl enable docker
```

### 2. 코드와 설정 준비

```bash
git clone <your-repo-url> /opt/stock-analyzer
cd /opt/stock-analyzer

cp .env.example .env
vim .env
```

`.env`에는 최소한 LLM API Key, 분석할 종목, 필요한 알림 채널을 설정합니다.

### 3. 서비스 시작

```bash
docker-compose -f ./docker/docker-compose.yml up -d
docker-compose -f ./docker/docker-compose.yml logs -f
docker-compose -f ./docker/docker-compose.yml ps
```

시작 후 브라우저에서 다음 주소를 엽니다.

```text
http://서버공인IP:8000
```

접속되지 않으면 클라우드 보안 그룹 또는 서버 방화벽에서 TCP `8000` 포트를 열었는지 확인합니다. 자세한 내용은 [클라우드 서버 WebUI 접속 가이드](deploy-webui-cloud.md)를 참고하세요.

### 4. 관리 명령

```bash
# 중지
docker-compose -f ./docker/docker-compose.yml down

# 재시작
docker-compose -f ./docker/docker-compose.yml restart

# 코드 갱신 후 재배포
git pull
docker-compose -f ./docker/docker-compose.yml build --no-cache
docker-compose -f ./docker/docker-compose.yml up -d

# 컨테이너 안에서 디버깅
docker-compose -f ./docker/docker-compose.yml exec -u dsa stock-analyzer bash

# 수동 분석 실행
docker-compose -f ./docker/docker-compose.yml exec -u dsa stock-analyzer python main.py --dry-run
```

### 5. 데이터 보존

다음 디렉터리는 호스트에 남습니다.

- `./data/`: 데이터베이스와 캐시
- `./logs/`: 실행 로그
- `./reports/`: 분석 보고서

### 6. 권한

Docker 이미지의 시작 스크립트는 `./data`, `./logs`, `./reports` 디렉터리를 만들고 권한을 보정한 뒤, 비 root 사용자 `dsa`(UID 1000)로 애플리케이션을 실행합니다. 일반 배포에서는 별도 `chown`이나 `chmod`가 필요하지 않습니다.

`--user`, Compose `user:`, rootless Docker, NFS, 읽기 전용 마운트를 사용하는 경우에는 실제 실행 사용자가 위 디렉터리에 쓸 수 있는지 직접 확인해야 합니다.

## 직접 실행

### 1. Python 환경 준비

```bash
sudo apt update
sudo apt install -y python3.10 python3.10-venv python3-pip

python3.10 -m venv /opt/stock-analyzer/venv
source /opt/stock-analyzer/venv/bin/activate
```

### 2. 의존성 설치

```bash
cd /opt/stock-analyzer
pip install -r requirements.txt
```

### 3. 환경 변수 설정

```bash
cp .env.example .env
vim .env
```

### 4. 실행

```bash
# 단일 실행
python main.py

# 스케줄 모드
python main.py --schedule

# 백그라운드 실행
nohup python main.py --schedule > /dev/null 2>&1 &

# WebUI만 실행
python main.py --serve-only

# WebUI와 분석 흐름 실행
python main.py --serve
```

클라우드 서버에서 WebUI를 외부에 노출하려면 `.env`에서 `WEBUI_HOST=0.0.0.0`을 설정하고 포트를 열어야 합니다.

## systemd 서비스

장기 운영 서버에서는 systemd로 자동 시작과 재시작을 관리할 수 있습니다.

### 1. 서비스 파일 작성

```bash
sudo vim /etc/systemd/system/stock-analyzer.service
```

예시:

```ini
[Unit]
Description=Daily Stock Analysis
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/stock-analyzer
Environment="PATH=/opt/stock-analyzer/venv/bin"
ExecStart=/opt/stock-analyzer/venv/bin/python main.py --schedule
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

### 2. 서비스 시작

```bash
sudo systemctl daemon-reload
sudo systemctl start stock-analyzer
sudo systemctl enable stock-analyzer
sudo systemctl status stock-analyzer
journalctl -u stock-analyzer -f
```

## 주요 설정

### 필수 또는 권장 설정

| 설정 | 설명 |
| --- | --- |
| `ANSPIRE_API_KEYS` / `AIHUBMIX_KEY` / `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | LLM provider 중 하나 이상 |
| `STOCK_LIST` | 분석할 종목 목록. 쉼표로 구분 |
| 알림 채널 | Feishu, Telegram, Discord, 이메일, 사용자 지정 Webhook 등 |

### 선택 설정

| 설정 | 기본값 | 설명 |
| --- | --- | --- |
| `SCHEDULE_ENABLED` | `false` | 스케줄 실행 여부 |
| `SCHEDULE_TIME` | `18:00` | 매일 실행 시간 |
| `MARKET_REVIEW_ENABLED` | `true` | 시장 리뷰 포함 여부 |
| `SERPAPI_API_KEYS` | 없음 | 뉴스 검색 provider |
| `TAVILY_API_KEYS` | 없음 | 뉴스 검색 provider |
| `MINIMAX_API_KEYS` | 없음 | 검색 provider |
| `WEBUI_HOST` | `127.0.0.1` | WebUI listen 주소 |
| `WEBUI_PORT` | `8000` | WebUI 포트 |

LLM 채널을 자세히 설정하려면 [LLM 설정 가이드](LLM_CONFIG_GUIDE.md)를 참고하세요.

## 프록시

서버 환경에서 특정 LLM API에 직접 접속할 수 없다면 프록시를 설정합니다.

Docker Compose 예시:

```yaml
environment:
  - http_proxy=http://your-proxy:port
  - https_proxy=http://your-proxy:port
```

직접 실행 환경에서는 쉘 환경 변수 또는 서비스 파일의 `Environment=`로 설정하는 방식을 권장합니다. 코드에 프록시 값을 하드코딩하지 마세요.

## 운영과 점검

### 로그 확인

```bash
# Docker
docker-compose -f ./docker/docker-compose.yml logs -f --tail=100

# 직접 실행
tail -f /opt/stock-analyzer/logs/stock_analysis_*.log
```

### 상태 확인

```bash
ps aux | grep main.py
ls -la /opt/stock-analyzer/reports/
```

### 정기 정리

```bash
# 7일 이상 지난 로그 정리
find /opt/stock-analyzer/logs -mtime +7 -delete

# 30일 이상 지난 보고서 정리
find /opt/stock-analyzer/reports -mtime +30 -delete
```

## 문제 해결

### Docker 빌드 실패

캐시를 비우고 다시 빌드합니다.

```bash
docker-compose -f ./docker/docker-compose.yml build --no-cache
```

### API 접속 시간 초과

서버에서 LLM provider API에 접근 가능한지 확인합니다. 네트워크 제한이 있는 환경이라면 프록시 또는 접근 가능한 provider를 사용합니다.

### 데이터베이스 lock 오류

서비스를 중지한 뒤 lock 파일을 확인합니다.

```bash
docker-compose -f ./docker/docker-compose.yml down
rm -f /opt/stock-analyzer/data/*.lock
```

### 메모리 부족

Compose 환경이라면 메모리 제한을 조정합니다.

```yaml
deploy:
  resources:
    limits:
      memory: 1G
```

### WebUI가 열리지만 화면이 깨짐

증상: 8000 포트에는 접속되지만 글자와 버튼이 비정상적으로 크고 스타일이 적용되지 않습니다.

원인: `static/index.html`은 있지만 `static/assets/`의 JS/CSS 파일이 없거나 404로 응답합니다.

Docker 환경:

```bash
docker-compose -f ./docker/docker-compose.yml down
docker-compose -f ./docker/docker-compose.yml build --no-cache
docker-compose -f ./docker/docker-compose.yml up -d
```

직접 실행 환경:

```bash
cd apps/dsa-web
npm ci
npm run build
cd ../..
python main.py --serve-only
```

브라우저 개발자 도구의 Network 탭에서 `/assets/index-*.js`와 `/assets/index-*.css` 404가 있는지 확인합니다.

## 서버 이전

기존 서버에서 설정과 데이터를 묶어 새 서버로 옮길 수 있습니다.

```bash
# 기존 서버
cd /opt/stock-analyzer
tar -czvf stock-analyzer-backup.tar.gz .env data/ logs/ reports/

# 새 서버
mkdir -p /opt/stock-analyzer
cd /opt/stock-analyzer
git clone <your-repo-url> .
tar -xzvf stock-analyzer-backup.tar.gz
docker-compose -f ./docker/docker-compose.yml up -d
```

## GitHub Actions 배포

서버 없이 GitHub Actions에서 정해진 시간에 분석을 실행하고 알림만 받을 수 있습니다.

### 장점

- 별도 서버가 필요 없습니다.
- 정기 실행을 GitHub Actions가 처리합니다.
- 운영 관리 부담이 적습니다.

### 제한

- 매 실행이 새 환경에서 시작됩니다.
- WebUI와 HTTP API를 제공하지 않습니다.
- GitHub Actions 스케줄은 지연될 수 있습니다.

### 1. 저장소 준비

```bash
cd /path/to/daily_stock_analysis
git init
git add .
git commit -m "Initial commit"

git remote add origin https://github.com/your-name/daily_stock_analysis.git
git branch -M main
git push -u origin main
```

### 2. Secrets 설정

GitHub 저장소에서 `Settings -> Secrets and variables -> Actions -> New repository secret`으로 이동해 필요한 값을 추가합니다.

| Secret | 설명 | 필수 |
| --- | --- | --- |
| `STOCK_LIST` | 분석할 종목 목록. 예: `600519,AAPL` | 예 |
| `ANSPIRE_API_KEYS` | Anspire Open API Key | 권장 |
| `AIHUBMIX_KEY` | AIHubMix API Key | 권장 |
| `ANTHROPIC_API_KEY` | Anthropic API Key | 선택 |
| `GEMINI_API_KEY` | Gemini API Key | 선택 |
| `OPENAI_API_KEY` | OpenAI 또는 OpenAI 호환 API Key | 선택 |
| `SERPAPI_API_KEYS` | SerpAPI Key | 권장 |
| `TAVILY_API_KEYS` | Tavily API Key | 선택 |
| `TUSHARE_TOKEN` | Tushare Token | 선택 |
| `FEISHU_WEBHOOK_URL` | Feishu Webhook | 선택 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | 선택 |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | 선택 |
| `DISCORD_WEBHOOK_URL` | Discord Webhook | 선택 |
| `EMAIL_SENDER` | 발신 이메일 | 선택 |
| `EMAIL_PASSWORD` | 이메일 앱 비밀번호 또는 인증 코드 | 선택 |
| `CUSTOM_WEBHOOK_URLS` | 사용자 지정 Webhook 목록 | 선택 |

LLM provider는 하나 이상, 알림 채널은 목적에 맞게 하나 이상 설정하는 것을 권장합니다.

### 3. Workflow 확인

`.github/workflows/daily_analysis.yml`이 저장소에 포함되어 있어야 합니다.

```bash
git add .github/workflows/daily_analysis.yml
git commit -m "Add GitHub Actions workflow"
git push
```

### 4. 수동 실행 테스트

1. GitHub 저장소의 Actions 탭을 엽니다.
2. 일일 분석 workflow를 선택합니다.
3. `Run workflow`를 누릅니다.
4. 실행 모드를 선택합니다.
   - `full`: 종목 분석과 시장 리뷰
   - `market-only`: 시장 리뷰만
   - `stocks-only`: 종목 분석만
5. 실행 로그와 Artifact를 확인합니다.

### 5. 스케줄

GitHub Actions cron은 UTC 기준입니다.

```yaml
schedule:
  - cron: "0 10 * * 1-5"  # UTC 10:00
```

예시:

| cron | 의미 |
| --- | --- |
| `0 10 * * 1-5` | 월-금 UTC 10:00 |
| `30 7 * * 1-5` | 월-금 UTC 07:30 |
| `0 10 * * *` | 매일 UTC 10:00 |

한국 시간은 UTC보다 9시간 빠릅니다.

## 클라우드 WebUI 접속

클라우드 서버에 배포했지만 브라우저 접속 주소를 모르겠다면 [클라우드 서버 WebUI 접속 가이드](deploy-webui-cloud.md)를 참고하세요.

해당 문서는 직접 실행과 Docker Compose 방식, 보안 그룹/방화벽, Nginx 역방향 프록시, 화면 깨짐 문제를 함께 다룹니다.
