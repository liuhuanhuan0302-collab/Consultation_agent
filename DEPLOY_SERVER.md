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
DEEPSEEK_API_KEY=你的DeepSeek密钥
PUBLIC_WEB_BASE_URL=http://你的服务器公网IP
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

第一次启动后初始化数据库：

```bash
docker compose exec backend python scripts/init_db.py
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

## 6. 访问测试

浏览器打开：

```text
http://你的服务器公网IP
```

后台：

```text
http://你的服务器公网IP/admin
```

接口健康检查：

```bash
curl http://127.0.0.1/api/health
```

公网测试：

```bash
curl http://你的服务器公网IP/api/health
```

## 7. 二维码地址

没有域名时，二维码会使用：

```env
PUBLIC_WEB_BASE_URL=http://你的服务器公网IP
```

之后如果换域名，需要改成：

```env
PUBLIC_WEB_BASE_URL=https://你的域名
CORS_ORIGINS=https://你的域名
```

然后重启：

```bash
docker compose up -d
```

旧二维码不会自动变，需要重新生成。

## 8. 重要提醒

安全组只开放：

- 22
- 80
- 443

不要开放：

- 3306
- 8000
- 5173

因为 MySQL、后端、worker 都在 Docker 内网里。
