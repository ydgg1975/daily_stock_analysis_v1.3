# 클라우드 서버 WebUI 접속 가이드

이 문서는 클라우드 서버에 daily_stock_analysis를 배포한 뒤 브라우저에서 WebUI를 여는 방법을 설명합니다. 핵심은 서비스가 외부 접속 주소를 listen하도록 설정하고, 서버 방화벽과 보안 그룹에서 포트를 열어두는 것입니다.

## 직접 실행

프로젝트 루트의 `.env`에서 WebUI listen 주소를 확인합니다.

```env
WEBUI_HOST=127.0.0.1
```

클라우드 서버에서 외부 접속을 허용하려면 다음처럼 바꿉니다.

```env
WEBUI_HOST=0.0.0.0
```

`127.0.0.1`은 서버 내부에서만 접속할 수 있고, `0.0.0.0`은 외부 네트워크 인터페이스에서도 접속할 수 있게 합니다. `--host 0.0.0.0`을 명시하더라도 `.env`에 `WEBUI_HOST=127.0.0.1`이 남아 있으면 실행 경로에 따라 로컬 전용으로 뜰 수 있으므로 먼저 `.env`를 확인하세요.

서비스를 시작합니다.

```bash
# WebUI만 실행
python main.py --serve-only

# WebUI와 분석 흐름을 함께 실행
python main.py --serve
```

정상 시작 시 다음과 비슷한 주소가 로그에 표시됩니다.

```text
FastAPI 서비스가 시작되었습니다: http://0.0.0.0:8000
```

터미널 종료 후에도 계속 실행하려면 Linux 서버에서 `nohup`이나 systemd 같은 프로세스 관리 방식을 사용합니다.

```bash
nohup python main.py --serve-only > /dev/null 2>&1 &
```

기본 포트는 `8000`입니다. 변경하려면 `.env`에 다음 값을 설정하고 서비스를 재시작합니다.

```env
WEBUI_PORT=8888
```

## Docker Compose

Docker Compose를 사용하면 `docker/docker-compose.yml`에서 컨테이너 내부 WebUI host를 `0.0.0.0`으로 설정합니다. 서버 외부 포트는 `.env`의 `API_PORT`로 조정할 수 있습니다.

```bash
# 전체 서비스 실행
docker-compose -f ./docker/docker-compose.yml up -d

# WebUI 서버만 실행
docker-compose -f ./docker/docker-compose.yml up -d server

# 상태 확인
docker-compose -f ./docker/docker-compose.yml ps
```

포트를 바꾸려면 `.env`에 다음 값을 설정한 뒤 컨테이너를 다시 올립니다.

```env
API_PORT=8888
```

```bash
docker-compose -f ./docker/docker-compose.yml down
docker-compose -f ./docker/docker-compose.yml up -d
```

## 브라우저 접속

서비스가 시작되면 브라우저에서 서버 공인 IP와 포트를 입력합니다.

```text
http://서버공인IP:8000
```

예를 들어 공인 IP가 `1.2.3.4`라면 다음 주소를 사용합니다.

```text
http://1.2.3.4:8000
```

도메인이 서버로 연결되어 있다면 도메인으로도 접속할 수 있습니다.

```text
http://your-domain.com:8000
```

공인 IP는 클라우드 콘솔의 인스턴스 상세 화면에서 확인할 수 있습니다.

## Docker 재빌드 확인

Docker 이미지 버전과 WebUI 정적 파일 빌드는 서로 다른 기준입니다.

- Docker 이미지 버전은 배포에 사용한 이미지 tag 또는 GitHub Releases를 기준으로 확인합니다.
- WebUI 정적 파일은 설정 화면의 버전 정보 카드에서 빌드 식별자와 빌드 시간을 확인합니다.

프런트엔드만 다시 빌드했는지 확인하려면 다음 명령을 실행한 뒤 브라우저를 강제 새로고침합니다.

```bash
cd apps/dsa-web
npm ci
npm run lint
npm run build
```

Docker까지 다시 만들려면 다음처럼 no-cache 빌드를 사용할 수 있습니다.

```bash
docker-compose -f ./docker/docker-compose.yml down
docker-compose -f ./docker/docker-compose.yml build --no-cache
docker-compose -f ./docker/docker-compose.yml up -d
```

## 접속 문제 확인

### 보안 그룹 또는 방화벽

클라우드 서버는 기본적으로 SSH 포트만 열려 있는 경우가 많습니다. 클라우드 콘솔의 보안 그룹 또는 방화벽 규칙에서 TCP `8000` 포트를 허용합니다. 포트를 바꿨다면 바꾼 포트를 열어야 합니다.

Linux 방화벽을 사용하는 경우:

```bash
# Ubuntu / Debian
sudo ufw allow 8000

# CentOS / RHEL
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

### WEBUI_HOST 설정

직접 실행 방식에서 `.env`에 `WEBUI_HOST=127.0.0.1`이 남아 있으면 외부에서 접속할 수 없습니다. 클라우드 서버에서는 `WEBUI_HOST=0.0.0.0`으로 변경한 뒤 재시작합니다. Docker 방식은 compose 설정에서 처리하므로 보통 이 변경이 필요하지 않습니다.

### 포트 불일치

브라우저 주소의 포트가 `.env` 또는 Docker Compose에서 노출한 포트와 같은지 확인합니다.

- 직접 실행: 기본 `8000`, `WEBUI_PORT`로 변경
- Docker: 기본 `8000`, `API_PORT`로 변경

### 화면은 열리지만 스타일이 깨짐

`static/index.html`은 있지만 `static/assets/`의 JS/CSS 파일이 없으면 브라우저가 기본 HTML처럼 렌더링합니다. 개발자 도구 Network 탭에서 `/assets/index-*.js` 또는 `/assets/index-*.css` 404가 있는지 확인하세요.

직접 실행 환경에서는 WebUI를 다시 빌드합니다.

```bash
cd apps/dsa-web
npm ci
npm run build
cd ../..
python main.py --serve-only
```

Docker 환경에서는 이미지를 다시 빌드합니다.

```bash
docker-compose -f ./docker/docker-compose.yml down
docker-compose -f ./docker/docker-compose.yml build --no-cache
docker-compose -f ./docker/docker-compose.yml up -d
```

## Nginx 역방향 프록시

도메인을 사용하거나 주소에서 `:8000`을 숨기려면 Nginx를 앞단에 둘 수 있습니다.

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y nginx

# CentOS
sudo yum install -y nginx
```

`/etc/nginx/conf.d/stock-analyzer.conf` 예시:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Agent 대화 페이지의 WebSocket 연결 지원
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

설정을 검사하고 Nginx를 다시 불러옵니다.

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Nginx 뒤에서 Web 로그인 인증을 사용할 때는 `.env`에 `TRUST_X_FORWARDED_FOR=true`를 설정할지 검토하세요. 단일 신뢰 프록시 구조에서는 실제 클라이언트 IP 판단에 도움이 되지만, CDN이나 다중 프록시 구조에서는 별도 검토가 필요합니다.

HTTPS가 필요하면 [Certbot](https://certbot.eff.org/)으로 Let's Encrypt 인증서를 발급할 수 있습니다.

## 보안 권장 사항

WebUI를 외부에 노출하기 전에는 관리자 인증을 켜는 것을 권장합니다.

```env
ADMIN_AUTH_ENABLED=true
```

처음 접속할 때 초기 비밀번호를 설정하고, 이후 설정 화면 접근 시 인증을 요구합니다. 비밀번호를 잊었다면 서버에서 다음 명령으로 재설정할 수 있습니다.

```bash
python -m src.auth reset_password
```

추가 문제가 있으면 [Issue](https://github.com/robot0971-art/daily_stock_analysis/issues)에 재현 절차와 로그를 남겨주세요.
