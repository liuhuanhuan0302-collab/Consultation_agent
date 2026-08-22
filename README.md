# 咨询诊断 Agent

商业版首版实现：外部客户完成企业信息与 68 题诊断问卷，后端规则评分，调用 DeepSeek 生成诊断报告，并提供网页版报告、PDF 导出和自建后台。

## 技术栈

- 后端：FastAPI、SQLAlchemy、MySQL/RDS 兼容，本地默认 SQLite
- 前端：Vue 3、Vite、TypeScript
- 模型：DeepSeek API，后端统一封装，前端不暴露密钥
- PDF：报告内容同源导出，本地使用服务端 PDF 兜底渲染

## 后端目录结构

后端按长期维护和检索习惯拆分（分层规则详见 `backend/ARCHITECTURE.md`）：

- `backend/app/api/v1/endpoints/`：接口入口，`public.py`（公开客户端点）、`health.py`、`admin/`（管理端点按域拆分：auth / users / leads / questions / cases / channels / reports / analytics / api_gateway）
- `backend/app/api/v1/router.py`：v1 API 聚合入口，后续新增 v2 时不影响旧接口
- `backend/app/service/`：业务编排层，如答卷提交、评分、报告生成、企业情报检索、报告队列、PDF、邮件、线索管理
- `backend/app/repositories/`：数据访问层，如线索、答卷、渠道、用户、题库、案例查询
- `backend/app/models/`：ORM 实体按域拆分（user / lead / questionnaire / report / case / channel / gateway / audit）
- `backend/app/schemas/`：Pydantic 入参和出参类型，按域拆分
- `backend/app/core/`：环境配置与安全原语（`config.py`、`security.py`）
- `backend/app/db/`：数据库连接、会话与初始化（`database.py`、`init_db.py`）
- `backend/app/utils/`：通用工具，如鉴权、安全、日志、二维码、请求工具
- `backend/app/data/`：版本化的静态应用数据（正式题库 JSON）
- `backend/app/seed.py`：初始化默认管理员、正式题库、案例和渠道
- `backend/app/config.py` / `backend/app/database.py`：仅为兼容再导出，新代码使用 `app.core.config` / `app.db.database`

企业情报证据规则：搜索提供商返回的引用是唯一可信来源集合；模型输出的来源 URL 必须与可信集合精确匹配才会保留，事实类栏目必须引用真实来源序号，无法证明证据时检索/生成走失败关闭路径（退避重试 → 人工审核），不会生成或发送无证据的客户报告。

暂时没有把所有接口改成统一 `{ code, message, data }` 返回格式，因为前端已经依赖当前接口结构；如果后续要统一返回，建议单独做一次前后端联动改造。

## 本地启动

后端：

```powershell
cd backend
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

报告队列：`ENVIRONMENT=development` 时报告队列消费者会在 API 进程内自动启动（报告生成与邮件发送在后台持续消费队列）。如需按生产方式单独运行消费者进程：

```powershell
cd backend
.\\.venv\\Scripts\\Activate.ps1
python scripts\\report_worker.py
```

两者可以并存——任务领取通过条件 UPDATE 原子完成，不会重复处理。

诊断系统前端：

```powershell
cd frontend
npm install
npm run dev
```

官网前端（另开一个终端）：

```powershell
cd official-website
npm install
npm run dev -- --port 5174
```

访问：

- 本地官网：http://localhost:5174
- 本地诊断系统：http://localhost:5173
- 本地后台：http://localhost:5173/admin
- 默认账号：admin@example.com
- 默认密码：Admin123!

## 生产配置

将 `backend/.env` 的 `DATABASE_URL` 改为阿里云 MySQL/RDS 连接，例如：

```env
DATABASE_URL=mysql+pymysql://user:password@host:3306/consultation_agent?charset=utf8mb4
DEEPSEEK_API_KEY=你的 DeepSeek Key
SECRET_KEY=生产随机密钥
PUBLIC_WEB_BASE_URL=https://你的域名/diagnosis
CORS_ORIGINS=https://你的域名
```

Docker 部署时填写根目录 `.env.production`，然后运行：

```powershell
docker compose up -d --build
```

后端容器启动时会先执行 `alembic upgrade head`，迁移成功后才启动 API。生产空库会由 Alembic 创建完整结构；没有版本记录的完整旧库会自动建立基线后执行增量迁移。部署前仍应先备份数据库。

生产环境统一入口：

- 官网：`https://你的域名/`
- 诊断系统：`https://你的域名/diagnosis/`
- 后台：`https://你的域名/diagnosis/admin`

服务器若已由系统 Nginx 占用 80 端口，Docker 前端会监听 `127.0.0.1:8080`，再由 Nginx 反向代理到该地址；配置模板位于 `deploy/nginx/consultation-agent.conf`。

## 内容维护

- 当前内置 10 个模块、68 道示例题；总分由启用模块的满分动态求和（当前题库数据合计 270 分），`scoring.py` 中的 260 仅为兼容常量。
- 正式上线前，在后台替换为你们提供的正式 68 题源表。
- 当前内置少量示例案例，正式上线前替换为你们审核过的真实案例。

导入正式题库：

```powershell
cd E:\Consultation_agent\backend
..\.venv\Scripts\python.exe scripts\import_questionnaire.py "E:\飞书\智简组织转型准备度诊断问卷.xlsx"
```

注意：Excel 中题目按 0-4 作答；模块得分 = 模块实际得分 / 模块题目总分 × 模块满分（四舍五入），总分等级按得分率换算（≤25% 高风险 / ≤50% 较弱 / ≤75% 良好 / >75% 优秀）。

## 测试

```powershell
cd backend
pytest
```
