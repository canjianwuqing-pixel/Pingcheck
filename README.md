# Pingcheck

Pingcheck 是一个简洁的 TCP / UDP 端口检测管理平台，支持 Docker Compose 单入口部署、SQLite 持久化和 Telegram 异常通知。

## 已实现

- FastAPI 后端和 Vue 3 / Vite 响应式中文管理界面
- 单管理员密码登录、登录状态检查和退出
- PBKDF2-SHA256 管理密码哈希，配置来自 `.env`
- SQLite 服务端会话，HttpOnly / SameSite Cookie
- SQLite 数据卷持久化，重启容器不会丢失数据
- 后端健康检查：`GET /api/health`
- TCP/UDP 入口的添加、编辑、删除、启用和暂停
- 支持 IPv4 / IPv6，同一 IP 可配置不同端口和协议
- TCP 建立真实连接并记录结果和延迟
- UDP 区分收到响应、明确不可达和无响应；无响应显示为“未知”
- 每 60 秒自动检测已启用入口，支持手动立即检测
- TCP 连续失败 3 次标记异常，成功后自动恢复正常
- SQLite 保存 30 天检测历史并自动清理
- Web 查看最近 200 条检测历史
- Web 管理 Telegram Bot Token、Chat ID 和通知开关
- TCP 首次异常与恢复各发送一次通知，持续异常不重复提醒
- Telegram 发送失败有限重试且不影响监控任务
- Docker Compose 一键构建和启动

## 项目结构

```text
Pingcheck/
├─ backend/
│  ├─ app/
│  │  ├─ api/          # 登录、退出、健康检查接口
│  │  ├─ core/         # 配置与密码哈希
│  │  └─ modules/      # 入口、探测调度、历史和 Telegram 模块
│  ├─ scripts/         # 密码哈希工具
│  └─ tests/           # 后端基础测试
├─ frontend/
│  └─ src/             # Vue 管理页面
├─ docker-compose.yml
└─ .env.example
```

## 运行环境

Docker 构建使用以下稳定运行时，不需要在宿主机安装 Python、Node.js 或 Nginx：

| 组件 | 版本线 | 用途 |
| --- | --- | --- |
| Python | 3.12 | FastAPI 后端与后台监控任务 |
| Node.js | 22 LTS | 仅用于构建 Vue 前端 |
| Nginx | 1.30 Alpine | 提供唯一 Web 入口并代理 `/api` |

后端不会映射到宿主机端口。浏览器只访问 `${APP_PORT:-8080}`，SQLite 保存在 Docker 命名卷 `pingcheck_pingcheck_data` 中。容器重启后，后端启动时会恢复每 60 秒的监控任务。

## Docker Compose 快速部署

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

   将输出完整复制到 `.env` 的 `ADMIN_PASSWORD_HASH`，并使用单引号包住整个哈希，防止 Compose 解析其中的 `$`。示例配置对应密码 `admin123`，仅供首次体验，正式使用前必须替换。

   生成会话密钥：

   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

   将结果写入 `.env` 的 `SESSION_SECRET`。

3. 构建并启动：

   ```bash
   docker compose up -d --build
   ```

4. 浏览器访问 `http://服务器IP:8080`。可通过 `.env` 中的 `APP_PORT` 修改宿主机端口。Telegram Bot Token 和 Chat ID 登录后在“通知设置”页面填写，不要写入 `.env`。

检查状态：

```bash
docker compose ps
curl http://127.0.0.1:8080/api/health
docker compose logs --tail=100 backend
```

停止服务：

```bash
docker compose down
```

默认不会删除 Compose 创建的 `pingcheck_pingcheck_data` 数据卷；只有显式执行 `docker compose down -v` 才会删除数据。

## 国内 Ubuntu / Debian VPS

推荐使用 Docker 官方 APT 仓库安装 Docker Engine 和 Compose 插件。官方安装包名称为 `docker-ce`、`docker-ce-cli`、`containerd.io`、`docker-buildx-plugin` 和 `docker-compose-plugin`。

Ubuntu：

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
```

Debian：

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
```

如果国内网络无法访问 Docker 官方仓库或镜像站，请优先使用云厂商提供的可信镜像加速配置；不要直接执行来源不明的安装脚本。Docker 官方说明见 [Ubuntu 安装文档](https://docs.docker.com/engine/install/ubuntu/) 和 [Debian 安装文档](https://docs.docker.com/engine/install/debian/)。

安装 Docker 后的部署命令：

```bash
git clone https://github.com/canjianwuqing-pixel/Pingcheck.git && cd Pingcheck && cp .env.example .env && nano .env && sudo docker compose up -d --build
```

`nano` 保存退出后才会继续启动。首次启动前必须修改管理密码哈希和 `SESSION_SECRET`。

### 端口与防火墙

- 云安全组只需放行一个 TCP 入站端口，默认为 `8080`；不要放行后端 `8000`。
- Pingcheck 探测目标需要相应的 TCP / UDP 出站权限；Telegram 官方 API 需要 TCP 443 出站权限。
- Docker 发布的端口可能绕过部分 UFW 规则。公网 VPS 应同时配置云安全组，复杂防火墙规则应放在 `DOCKER-USER` 链中。
- 若只通过反向代理访问，可让云安全组仅允许反向代理来源访问 `APP_PORT`。

### Telegram API 地址

默认使用：

```env
TELEGRAM_API_BASE_URL=https://api.telegram.org
```

国内 VPS 无法直连时，可将其改为你自己维护或信任的 Telegram Bot API 兼容地址，然后执行：

```bash
sudo docker compose up -d --force-recreate backend
```

项目不会部署额外转发服务。Bot Token 和 Chat ID 始终在 Web 页面配置并保存到 SQLite。

## 更新

更新前先备份数据，然后执行：

```bash
git pull --ff-only
sudo docker compose build --pull
sudo docker compose up -d --remove-orphans
sudo docker compose ps
```

不要使用 `git reset --hard` 覆盖本地 `.env`，也不要执行 `docker compose down -v`。

## 备份与恢复

SQLite、Telegram 设置、会话、入口配置和检测历史都在 `pingcheck_pingcheck_data` 卷中。为获得一致备份，先短暂停止容器：

```bash
mkdir -p backups
sudo docker compose stop
sudo docker run --rm \
  -v pingcheck_pingcheck_data:/data:ro \
  -v "$PWD/backups:/backup" \
  alpine:3 sh -c 'tar czf /backup/pingcheck-data-$(date +%Y%m%d-%H%M%S).tar.gz -C /data .'
sudo docker compose start
```

恢复会覆盖当前数据。请先确认备份文件名并停止服务：

```bash
sudo docker compose down
sudo docker run --rm \
  -v pingcheck_pingcheck_data:/data \
  -v "$PWD/backups:/backup:ro" \
  alpine:3 sh -c 'find /data -mindepth 1 -maxdepth 1 -exec rm -rf {} + && tar xzf /backup/你的备份文件.tar.gz -C /data'
sudo docker compose up -d
```

恢复后用 `docker compose ps` 和 `/api/health` 检查服务，并确认入口、历史和 Telegram 设置仍在。

## 常见问题

### 页面无法访问

依次检查 `docker compose ps`、`docker compose logs frontend`、云安全组和 `APP_PORT`。外部只需要访问前端端口，后端 `8000` 不对宿主机开放。

### 后端一直不健康

运行 `docker compose logs --tail=200 backend`。常见原因是 `.env` 缺少 `ADMIN_PASSWORD_HASH`、`SESSION_SECRET` 太短，或数据卷权限异常。

### 管理密码总是错误

重新运行 `python3 backend/scripts/hash_password.py`，把完整结果用单引号包住后写入 `.env`，再执行 `docker compose up -d --force-recreate backend`。哈希中的 `$` 不能丢失。

### 重启后数据不见了

确认没有执行过 `docker compose down -v`，并检查 `docker volume ls | grep pingcheck`。固定项目名为 `pingcheck`，正常数据卷名称是 `pingcheck_pingcheck_data`。

### 出现重复检测

本项目按单个后端容器设计。不要使用 `docker compose up --scale backend=...`，并用 `docker compose ps` 确认只有一个 backend 容器。单容器内部会避免重复启动调度任务。

### UDP 一直显示“未知”

许多 UDP 服务不会响应通用探测包。“未知”只代表未收到响应，不代表端口故障或被墙，也不会增加连续失败次数或触发 Telegram 告警。

### Telegram 测试失败

确认 Bot Token、Chat ID、Bot 在目标群组中的权限和 TCP 443 出站连接。国内网络无法访问官方 API 时，只配置你信任的 `TELEGRAM_API_BASE_URL`，修改后重建 backend 容器。

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
| `POST` | `/api/targets/{id}/check` | 立即检测一个入口 |
| `GET` | `/api/targets/{id}/history` | 获取入口检测历史 |
| `DELETE` | `/api/targets/{id}` | 删除监控入口 |
| `GET` | `/api/history` | 获取最近检测历史 |
| `GET` | `/api/telegram/settings` | 获取通知设置，不返回 Token |
| `PUT` | `/api/telegram/settings` | 保存通知设置 |
| `POST` | `/api/telegram/test` | 发送测试消息 |

开发环境可访问 FastAPI 自动文档：`http://localhost:8000/docs`。

## 监控与通知规则

- TCP 使用真实连接探测。前两次连续失败显示“待确认”，连续失败达到 3 次后显示“异常”；任意一次成功会清零失败次数并恢复“正常”。
- UDP 会发送一个轻量探测包。收到任何响应视为正常；收到明确的端口不可达错误视为异常；超时无响应只能说明结果不确定，因此显示“未知”且不增加失败次数。
- 暂停入口不会参与自动或手动检测。
- 检测历史默认保留 30 天。
- Telegram 只在 TCP 首次达到异常状态时告警；持续异常不会重复发送。
- 已告警的 TCP 入口恢复连接后发送一次恢复消息。
- UDP 未知、暂停入口和删除入口不会发送通知。
- Bot Token 保存到 SQLite，但读取设置时不会通过 API 或页面明文返回。

本项目不实现 VLESS、Trojan、HY2 等代理协议，不接入代理内核。当前单进程后台任务和 SQLite 足以满足范围，未引入任务队列或分布式调度。
