# Web UI 클라우드 배포

이 문서는 Web UI를 클라우드 서버에서 실행하는 최소 절차를 설명합니다.

## 1. 서버 준비

- Python 3.10 이상
- Node.js
- Git
- 필요한 경우 Docker와 Nginx

## 2. 저장소 준비

```bash
git clone https://github.com/ZhuLinsen/daily_stock_analysis.git
cd daily_stock_analysis
pip install -r requirements.txt
cp .env.example .env
```

## 3. Web UI 빌드

```bash
cd apps/dsa-web
npm ci
npm run build
cd ../..
```

## 4. 서버 실행

```bash
python main.py --serve-only
```

예약 분석까지 함께 실행하려면:

```bash
python main.py --serve
```

## 5. Docker 실행

```bash
docker compose -f ./docker/docker-compose.yml up -d --build
```

## 6. Nginx 예시

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

설정 후 문법 검사와 재시작을 실행합니다.

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 7. 배포 확인

- Web UI 접속
- `/api/health` 응답
- 종목 검색
- 단일 종목 분석
- 설정 저장
- 알림 전송

## 8. 보안 권장

공개 서버에서는 관리자 인증을 켜고, API 키가 화면과 로그에 노출되지 않도록 확인하세요.
