# 云服务器部署步骤

适用场景：Ubuntu 22.04 服务器，暂时没有域名，先用公网 IP 部署。

## 1. 登录服务器

在本地 PowerShell 执行：

```powershell
ssh ecs-user@你的服务器公网IP
```

如果你用的是 root：

```powershell
ssh root@你的服务器公网IP
```

## 2. 安装 Docker

服务器里执行：

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable docker
sudo systemctl start docker
```

验证：

```bash
docker --version
docker compose version
```

## 3. 上传项目到服务器

推荐放到：

```bash
/opt/consultation_agent
```

如果用 Git：

```bash
sudo mkdir -p /opt/consultation_agent
sudo chown -R $USER:$USER /opt/consultation_agent
cd /opt/consultation_agent
```

然后把本地项目文件上传到这个目录。

不建议上传：

- `backend/.venv`
- `frontend/node_modules`
- `frontend/dist`
- `backend/consultation_agent.db`
- 本地测试日志和缓存

## 4. 修改生产环境变量

进入项目目录：

```bash
cd /opt/consultation_agent
nano .env.production
```

必须改这些：

```env
MYSQL_ROOT_PASSWORD=一个强密码
MYSQL_PASSWORD=另一个强密码
DATABASE_URL=mysql+pymysql://consult_agent:同MYSQL_PASSWORD@mysql:3306/consultation_agent?charset=utf8mb4
SECRET_KEY=一个随机长字符串
INITIAL_ADMIN_EMAIL=首个管理员的公司邮箱
INITIAL_ADMIN_PASSWORD=仅首次启动使用的强密码
DEEPSEEK_API_KEY=你的DeepSeek密钥
PUBLIC_WEB_BASE_URL=http://你的服务器公网IP/diagnosis
CORS_ORIGINS=http://你的服务器公网IP
```

生成 `SECRET_KEY`：

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

如果要发送邮件，还要填写：

```env
SMTP_HOST=smtp.xxx.com
SMTP_PORT=465
SMTP_USERNAME=report@xxx.com
SMTP_PASSWORD=邮箱授权码或客户端密码
SMTP_FROM_EMAIL=report@xxx.com
SMTP_FROM_NAME=AI 原生转型诊断
```

## 5. 启动服务

```bash
cd /opt/consultation_agent
docker compose up -d --build
```

后端容器会在 API 启动前自动执行 Alembic 数据库迁移。更新生产环境前请先备份数据库：

```bash
docker compose exec mysql sh -lc 'mysqldump -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' > consultation_agent_backup.sql
```

当前服务器由系统 Nginx 对外监听 80 端口，Docker 前端只监听本机 `127.0.0.1:8080`。首次部署或更新后，还需要启用项目内的 Nginx 转发配置：

```bash
sudo cp deploy/nginx/consultation-agent.conf /etc/nginx/sites-available/consultation-agent
sudo ln -sfn /etc/nginx/sites-available/consultation-agent /etc/nginx/sites-enabled/consultation-agent
sudo nginx -t
sudo systemctl reload nginx
```

查看状态：

```bash
docker compose ps
```

查看日志：

```bash
docker compose logs -f backend
docker compose logs -f report_worker
docker compose logs -f frontend
```

确认 Docker 前端在本机可访问：

```bash
curl -I http://127.0.0.1:8080/
```

## 6. 访问测试

官网：

```text
http://你的服务器公网IP
```

诊断系统：

```text
http://你的服务器公网IP/diagnosis/
```

后台：

```text
http://你的服务器公网IP/diagnosis/admin
```

接口健康检查：

```bash
curl http://127.0.0.1/api/health
```

公网测试：

```bash
curl http://你的服务器公网IP/api/health
```

## 7. 启动隔离测试环境（与生产共用 MySQL 服务）

测试环境与生产环境共用同一个 MySQL 容器，但使用独立数据库、独立数据库账号、独立管理员和独立后端数据卷。测试数据不会进入生产库。

先创建配置：

```bash
cd /opt/consultation_agent
cp .env.staging.example .env.staging
nano .env.staging
```

至少修改以下内容：

```env
STAGING_MYSQL_PASSWORD=测试库专用强密码
DATABASE_URL=mysql+pymysql://consult_agent_test:同上密码@mysql:3306/consultation_agent_test?charset=utf8mb4
SECRET_KEY=测试环境专用随机长字符串
INITIAL_ADMIN_EMAIL=测试后台管理员邮箱
INITIAL_ADMIN_PASSWORD=测试后台管理员强密码
DEEPSEEK_API_KEY=你的DeepSeek密钥
PUBLIC_WEB_BASE_URL=http://你的服务器公网IP:8081/diagnosis
CORS_ORIGINS=http://你的服务器公网IP:8081
SMTP_RECIPIENT_ALLOWLIST=你的测试收件邮箱
```

`DATABASE_URL` 的数据库名必须以 `_test` 或 `_staging` 结尾，否则测试后端会拒绝启动。测试数据库密码请只使用字母、数字和 `_ . -`，避免 URL 转义错误。

首次启动或修改测试数据库账号后执行：

```bash
docker compose --profile staging run --rm mysql_staging_init
docker compose --profile staging up -d --build backend_staging report_worker_staging frontend_staging
```

测试地址：

```text
官网：http://你的服务器公网IP:8081/
诊断：http://你的服务器公网IP:8081/diagnosis/
后台：http://你的服务器公网IP:8081/diagnosis/admin
```

阿里云安全组只允许你的办公公网 IP 访问 TCP `8081`，不要向所有来源开放测试环境。

查看测试环境状态和日志：

```bash
docker compose --profile staging ps
docker compose --profile staging logs -f backend_staging report_worker_staging
```

清空测试数据时只删除测试数据库，禁止操作生产数据库 `consultation_agent`：

```bash
docker compose exec mysql sh -lc 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS consultation_agent_test;"'
docker compose --profile staging run --rm mysql_staging_init
docker compose --profile staging restart backend_staging report_worker_staging
```

## 8. 二维码地址

域名尚未完成 ICP 备案时，请先使用服务器公网 IP：

```env
PUBLIC_WEB_BASE_URL=http://8.138.165.2/diagnosis
```

阿里云安全组需要放行 TCP 80。此阶段二维码和访问地址都使用 IP，微信内访问会显示 IP 地址提醒，这是平台行为，无法由项目代码消除。

完成 ICP 备案、域名解析生效后，再改为：

```env
PUBLIC_WEB_BASE_URL=https://youyuexinxi.com.cn/diagnosis
CORS_ORIGINS=https://youyuexinxi.com.cn
```

同时开放 TCP 443，并在系统 Nginx 中配置 HTTPS 证书；Docker 内的 Caddy 只负责站点和接口路由。

之后如果换域名，需要改成：

```env
PUBLIC_WEB_BASE_URL=https://你的域名/diagnosis
CORS_ORIGINS=https://你的域名
```

然后重启：

```bash
docker compose up -d
```

官网二维码通过 `/api/public/channels/OFFICIAL_WEBSITE/qr` 实时生成；完成上述配置并重建前端容器后，会自动使用新的地址，无需替换静态图片。

## 9. 重要提醒

当前使用 IP 临时访问时，安全组只开放：

- 22
- 80

完成备案并切回 HTTPS 域名后，再开放：

- 443

不要开放：

- 3306
- 8000
- 5173

因为 MySQL、后端、worker 都在 Docker 内网里。
