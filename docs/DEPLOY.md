# 🚀 部署指南

本文档介绍如何将 A股自选股智能分析系统部署到服务器。

## 📋 部署方案对比

| 方案 | 优点 | 缺点 | 推荐场景 |
|------|------|------|----------|
| **Docker Compose** ⭐ | 一键部署、环境隔离、自动重启 | 需要安装 Docker | 生产环境、云服务器 |
| **直接部署** | 无需容器化、灵活度高 | 依赖管理较复杂、环境易污染 | 本地开发、测试 |
| **GitHub Actions** | 零成本、全自动化、无需服务器 | 只能定时运行、无 Web 界面 | 仅需每日推送报告的用户 |

---

## 🐳 方案一：Docker Compose 部署 (推荐)

这是最简单、最稳定的部署方式。

### 1. 准备工作
- 安装 [Docker](https://docs.docker.com/get-docker/)
- 安装 [Docker Compose](https://docs.docker.com/compose/install/)

### 2. 获取代码与配置
```bash
git clone https://github.com/ZhuLinsen/daily_stock_analysis.git
cd daily_stock_analysis
cp .env.example .env
```

### 3. 修改配置文件
编辑 `.env` 文件，填入你的 AI API Key 和通知配置。
> 详情请参考 [配置指南](full-guide.md#3-配置说明)

### 4. 启动服务
```bash
docker-compose up -d
```

### 5. 查看运行状态
```bash
docker-compose logs -f
```

> **权限说明**：容器默认以非 root 用户 `dsa` (UID 1000) 运行。如果您在宿主机手动创建了挂载目录且遇到了 `Permission denied` 错误，请在宿主机执行以下命令修复权限：
> ```bash
> sudo chown -R 1000:1000 ./data ./logs ./reports
> ```

---

## 🖥️ 方案二：直接部署

### 1. 环境要求
- Python 3.10+
- Node.js 20+ (仅 Web 管理界面需要)

### 2. 安装依赖
```bash
# 后端依赖
pip install -r requirements.txt

# 前端依赖 (如需 Web 界面)
cd apps/dsa-web
npm install
npm run build
cd ../..
```

### 3. 运行程序
- **定时调度模式**: `python main.py --schedule`
- **Web 服务模式**: `python main.py --serve`
- **单次分析模式**: `python main.py --stocks 600519`

---

## ⚡ 方案三：GitHub Actions 零成本部署

适合不想折腾服务器，只需每天在微信/Telegram 收到报告的用户。

1. **Fork 本仓库** 到你的 GitHub 账号。
2. **配置 Secrets**: 在你的 Fork 仓库中，进入 `Settings > Secrets and variables > Actions`。
3. **添加配置**: 点击 `New repository secret`，将 `.env` 中的配置项（如 `GEMINI_API_KEY`, `STOCK_LIST` 等）逐一添加。
4. **启用 Workflow**: 点击仓库顶部的 `Actions` 标签，找到 `Daily Stock Analysis`，点击 `Enable workflow`。
5. **手动测试**: 可以点击 `Run workflow` 立即测试一次。

**Q: 免费额度够用吗？**
A: 每次运行约 2-5 分钟，一个月 22 个工作日 = 44-110 分钟，远低于 2000 分钟限制。

---

## 🌐 云服务器上部署了，但不知道怎么用浏览器访问？

详见 → [云服务器 Web 界面访问指南](deploy-webui-cloud.md)

涵盖：直接部署和 Docker 两种方式的启动与访问、安全组/防火墙配置、常见问题排查、Nginx 反向代理（可选）。

---

**祝部署顺利！🎉**
