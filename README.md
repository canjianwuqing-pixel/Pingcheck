# Pingcheck

Pingcheck 是一个简洁的网络检测管理平台。本仓库当前完成第二阶段：在可部署基础框架和单管理员登录之上，提供 TCP/UDP 监控入口管理，**尚未实现实际网络检测**。

## 已实现

- FastAPI 后端和 Vue 3 / Vite 响应式中文管理界面
- 单管理员密码登录、登录状态检查和退出
- PBKDF2-SHA256 管理密码哈希，配置来自 `.env`
- SQLite 服务端会话，HttpOnly / SameSite Cookie
- SQLite 数据卷持久化，重启容器不会丢失数据
- 后端健康检查：`GET /api/health`
- TCP/UDP 入口的添加、编辑、删除、启用和暂停
- 支持 IPv4 / IPv6，同一 IP 可配置不同端口和协议
- 检测历史、Telegram 通知的数据库表和代码模块占位
- Docker Compose 一键构建和启动

## 项目结构

```text
Pingcheck/
├─ backend/
│  ├─ app/
│  │  ├─ api/          # 登录、退出、健康检查接口
│  │  ├─ core/         # 配置与密码哈希
│  │  └─ modules/      # 入口管理与后续功能模块
│  ├─ scripts/         # 密码哈希工具
│  └─ tests/           # 后端基础测试
├─ frontend/
│  └─ src/             # Vue 管理页面
├─ docker-compose.yml
└─ .env.example
```

## Docker Compose 部署

1. 复制环境变量示例：

   ```bash
   cp .env.example .env
   ```

   Windows PowerShell：

   ```powershell
   Copy-Item .env.example .env
   ```

2. 生成新的管理密码哈希：

   ```bash
   python backend/scripts/hash_password.py
   ```

   将输出完整复制到 `.env` 的 `ADMIN_PASSWORD_HASH`。示例配置对应密码 `admin123`，仅供首次体验，正式使用前必须替换。同时把 `SESSION_SECRET` 改成随机长字符串。

3. 构建并启动：

   ```bash
   docker compose up -d --build
   ```

4. 浏览器访问 `http://localhost:8080`。可通过 `.env` 中的 `APP_PORT` 修改宿主机端口。

停止服务：

```bash
docker compose down
```

默认不会删除名为 `pingcheck_data` 的数据卷；只有显式执行 `docker compose down -v` 才会删除数据。

## 本地开发

后端（Python 3.11+）：

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

请先在仓库根目录准备 `.env`。本地运行时 `.env.example` 中的 `DATABASE_PATH=data/pingcheck.db` 会在 `backend/data/` 下创建数据库。

前端（Node.js 22+）：

```bash
cd frontend
npm install
npm run dev
```

Vite 开发服务器地址为 `http://localhost:5173`，并会把 `/api` 代理到本机 `8000` 端口。

## 测试与检查

```bash
cd backend
pytest -q

cd ../frontend
npm run build

cd ..
docker compose config --quiet
```

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/health` | 服务与数据库健康检查 |
| `POST` | `/api/auth/login` | 使用管理密码登录 |
| `GET` | `/api/auth/me` | 检查当前登录会话 |
| `POST` | `/api/auth/logout` | 注销当前会话 |
| `GET` | `/api/targets` | 获取监控入口列表 |
| `POST` | `/api/targets` | 添加监控入口 |
| `GET` | `/api/targets/{id}` | 获取单个入口 |
| `PUT` | `/api/targets/{id}` | 编辑监控入口 |
| `PATCH` | `/api/targets/{id}/enabled` | 启用或暂停入口 |
| `DELETE` | `/api/targets/{id}` | 删除监控入口 |

开发环境可访问 FastAPI 自动文档：`http://localhost:8000/docs`。

## 第二阶段边界

本阶段只实现入口管理，没有实现 TCP/UDP 探测、定时任务、检测记录写入或 Telegram 发信。检测历史和通知的 SQLite 表及 `backend/app/modules/` 目录仍保留扩展边界，未提前引入任务队列或分布式组件。
