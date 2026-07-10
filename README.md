# 咨询诊断 Agent

商业版首版实现：外部客户完成企业信息与 68 题诊断问卷，后端规则评分，调用 DeepSeek 生成诊断报告，并提供网页版报告、PDF 导出和自建后台。

## 技术栈

- 后端：FastAPI、SQLAlchemy、MySQL/RDS 兼容，本地默认 SQLite
- 前端：Vue 3、Vite、TypeScript
- 模型：DeepSeek API，后端统一封装，前端不暴露密钥
- PDF：报告内容同源导出，本地使用服务端 PDF 兜底渲染

## 后端目录结构

后端按长期维护和检索习惯拆分：

- `backend/app/api/v1/endpoints/`：接口入口，当前按 `public.py`、`admin.py`、`health.py` 拆分
- `backend/app/api/v1/router.py`：v1 API 聚合入口，后续新增 v2 时不影响旧接口
- `backend/app/schemas/`：Pydantic 入参和出参类型
- `backend/app/service/`：核心业务逻辑，如评分、报告生成、PDF、答卷处理
- `backend/app/repositories/`：数据访问层，如线索、渠道、用户、题库、案例查询
- `backend/app/utils/`：通用工具，如鉴权、安全、日志、二维码、请求工具
- `backend/app/models.py`：数据库模型
- `backend/app/database.py`：数据库连接和轻量 schema 升级
- `backend/app/seed.py`：初始化默认管理员、正式题库、案例和渠道

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

前端：

```powershell
cd frontend
npm install
npm run dev
```

访问：

- 客户端：http://localhost:5173
- 后台：http://localhost:5173/admin
- 默认账号：admin@example.com
- 默认密码：Admin123!

## 生产配置

将 `backend/.env` 的 `DATABASE_URL` 改为阿里云 MySQL/RDS 连接，例如：

```env
DATABASE_URL=mysql+pymysql://user:password@host:3306/consultation_agent?charset=utf8mb4
DEEPSEEK_API_KEY=你的 DeepSeek Key
SECRET_KEY=生产随机密钥
PUBLIC_WEB_BASE_URL=https://你的域名
CORS_ORIGINS=https://你的域名
```

Docker 部署时填写根目录 `.env.production`，然后运行：

```powershell
docker compose up -d --build
```

后端镜像已内置正式 68 题题库，生产空库首次启动会自动创建正式题库、默认渠道和默认管理员。

## 内容维护

- 当前内置 10 个模块、68 道示例题，总分规则按 260 分设计。
- 正式上线前，在后台替换为你们提供的正式 68 题源表。
- 当前内置少量示例案例，正式上线前替换为你们审核过的真实案例。

导入正式题库：

```powershell
cd E:\Consultation_agent\backend
..\.venv\Scripts\python.exe scripts\import_questionnaire.py "E:\飞书\智简组织转型准备度诊断问卷.xlsx"
```

注意：Excel 中题目按 0-4 作答，但模块汇总满分与“总分 260”存在不一致；系统按 PRD 的 260 总分口径做模块权重归一，确保全满分结果为 260。

## 测试

```powershell
cd backend
pytest
```
