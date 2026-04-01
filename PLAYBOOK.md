# 🚀 股票智能分析系统 - 可执行入门指南

> 本指南是一个"可执行的笔记本"，每个命令都可以直接复制运行。
> 按照顺序执行，即可快速启动项目。

---

## 📋 前置检查

### 1. 检查 Python 版本

```bash
python3 --version
```

**期望输出**: `Python 3.10.x` 或更高版本

---

## 🔧 步骤 1: 安装 uv（推荐的 Python 包管理器）

uv 是一个超快的 Python 包安装器和项目管理器。

### 安装 uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 验证安装

```bash
uv --version
```

---

## 📥 步骤 2: 克隆项目

如果你还没有克隆项目：

```bash
git clone https://github.com/ZhuLinsen/daily_stock_analysis.git && cd daily_stock_analysis
```

如果你已经在项目目录中：

```bash
cd /home/frank/code/daily_stock_analysis
```

---

## 📦 步骤 3: 安装依赖

### 方式 A: 使用 uv（推荐，更快）

```bash
uv sync
```

或者，如果 `pyproject.toml` 还未完全配置：

```bash
uv pip install -r requirements.txt
```

### 方式 B: 使用 pip

```bash
pip install -r requirements.txt
```

---

## ⚙️ 步骤 4: 配置环境变量

### 复制配置文件

```bash
cp .env.example .env
```

### 编辑配置文件

```bash
vim .env
```

### 最小配置（至少配置一个 AI 模型）

在 `.env` 文件中添加以下配置（选择其中一个即可）：

#### 选项 1: 使用 AIHubMix（推荐，无需科学上网）

```env
AIHUBMIX_KEY=your_aihubmix_key_here
LITELLM_MODEL=aihubmix/gpt-4o
```

#### 选项 2: 使用 Google Gemini（需科学上网）

```env
GEMINI_API_KEY=your_gemini_api_key_here
LITELLM_MODEL=gemini/gemini-pro
```

#### 选项 3: 使用 DeepSeek

```env
OPENAI_API_KEY=your_deepseek_key_here
OPENAI_BASE_URL=https://api.deepseek.com/v1
LITELLM_MODEL=openai/deepseek-chat
```

#### 选项 4: 使用 Ollama 本地模型（免费，无需 API Key）

```env
OLLAMA_API_BASE=http://localhost:11434
LITELLM_MODEL=ollama/llama2
```

### 配置自选股列表

```env
STOCK_LIST=600519,hk00700,AAPL
```

### 可选：配置搜索 API（用于获取股票新闻）

```env
TAVILY_API_KEYS=your_tavily_api_key_here
```

> 💡 获取 TAVILY API Key: https://tavily.com/ (每月 1000 次免费调用)

---

## 🎯 步骤 5: 运行项目

### 方式 A: 使用 uv run（推荐）

```bash
uv run main.py
```

### 方式 B: 使用 python3

```bash
python3 main.py
```

---

## 🌐 启动 Web 界面

### 仅启动 Web 界面（不执行定时任务）

```bash
uv run main.py --webui-only
```

或者

```bash
python3 main.py --webui-only
```

访问：http://127.0.0.1:8000

### 启动完整服务（Web + 定时任务）

```bash
uv run main.py --webui
```

---

## 🧪 步骤 6: 测试运行

### 测试单只股票分析

```bash
uv run main.py --stocks 600519
```

### 调试模式运行

```bash
uv run main.py --debug
```

### 干运行（不实际执行，仅检查配置）

```bash
uv run main.py --dry-run
```

---

##  配置通知渠道（可选）

### 企业微信

在 `.env` 中添加：

```env
WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY
```

### Telegram

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 邮件通知

```env
EMAIL_SENDER=your_email@example.com
EMAIL_PASSWORD=your_email_password_or_auth_code
EMAIL_RECEIVERS=recipient@example.com
```

---

## 📅 配置定时任务

### GitHub Actions 定时运行

1. Fork 本仓库
2. 在 GitHub 仓库的 `Settings` → `Secrets and variables` → `Actions` 中配置 Secrets
3. 启用 Actions: `Actions` → `I understand my workflows, go ahead and enable them`
4. 默认每个工作日 18:00（北京时间）自动执行

### 本地 Cron 定时任务

```bash
crontab -e
```

添加以下行（每个工作日 18:00 执行）：

```cron
0 10 * * 1-5 cd /path/to/daily_stock_analysis && /path/to/uv run main.py >> /var/log/stock_analysis.log 2>&1
```

---

## 🐳 Docker 部署（可选）

### 构建并运行 Docker 容器

```bash
cd docker
docker-compose up -d
```

### 查看日志

```bash
docker-compose logs -f
```

### 停止服务

```bash
docker-compose down
```

---

## 🧹 故障排查

### 问题 1: 依赖安装失败

```bash
# 清理缓存重试
uv cache clean
uv sync
```

### 问题 2: API Key 无效

检查 `.env` 文件中的 API Key 是否正确，无多余空格：

```bash
cat .env | grep API_KEY
```

### 问题 3: 端口被占用

如果 8000 端口被占用，可以修改端口：

```bash
uv run main.py --webui-only --port 8001
```

或者在 `.env` 中设置：

```env
PORT=8001
```

### 问题 4: 查看日志

```bash
# 查看最近的日志
tail -f /var/log/stock_analysis.log

# 或者在运行时查看详细日志
uv run main.py --debug
```

---

## 📚 常用命令速查

| 命令 | 说明 |
|------|------|
| `uv run main.py` | 运行主程序 |
| `uv run main.py --webui-only` | 仅启动 Web 界面 |
| `uv run main.py --stocks 600519,AAPL` | 分析指定股票 |
| `uv run main.py --debug` | 调试模式 |
| `uv run main.py --dry-run` | 干运行（不执行） |
| `uv run main.py --market-review` | 市场复盘模式 |
| `uv run main.py --schedule` | 定时任务模式 |

---

## 🔗 下一步

- 📖 [完整配置指南](docs/full-guide.md)
- ❓ [常见问题解答](docs/FAQ.md)
- 🤖 [机器人命令说明](docs/bot-command.md)
- 📊 [LLM 配置指南](docs/LLM_CONFIG_GUIDE.md)

---

## 📞 获取帮助

- 提交 Issue: https://github.com/ZhuLinsen/daily_stock_analysis/issues
- 查看文档：https://github.com/ZhuLinsen/daily_stock_analysis/tree/main/docs

---

**祝你投资顺利！📈**