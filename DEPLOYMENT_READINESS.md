# 咨询诊断 Agent — 上线前完整检查对照报告

> 对照《AI 开发系统上线前完整检查清单》(30 节)逐项核对当前代码与部署配置。
> 核对时间:2026-08-17 | 结论符号:✅ 已具备 / ⚠️ 部分具备或需人工确认 / ❌ 缺失 / ➖ 不适用

---

## 一、服务器基础环境

| 检查项 | 状态 | 说明 |
|---|---|---|
| 购买正式云服务器 | ✅ | 阿里云 ECS,公网 IP 8.138.165.2(见 DEPLOY_SERVER.md) |
| CPU/内存/磁盘足够 | ⚠️ | 未做正式容量评估;压测脚本存在(load_test.py),上线前建议按 20-50 并发验证 |
| 操作系统版本 | ⚠️ | 文档按 Ubuntu 22.04,需确认实际版本 |
| 独立部署用户 | ⚠️ | 文档用 ecs-user,需确认非 root 操作 |
| SSH 登录 / 关闭密码登录 | ⚠️ | 文档含 SSH 步骤,未含禁用密码登录与 SSH Key 配置 |
| 安全组只开必要端口 | ⚠️ | 文档明确只开 22/80(HTTPS 后 443),未开 3306/8000 ✓ 方向正确,需核对云控制台实际规则 |
| 数据库端口不暴露公网 | ✅ | 文档明确"不要开放 3306",MySQL 在 Docker 内网 |
| 服务器时区 | ❌ | 未在部署文档/容器中设置 TZ |
| 磁盘监控 | ❌ | 无磁盘告警 |
| 重启后服务自动恢复 | ✅ | Docker `restart: unless-stopped` |

## 二、Nginx

| 检查项 | 状态 | 说明 |
|---|---|---|
| 安装 Nginx | ✅ | 系统 Nginx + 项目配置模板 `deploy/nginx/consultation-agent.conf` |
| 配置域名 / 反代 | ⚠️ | 当前 `server_name 8.138.165.2`(IP);备案后需改域名 |
| 前端 → 后端转发 | ✅ | `/` 全部反代到 `127.0.0.1:8080`(前端容器) |
| `/api` 单独转发 | ⚠️ | 目前统一走前端容器,由容器内 Caddy 再分 `/api` 到后端;单 location 可用但无独立错误处理 |
| WebSocket / SSE | ➖ | 项目无 WebSocket / 流式输出 |
| 请求超时调整 | ❌ | 无 `proxy_read_timeout`;报告生成最长可达 120s+,需调大(≥180s) |
| 上传大小限制 | ✅ | `client_max_body_size 20m`(项目暂无文件上传) |
| gzip / 静态资源 | ❌ | 未配置 gzip |
| HTTP → HTTPS 跳转 | ❌ | 当前仅 80,无 443/跳转 |
| 隐藏版本信息 | ❌ | 未配置 `server_tokens off` |
| 访问/错误日志 | ❌ | 未配置自定义 access/error log |

## 三、HTTPS / SSL 证书

| 检查项 | 状态 | 说明 |
|---|---|---|
| 购买/申请域名 | ❌ | 未备案域名(计划 youyuexinxi.com.cn) |
| DNS 解析 | ❌ | 未完成 |
| SSL 证书 / 自动续期 | ❌ | 未配置(certbot 未装) |
| 前后端全 HTTPS / Mixed Content | ❌ | 全站仍 HTTP |

## 四、后端服务

| 检查项 | 状态 | 说明 |
|---|---|---|
| 不用开发模式跑生产 | ✅ | `ENVIRONMENT=production` 时:禁 SQLite、必须 INITIAL_ADMIN_* |
| 进程管理 / 自动重启 | ✅ | Docker `restart: unless-stopped`;Dockerfile 单 worker 启动 |
| 合理 worker 数 | ✅ | 单 worker(避免多 worker 并发 seed)+ 独立 report_worker 消费队列 |
| 接口超时 / 请求大小 | ⚠️ | DeepSeek/搜索超时已调大;请求体大小未显式限制(Nginx 层有 20m) |
| CORS 白名单 | ✅ | 逗号分隔白名单,生产填正式域名 |
| 删除测试/Debug 接口 | ⚠️ | 无调试接口;但存在测试辅助(如 regenerate 入口仅开发用) |
| 生产关闭 debug | ✅ | 未开启 debug 模式 |
| `/docs`、`/redoc`、`/openapi.json` 公网开放 | ❌ | **FastAPI 默认全部开放**,未限制(上线前必须处理) |
| `/api/health` 健康检查 | ✅ | 返回 status/environment/database |

## 五、数据库

| 检查项 | 状态 | 说明 |
|---|---|---|
| 正式生产数据库 | ✅ | 阿里云 MySQL/RDS 或 Docker MySQL(docker-compose) |
| 开发/生产分离 | ⚠️ | 通过 DATABASE_URL 区分;需确保生产库独立 |
| 非 root 应用账号 | ⚠️ | docker-compose 用 env 变量创建专用用户;RDS 场景需人工确认 |
| 密码复杂度 | ⚠️ | 取决于 .env.production 实际值 |
| 端口不公网暴露 | ✅ | MySQL 仅 Docker 内网 |
| 字符编码 | ✅ | utf8mb4 |
| 连接池 | ✅ | SQLAlchemy pool_size/max_overflow/timeout 可配 |
| 索引 | ✅ | 模型关键字段带 index(created_at/status/email 等) |
| 慢查询 | ❌ | 未配置 slow query log |
| Migration | ⚠️ | Alembic 初始迁移 + 启动时轻量 schema 升级(database.py);新表结构变更建议走 migration |
| **数据库自动备份 + 恢复验证** | ❌ | **无备份机制 —— 上线前最高优先级** |

## 六、Redis

| 检查项 | 状态 | 说明 |
|---|---|---|
| 是否使用 Redis | ➖ | 项目未用 Redis(队列=DB 表,限流=slowapi 内存) |
| 提示 | ⚠️ | slowapi 限流是**进程内存态**:多 worker 或多实例时计数不共享,严格限流需引入共享存储(Redis)。当前单 worker 可接受 |

## 七、账号和权限系统

| 检查项 | 状态 | 说明 |
|---|---|---|
| 登录/退出 | ✅ | JWT(HttpOnly Cookie)+ logout |
| 密码加密 | ✅ | pbkdf2_sha256 |
| JWT 过期 | ✅ | 720 分钟可配 |
| Refresh Token | ➖ | 内部后台系统,12h 会话可接受 |
| 管理员/普通用户权限 | ✅ | 4 角色 + 接口级权限依赖(AdminOnly/LeadViewer/LeadExporter/ReportViewer/ContentManager) |
| 接口层权限校验 | ✅ | 全部 admin 接口带角色依赖 |
| 防修改 ID 越权 | ✅ | 匿名端:X-Session-Token 绑定答卷归属(submission/lead);公开报告用随机 token;后台按角色鉴权 |

## 八、API 安全

| 检查项 | 状态 | 说明 |
|---|---|---|
| 身份认证 | ✅ | admin 接口全部鉴权 |
| SQL 注入 | ✅ | SQLAlchemy 参数化查询 |
| XSS | ✅ | 报告 HTML 服务端 escape;CSV 导出防注入(escape_csv_cell) |
| CSRF | ✅ | 后台用 HttpOnly Cookie + fetch(无跨站表单场景);建议确认同源校验 |
| 文件上传 | ➖ | 无上传功能 |
| 暴力调用防护 / 限流 | ✅ | slowapi:登录 5/min、会话创建 20/hour、提交 3/hour、线索 10/hour;队列容量上限 100 |
| AI 接口限流 | ✅ | 提交限流 + 报告并发信号量 + 队列上限 |

## 九、API Key / 密钥

| 检查项 | 状态 | 说明 |
|---|---|---|
| Key 不写前端 | ✅ | 后端统一调用,前端不接触 |
| 不提交 Git | ✅ | `.gitignore` 已忽略 `.env`、`.env.*`、`.env.production`、`*.pem`、`*.key` |
| 数据库密码不写死 | ✅ | 全部走 .env |
| JWT Secret 强度 | ✅ | SECRET_KEY 启动校验(拒绝默认值);网关 Key 用 Fernet 加密存储(enc:v1:) |

## 十、AI 模型调用特别检查

| 检查项 | 状态 | 说明 |
|---|---|---|
| Key 不暴露前端 | ✅ | 全后端调用 |
| 请求超时 | ✅ | 报告 120s / 搜索 90s(已调大) |
| 最大重试次数 | ⚠️ | 后台报告生成 3 次重试;call_deepseek 本身不重试(超时即降级 fallback) |
| 最大 Token | ❌ | 未设置 max_tokens(依赖模型默认) |
| 单用户调用次数/单日额度 | ⚠️ | 有提交限流(3/hour/会话)与并发信号量;**无单日总额度/预算上限** |
| AI 调用日志 | ⚠️ | 有 ai_conversation_messages(留痕);**无 token 消耗/成本记录(缺 ai_usage_log)** |
| 失败降级 | ✅ | AI 失败自动 fallback 模板,不阻塞客户 |
| 防重复提交/连续点击 | ✅ | 前端 busy 防抖 + 后端 409 已提交拦截 + 限流 |
| 昂贵模型预算 | ❌ | 无成本上限/告警 |

## 十一、Prompt Injection / AI 安全

| 检查项 | 状态 | 说明 |
|---|---|---|
| 用户输入覆盖 System Prompt | ⚠️ | 客户自填文本(ai_focus 等)进入提示词,提示词已声明"不得编造、以数据为准";无角色切换风险 |
| Agent 工具/数据库/Shell | ➖ | 无 Agent 工具调用 |
| RAG 权限隔离 | ➖ | 无 RAG/知识库 |
| 敏感信息过滤 | ⚠️ | 报告提示词注入公司情报(公开信息);未做输出敏感信息过滤(低风险) |

## 十二、文件上传

| 检查项 | 状态 | 说明 |
|---|---|---|
| 全部 | ➖ | 系统无用户上传功能(Excel 题库导入为本地运维脚本,不对外) |

## 十三、前端

| 检查项 | 状态 | 说明 |
|---|---|---|
| production build | ✅ | Vite build 正常(官方站、诊断前端) |
| API 地址正式域名 | ⚠️ | 生产用 VITE_API_BASE_URL 构建参数;官网用 VITE_DIAGNOSIS_URL/QR 构建参数,需确认无 localhost 残留 |
| 不暴露 Key | ✅ | 无前端密钥 |
| 404/500/网络异常提示 | ⚠️ | 官网有 404.html;诊断前端有错误提示与重试;500 页无 |
| 防重复提交 | ✅ | busy 状态防抖 |
| Token 过期处理 | ✅ | 401 → 清会话跳登录 |

## 十四、日志

| 检查项 | 状态 | 说明 |
|---|---|---|
| Nginx access/error log | ❌ | 未配置(系统默认有,未定制) |
| 后端日志 | ✅ | logging 到 stderr(Docker 可收集) |
| 数据库错误日志 | ⚠️ | MySQL 默认 error log;应用层无 slow query |
| AI 调用日志 | ⚠️ | 有消息留痕,无 token/成本 |
| 用户操作日志 | ✅ | operation_logs + tracking_events + export_logs |
| **request_id** | ❌ | 每次请求无唯一 ID,排障成本高 |

## 十五、异常处理

| 检查项 | 状态 | 说明 |
|---|---|---|
| 统一异常处理 | ✅ | register_exception_handlers;不向用户泄露内部错误 |
| 404/400/401/403/429/500 | ✅ | FastAPI + 自定义处理,429 限流提示 |
| AI 超时/数据库断开 | ✅ | AI 失败降级;DB 断开由异常处理兜底(500 友好提示) |

## 十六、监控

| 检查项 | 状态 | 说明 |
|---|---|---|
| 健康检查 | ✅ | `/api/health`(含 DB 探测) |
| CPU/内存/磁盘/服务存活监控 | ❌ | 无监控与告警(依赖 Docker restart 自愈) |
| API 响应时间 / 5xx 统计 | ❌ | 无指标采集 |
| AI API 异常监控 | ⚠️ | 有日志,无告警 |

## 十七、备份

| 检查项 | 状态 | 说明 |
|---|---|---|
| **数据库每日自动备份** | ❌ | **无 —— 上线前最高优先级** |
| 配置/代码备份 | ✅ | Git 管理 + .env.example 模板 |
| 备份可恢复验证 | ❌ | 未建立恢复演练 |

## 十八、Docker

| 检查项 | 状态 | 说明 |
|---|---|---|
| Docker 化 | ✅ | mysql/backend/report_worker/frontend 四服务 |
| 安全加固 | ✅ | cap_drop ALL + no-new-privileges + 单 worker |
| 重新部署成本 | ✅ | `docker compose up -d --build` 一键 |

## 十九、服务自动恢复

| 检查项 | 状态 | 说明 |
|---|---|---|
| 自动恢复 | ✅ | Docker `restart: unless-stopped` 全服务 |

## 二十、定时任务 / 队列

| 检查项 | 状态 | 说明 |
|---|---|---|
| 异步队列 | ✅ | report_delivery_jobs(DB 表)+ report_worker 独立进程 |
| Worker 自动启动 | ✅ | Docker 服务 |
| 崩溃恢复/重试/防重复 | ✅ | 原子领取、超时回收、max_attempts=3、邮件失败不阻塞 |
| 任务超时 | ✅ | STALE_PROCESSING_TIMEOUT 15 分钟 |

## 二十一、邮件

| 检查项 | 状态 | 说明 |
|---|---|---|
| SMTP | ✅ | 163 已配置并实测发送成功 |
| 发送失败处理 | ✅ | 失败不阻塞队列,last_error 记录 |
| 防刷/频率限制 | ⚠️ | 提交限流间接限制;无独立邮件频率限制 |
| 邮件模板/日志 | ⚠️ | 单模板;投递状态在 report_delivery_jobs 可查 |

## 二十二、数据隐私

| 检查项 | 状态 | 说明 |
|---|---|---|
| 敏感字段识别 | ⚠️ | 手机号/邮箱/公司信息属敏感数据,已存明文(业务需要);建议评估是否需字段加密 |
| 密码不明文 | ✅ | pbkdf2 |
| 数据导出权限 | ✅ | 导出需 LeadExporter 角色 + export_logs 审计 |
| 删除机制 | ❌ | 无数据删除/匿名化接口 |

## 二十三、并发/压测

| 检查项 | 状态 | 说明 |
|---|---|---|
| 压测 | ✅ | PRESSURE_TEST.md + scripts/load_test.py + build_pressure_test_report.py |
| 重点观察项 | ⚠️ | 压测报告需覆盖 20-50 并发下的超时/502/DB 连接 |

## 二十四、数据库索引

| 检查项 | 状态 | 说明 |
|---|---|---|
| 索引 | ✅ | 模型关键列带 index;唯一约束齐全 |
| 慢查询优化 | ❌ | 未建立慢查询监控 |

## 二十五、上线发布机制

| 检查项 | 状态 | 说明 |
|---|---|---|
| Git 管理 | ✅ | 已有仓库与提交历史 |
| 部署方式 | ⚠️ | 手动 docker compose;无 CI/CD |
| 回滚方案 | ⚠️ | 可回滚 Git commit + 重建镜像;无镜像版本 tag 管理 |

## 二十六、环境分离

| 检查项 | 状态 | 说明 |
|---|---|---|
| 开发/生产分离 | ✅ | ENVIRONMENT 配置 + 生产校验;本地 SQLite/MySQL 分离 |
| Staging | ❌ | 无独立测试环境(可接受,按需补) |

## 二十七、版本与回滚

| 检查项 | 状态 | 说明 |
|---|---|---|
| 版本管理 | ⚠️ | Git 有;无语义化版本 tag |
| 镜像回滚 | ⚠️ | 依赖 Git 重建 |
| 数据库 migration 回滚 | ⚠️ | Alembic 可 down;初始迁移存在 |

## 二十八、生产环境配置扫描

| 检查项 | 状态 | 说明 |
|---|---|---|
| 搜索 localhost/127.0.0.1 | ⚠️ | 前端构建参数(生产域名注入);官网 .env 为本地开发配置不提交;需最终构建产物扫描确认 |
| DEBUG/test/dev 残留 | ✅ | 无 debug 模式 |

## 二十九、最容易被 AI 漏掉的 15 件事(本项目对应)

| # | 检查项 | 本项目状态 |
|---|---|---|
| 1 | .env 泄露 | ✅ 已 gitignore |
| 2 | API Key 写前端 | ✅ 无 |
| 3 | 数据库公网暴露 | ✅ 内网 |
| 4 | **没有数据库备份** | ❌ **缺失,必须补** |
| 5 | 没有 Nginx | ✅ 有(需完善) |
| 6 | 没有 HTTPS | ❌ **缺失,域名就绪后必须补** |
| 7 | 后端 Debug 开着 | ✅ 无 |
| 8 | **Swagger 公网开放** | ❌ **默认开放,必须限制** |
| 9 | 没有接口权限校验 | ✅ 有 |
| 10 | 没有限流 | ✅ 有(注意内存态) |
| 11 | 没有日志 | ⚠️ 有业务日志,无 request_id/nginx 定制 |
| 12 | 没有健康检查 | ✅ 有 |
| 13 | 没有自动重启 | ✅ Docker restart |
| 14 | **没有 AI Token 成本限制** | ❌ **缺失(缺 ai_usage_log/预算)** |
| 15 | 用户数据未隔离 | ✅ 会话绑定 |

## 三十、推荐生产架构对照

当前架构已接近推荐结构:
```
用户 → 域名 → Nginx → Frontend/Caddy → FastAPI Container → MySQL
                                        └→ report_worker → AI API(DeepSeek)
```
缺:Redis(非必需)、对象存储(无上传)、监控/告警、备份、CI/CD。

---

# 📌 上线前必做清单(按优先级)

## P0 — 上线前必须完成(安全/数据)
1. **数据库每日自动备份 + 恢复演练**(mysqldump + cron 或备份服务)
2. **关闭公网 `/docs`、`/redoc`、`/openapi.json`**(生产环境仅内网或直接禁用)
3. **HTTPS**:域名备案 → SSL 证书(certbot 自动续期)→ HTTP 跳 HTTPS
4. **Nginx 加固**:`server_tokens off`、`proxy_read_timeout 180s`、gzip、access/error 日志、`/api` 独立 location
5. **AI 用量与成本记录**:新增 `ai_usage_log`(model/tokens/cost/status),记录每次模型调用;设置单日预算或告警
6. 生产 `.env` 扫描:确认无 localhost、密码强度、SECRET_KEY 随机

## P1 — 尽快补(运维体验)
7. 生产环境限制 API 文档:仅管理员 IP 或关闭
8. Nginx/后端 request_id(排障)
9. 服务器时区 + 磁盘监控告警
10. 慢查询日志开启
11. 压测(20-50 并发)并按结果调优连接池/worker
12. 前端 500 错误友好页

## P2 — 完善(可选)
13. 敏感字段加密评估(手机号/邮箱)
14. 数据删除/匿名化接口(隐私合规)
15. 语义化版本 tag + 镜像 tag + 回滚脚本
16. CI/CD(可选)
17. 多 worker 限流共享(若引入 Redis)

---

> 说明:本报告基于当前代码与配置静态核对;P0 项中有多项(HTTPS/域名/备份)需要服务器与域名环境配合,代码层可先行准备(如文档、脚本、配置模板)。
