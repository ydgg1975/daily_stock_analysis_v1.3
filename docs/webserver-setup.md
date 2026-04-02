# Web + Server 后端服务完整部署指南

本文档说明如何启动完整的 Web 管理界面 + FastAPI 后端服务，包括需要开启的配置项和每一步执行的命令。

---

## 目录

- [架构说明](#架构说明)
- [方式一：本地运行（推荐开发/调试）](#方式一本地运行推荐开发调试)
- [方式二：Docker 部署（推荐生产）](#方式二docker-部署推荐生产)
- [.env 关键配置说明](#env-关键配置说明)
- [启动模式对照表](#启动模式对照表)
- [常用 API 端点](#常用-api-端点)
- [常见问题](#常见问题)

---

## 架构说明

```
前端 (React/Vite)  ──构建→  static/        (FastAPI 托管静态文件)
后端 (FastAPI)     ──运行→  api/app.py      (REST API + WebSocket)
入口               ──调度→  main.py         (--serve-only / --webui-only)
```

服务启动后：
- Web 管理界面：`http://127.0.0.1:8000`
- API 文档（Swagger）：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/api/health`

---

## 方式一：本地运行（推荐开发/调试）

### 第 1 步：克隆项目 & 安装 Python 依赖

```bash
git clone https://github.com/ZhuLinsen/daily_stock_analysis.git
cd daily_stock_analysis

# Python 3.10+ 推荐，建议使用虚拟环境
python -m venv venv

# Linux/Mac:
# source venv/bin/activate

# Windows PowerShell:
.\venv\Scripts\Activate.ps1

# Windows CMD:
# venv\Scripts\activate.bat

pip install -r requirements.txt
```

### 第 2 步：构建前端（首次运行必须执行）

前端代码在 `apps/dsa-web/`，构建产物输出到项目根目录的 `static/` 文件夹。

```bash
cd apps/dsa-web
npm install          # 安装前端依赖
npm run build        # 构建到 ../../static/
cd ../..
```

> 构建完成后，项目根目录会出现 `static/` 文件夹，内含 `index.html` 等静态资源。

### 第 3 步：配置环境变量

```bash
cp .env.example .env
# 用任意编辑器编辑 .env
```

**需要取消注释 / 填写的最小配置集（见下方详细说明）：**

```bash
# 1. 股票列表（必填）
STOCK_LIST=600519,300750,002594

# 2. AI 模型（至少一个）
GEMINI_API_KEY=your_gemini_key
# 或
# OPENAI_API_KEY=your_openai_key
# OPENAI_BASE_URL=https://api.deepseek.com/v1
# OPENAI_MODEL=deepseek-chat

# 3. 通知渠道（至少一个，可选 - 本地调试可暂不配置）
# TELEGRAM_BOT_TOKEN=xxx
# TELEGRAM_CHAT_ID=xxx

# 4. 开启 Web 服务（取消注释此行，或用命令行参数代替）
WEBUI_ENABLED=true
WEBUI_HOST=127.0.0.1    # 仅本机访问；局域网访问改为 0.0.0.0
WEBUI_PORT=8000
```

**让当前终端会话使用 .env 中的最新配置：**

- 激活 venv 时**不会**自动把 `.env` 载入当前 shell，只切换了 Python 环境。
- 每次**新启动**一次 `python main.py` 时，应用都会重新读取 `.env`，因此“改完 .env 再启动”会自动生效。
- 若你希望**当前 PowerShell 会话**里的环境变量与 `.env` 一致（例如在终端里 `echo $env:STOCK_LIST` 或给其他命令用），可在激活 venv 后执行下面脚本；**每次修改 `.env` 后重新执行一次**即可更新当前会话的变量：

```powershell
# 在项目根目录、已激活 venv 的前提下执行
Get-Content .env | ForEach-Object {
  $line = $_.Trim()
  if ($line -and $line -notmatch '^\s*#') {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
      $key = $Matches[1]
      $val = $Matches[2].Trim().Trim('"').Trim("'")
      Set-Item -Path "Env:$key" -Value $val
      Write-Host "$key = $val"
    }
  }
}
```

- 若服务已用 `python main.py --webui-only` 等**常驻运行**，修改 `.env` 不会影响该进程，需**重启服务**后新配置才会生效。

### 第 4 步：启动服务

```bash
# 推荐：仅启动 Web 服务，通过界面手动触发分析
python main.py --webui-only

# 或：启动 Web 服务 + 立即执行一次完整分析
python main.py --webui

# 或：通过环境变量控制（.env 中 WEBUI_ENABLED=true 时等效 --webui-only）
python main.py
```

访问 `http://127.0.0.1:8000` 即可使用。

---

## 方式二：Docker 部署（推荐生产）

Docker 方式会自动构建前端，无需手动执行 `npm run build`。

### 第 1 步：克隆项目

```bash
git clone https://github.com/ZhuLinsen/daily_stock_analysis.git
cd daily_stock_analysis
```

### 第 2 步：配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填写必要配置（见下方说明）
```

Docker 场景需要特别注意以下两项（docker-compose.yml 已自动覆盖）：

```bash
# docker/docker-compose.yml 中已强制设置，无需在 .env 中手动改
# WEBUI_HOST=0.0.0.0   ← 容器内必须绑定 0.0.0.0 才能通过端口映射访问
```

### 第 3 步：构建并启动容器

```bash
# 仅启动 Web+API 服务（推荐）
docker-compose -f ./docker/docker-compose.yml up -d server

# 同时启动 Web 服务 + 定时分析任务
docker-compose -f ./docker/docker-compose.yml up -d server analyzer

# 查看日志
docker-compose -f ./docker/docker-compose.yml logs -f server

# 查看容器状态
docker-compose -f ./docker/docker-compose.yml ps
```

访问 `http://localhost:8000` 即可使用。

### 常用 Docker 运维命令

```bash
# 停止服务
docker-compose -f ./docker/docker-compose.yml down

# 代码更新后重新构建
docker-compose -f ./docker/docker-compose.yml build --no-cache
docker-compose -f ./docker/docker-compose.yml up -d server

# 进入容器调试
docker exec -it stock-server bash
```

---

## .env 关键配置说明

以下为 Web+Server 模式涉及的所有配置项，按类别说明哪些需要取消注释。

### AI 模型（至少开启一个）

```bash
# ── 方案一：AIHubMix（推荐，无需科学上网）──
# AIHUBMIX_KEY=your_key_here
# OPENAI_MODEL=gemini-3.1-pro-preview

# ── 方案二：Gemini 直连 ──
GEMINI_API_KEY=your_gemini_key_here       # 取消注释并填写
GEMINI_MODEL=gemini-3-flash-preview
GEMINI_MODEL_FALLBACK=gemini-2.5-flash

# ── 方案三：Anthropic Claude ──
# ANTHROPIC_API_KEY=sk-ant-xxx
# ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
# ANTHROPIC_BASE_URL=https://your-proxy.example.com  # 中转站，可选

# ── 方案四：OpenAI 兼容 API（DeepSeek 等）──
# OPENAI_API_KEY=sk-xxx
# OPENAI_BASE_URL=https://api.deepseek.com/v1
# OPENAI_MODEL=deepseek-chat
```

### WebUI 服务配置

```bash
# 是否默认以服务模式启动（等效于命令行 --webui-only）
WEBUI_ENABLED=true                  # ← 取消注释，改为 true

# 监听地址
WEBUI_HOST=127.0.0.1               # 本机访问用此值
# WEBUI_HOST=0.0.0.0               # 局域网/Docker 访问改为此值

# 监听端口
WEBUI_PORT=8000
```

### Web 登录认证（可选）

```bash
# 启用后首次访问网页时设置初始密码
ADMIN_AUTH_ENABLED=false            # 改为 true 开启密码保护
# ADMIN_SESSION_MAX_AGE_HOURS=24   # Session 有效期，默认 24 小时
```

### Agent 策略对话（可选）

```bash
# 开启后可在 /chat 页面进行多轮 AI 策略问答
# AGENT_MODE=true                  # 取消注释开启
# AGENT_MAX_STEPS=10
# AGENT_SKILLS=bull_trend,ma_golden_cross,shrink_pullback
```

### 定时分析任务（可选，与 Web 服务组合使用）

```bash
# 在 Web 服务同时执行定时分析（使用 --webui 而非 --webui-only 时生效）
SCHEDULE_ENABLED=false              # 改为 true 开启每日定时
SCHEDULE_TIME=18:00                 # 每日执行时间（北京时间）
RUN_IMMEDIATELY=true                # 启动时是否立即执行一次
```

### 通知渠道（可选，调试期间可不配置）

```bash
# Telegram
# TELEGRAM_BOT_TOKEN=123456789:ABCdefGHI...
# TELEGRAM_CHAT_ID=123456789

# 企业微信
# WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx

# 邮件
# EMAIL_SENDER=your@qq.com
# EMAIL_PASSWORD=your_auth_code
# EMAIL_RECEIVERS=receiver@example.com
```

---

## 启动模式对照表

| 命令 | 效果 | 适用场景 |
|------|------|----------|
| `python main.py --webui-only` | 仅启动 Web 服务，不自动分析 | 纯 UI 管理，手动触发分析 |
| `python main.py --webui` | 启动 Web 服务 + 执行一次完整分析 | 启动即分析一次 |
| `python main.py --serve-only` | 同 `--webui-only`（等效别名） | 同上 |
| `python main.py --serve` | 同 `--webui`（等效别名） | 同上 |
| `python main.py --webui-only --schedule` | Web 服务 + 定时任务 | 长期后台服务 |
| `docker-compose ... up -d server` | Docker Web 服务模式 | 生产环境 |
| `docker-compose ... up -d` | Docker Web + 定时任务 | 生产环境全功能 |

---

## 常用 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/docs` | GET | Swagger API 文档 |
| `/api/v1/analysis/analyze` | POST | 触发个股分析 |
| `/api/v1/analysis/tasks` | GET | 查询任务列表 |
| `/api/v1/analysis/status/{task_id}` | GET | 查询任务状态 |
| `/api/v1/history` | GET | 查询历史分析记录 |
| `/api/v1/backtest/run` | POST | 触发回测 |
| `/api/v1/backtest/performance` | GET | 查询整体回测绩效 |
| `/api/v1/agent/chat/stream` | POST (SSE) | Agent 策略对话（流式） |
| `/api/v1/stocks/extract-from-image` | POST | 从图片提取股票代码 |

**示例：触发单股分析**

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analysis/analyze \
  -H 'Content-Type: application/json' \
  -d '{"stock_code": "600519"}'
```

**示例：查询任务状态**

```bash
curl http://127.0.0.1:8000/api/v1/analysis/status/<task_id>
```

---

## 常见问题

### Q：修改了 .env，如何让配置生效？

- **新启动的进程**：每次执行 `python main.py`（或其它入口）时都会重新读 `.env`，改完保存后重新运行即可。
- **当前 PowerShell 会话**：若希望当前终端里的环境变量与 `.env` 一致，见上文「让当前终端会话使用 .env 中的最新配置」中的脚本，修改 `.env` 后重新执行该脚本即可更新。
- **已运行中的 Web 服务**：修改 `.env` 不会影响已启动的进程，需要重启服务（先停止再重新执行 `python main.py --webui-only` 等）后新配置才会生效。

### Q：访问 `http://127.0.0.1:8000` 显示 404？

前端静态文件未构建。执行：

```bash
cd apps/dsa-web && npm install && npm run build && cd ../..
```

确认 `static/index.html` 文件存在后重启服务。

### Q：局域网其他设备无法访问？

将 `.env` 中 `WEBUI_HOST` 改为 `0.0.0.0`：

```bash
WEBUI_HOST=0.0.0.0
```

或使用命令行参数：

```bash
python main.py --webui-only --host 0.0.0.0 --port 8000
```

### Q：Docker 容器内无法访问外网（Gemini/OpenAI）？

在 `docker/docker-compose.yml` 中取消代理注释：

```yaml
environment:
  - http_proxy=http://host.docker.internal:10809
  - https_proxy=http://host.docker.internal:10809
```

或在 `.env` 中配置：

```bash
USE_PROXY=true
PROXY_HOST=127.0.0.1
PROXY_PORT=10809
```

### Q：如何修改服务端口？

方法一（命令行）：

```bash
python main.py --webui-only --port 9000
```

方法二（.env）：

```bash
WEBUI_PORT=9000
```

方法三（Docker）：

```bash
API_PORT=9000 docker-compose -f ./docker/docker-compose.yml up -d server
```

### Q：忘记 Web 登录密码怎么办？

```bash
# 本地
python -m src.auth reset_password

# Docker
docker exec -it stock-server python -m src.auth reset_password
```

### Q：Agent 对话功能不可用？

1. 确认 `.env` 中 `AGENT_MODE=true`（取消注释）
2. 确认至少配置了一个 AI 模型 API Key
3. 重启服务后访问 `http://127.0.0.1:8000/chat`
