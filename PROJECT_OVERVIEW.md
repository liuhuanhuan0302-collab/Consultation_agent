# 咨询诊断 Agent — 项目全貌文档

> 用于让 GPT / Codex / 新成员快速了解项目全貌，包含架构、数据流、文件结构、API 清单、评分逻辑。

---

## 一、项目简介

AI 原生企业转型就绪度诊断工具。客户扫码进入 → 填写企业信息 → 完成 68 题问卷 → 系统评分 → DeepSeek 生成诊断报告 → 网页查看 / PDF 下载。后台可管理题库、案例、渠道、线索。

**技术栈**：FastAPI + SQLAlchemy（后端） / Vue 3 + Vite + Chart.js（前端） / DeepSeek API（AI 报告） / ReportLab（PDF）

---

## 二、文件目录

```
E:\Consultation_agent\
├── .env.production              # 生产环境变量模板
├── docker-compose.yml           # Docker 编排
├── README.md
│
├── backend/
│   ├── .env.example             # 本地环境变量模板
│   ├── Dockerfile               # Python 后端镜像
│   ├── alembic.ini              # Alembic 迁移配置
│   ├── requirements.txt         # Python 依赖
│   ├── pytest.ini               # 测试配置
│   ├── app/
│   │   ├── main.py              # FastAPI 入口：CORS、日志、异常处理、启动校验
│   │   ├── config.py            # Pydantic Settings（.env 读取）
│   │   ├── database.py          # SQLAlchemy engine/session/建表
│   │   ├── models.py            # 13 个 ORM 模型（所有表定义）
│   │   ├── seed.py              # 初始数据：管理员、渠道、模块、题库、案例
│   │   ├── api/v1/
│   │   │   ├── router.py        # 汇聚 health + public + admin 三个路由
│   │   │   └── endpoints/
│   │   │       ├── health.py    # GET /api/health（含数据库探测）
│   │   │       ├── public.py    # 9 个公开端点（会话、答题、报告、二维码）
│   │   │       └── admin.py     # 15 个管理端点（登录、CRUD、统计）
│   │   ├── schemas/
│   │   │   └── __init__.py      # 24 个 Pydantic 请求/响应模型
│   │   ├── repositories/        # 数据访问层
│   │   │   ├── consult_repo.py  # Lead / Submission / Report / 统计 查询
│   │   │   ├── questionnaire_repo.py  # 模块/题目 查询
│   │   │   ├── case_repo.py     # 案例 查询
│   │   │   ├── user_repo.py     # 用户 查询
│   │   │   └── qr_code_repo.py  # 渠道 查询
│   │   ├── service/             # 业务逻辑层
│   │   │   ├── scoring.py       # 评分算法（260分制，维度归一化）
│   │   │   ├── diagnosis.py     # 答卷保存、评分编排、线索等级
│   │   │   ├── reporting.py     # DeepSeek 调用、报告生成、回退 HTML
│   │   │   └── pdf_service.py   # ReportLab PDF 生成（含图表）
│   │   ├── utils/               # 工具层
│   │   │   ├── security.py      # 密码哈希（pbkdf2_sha256）+ JWT
│   │   │   ├── auth.py          # JWT 校验 + 角色权限依赖
│   │   │   ├── exceptions.py    # 全局异常处理注册
│   │   │   ├── logging_utils.py # 操作日志 / 埋点事件写入
│   │   │   ├── qr_code.py       # 二维码 PNG 生成
│   │   │   └── request.py       # 客户端 IP 提取
│   │   └── data/
│   │       └── official_questionnaire.json  # 正式 68 题题库
│   ├── migrations/              # Alembic（初始空迁移）
│   ├── scripts/
│   │   ├── init_db.py           # 手动初始化数据库
│   │   └── import_questionnaire.py  # 从 Excel 导入题库
│   └── tests/
│       ├── test_scoring.py      # 评分算法测试（4 个）
│       └── test_report_fallback.py  # 回退报告测试（1 个）
│
└── frontend/
    ├── Dockerfile               # 多阶段构建（Node 构建 + Nginx 运行）
    ├── nginx.conf               # SPA 路由 + /api/ 反代
    ├── package.json             # 依赖（vue, chart.js, vite, typescript）
    ├── vite.config.ts           # Vite 配置，/api 代理到 8000
    ├── index.html               # 入口 HTML
    └── src/
        ├── main.ts              # Vue 应用挂载
        ├── App.vue              # 单文件 SPA（全部视图逻辑）
        ├── api.ts               # fetch 封装（15 个 API 方法）
        ├── types.ts             # TypeScript 类型定义
        ├── styles.css           # 全局样式（852 行）
        └── components/
            └── ReportCharts.vue # Chart.js 柱状图 + 雷达图组件
```

---

## 三、架构分层

```
HTTP 请求
  → main.py（CORS / 限流 / 异常处理）
    → api/v1/endpoints/（路由层：参数校验、鉴权）
      → repositories/（数据访问：仅做 DB 查询）
      → service/（业务逻辑：评分、报告、诊断）
        → models.py（ORM 模型）
```

**原则**：端点不写 SQL，service 不写 SQL，所有 DB 查询经 repository。

---

## 四、13 个数据库模型

| 表名 | 模型 | 用途 |
|---|---|---|
| `users` | User | 后台用户（admin/operator/sales/consultant），pbkdf2_sha256 密码 |
| `channel_sources` | ChannelSource | 渠道来源（二维码场景） |
| `company_leads` | CompanyLead | 客户线索（公司信息、联系方式、来源、等级） |
| `question_modules` | QuestionModule | 10 个评估模块（M01-M10） |
| `questions` | Question | 68 道题目（每题含 0-4 量表描述 option_text） |
| `diagnosis_submissions` | DiagnosisSubmission | 答题提交（总分、得分率、风险等级） |
| `question_answers` | QuestionAnswer | 每题答案（0-4 分） |
| `dimension_scores` | DimensionScore | 每模块维度得分 |
| `reports` | Report | 诊断报告（HTML + summary_json + PDF 路径） |
| `case_studies` | CaseStudy | AI 场景案例（按行业、模块、优先级） |
| `recommendations` | Recommendation | 报告与案例的关联推荐 |
| `report_templates` | ReportTemplate | 报告模板 |
| `tracking_events` | TrackingEvent | 用户行为埋点 |
| `export_logs` | ExportLog | 导出审计日志 |
| `operation_logs` | OperationLog | 后台操作审计日志 |

---

## 五、10 个评估模块（260 分制）

| 编码 | 简称 | 全称 | 题数 | 满分 |
|---|---|---|---|---|
| M01 | 一心 | 以用户/客户为中心 | 7 | 28 |
| M02 | 简化业务 | 业务聚焦与差异化 | 7 | 28 |
| M03 | 简练组织 | 组织结构与协作 | 7 | 26 |
| M04 | 简单团队 | 人效与 AI 协作能力 | 7 | 28 |
| M05 | 流程化 | 流程精简与体验 | 6 | 24 |
| M06 | 自动化 | 工作流自动化 | 6 | 24 |
| M07 | 数字化 | 数据资产与指标体系 | 7 | 26 |
| M08 | 智能化 | AI 能力嵌入业务流程 | 7 | 26 |
| M09 | 生态化 | 供应链与伙伴协同 | 7 | 24 |
| M10 | 五差就绪度 | 差异化/差距/差评/差错/差速管理 | 7 | 26 |

---

## 六、评分算法

```python
# 每模块得分 = (该模块实际得分 / 该模块题目总分) × 模块满分
weighted = Decimal(module_input_scores[id]) * Decimal(module.max_score) / Decimal(possible_score)
raw_score = int(weighted.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

# 总分为 10 个模块得分之和，满分 260
total = sum(dimension.raw_score for dimension in dimensions)

# 总分等级
<=65  → 高风险
<=130 → 较弱
<=195 → 良好
>195  → 优秀

# 维度等级
<0.25  → 高风险
<0.50  → 较弱
<0.75  → 良好
>=0.75 → 优秀
```

---

## 七、完整 API 清单（22 个端点）

### 公开端点（无需鉴权）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查（含数据库探测） |
| POST | `/api/public/sessions` | 创建匿名会话，返回 session_token |
| POST | `/api/public/events` | 记录用户行为埋点 |
| GET | `/api/public/questions` | 获取活跃模块及题目 |
| POST | `/api/public/leads` | 创建/更新线索，生成提交记录 |
| PUT | `/api/public/submissions/{id}/draft` | 保存草稿答案 |
| POST | `/api/public/submissions/{id}/submit` | 提交问卷 → 评分 → 生成报告 |
| GET | `/api/public/reports/{token}` | 公开查看报告（含 score/dimensions） |
| GET | `/api/public/reports/{token}/pdf` | 下载报告 PDF |
| GET | `/api/public/channels/{code}/qr` | 获取渠道二维码图片 |

### 管理端点（需 JWT + 角色）

| 方法 | 路径 | 角色 | 说明 |
|---|---|---|---|
| POST | `/api/admin/auth/login` | 限流 5/分钟 | 登录获取 token |
| GET | `/api/admin/me` | 登录用户 | 当前用户信息 |
| POST | `/api/admin/users` | AdminOnly | 创建后台用户 |
| GET | `/api/admin/users` | AdminOnly | 用户列表 |
| GET | `/api/admin/leads` | LeadViewer | 线索列表（支持筛选） |
| GET | `/api/admin/leads/export` | LeadExporter | 导出 CSV |
| GET | `/api/admin/reports/{id}` | ReportViewer | 查看报告详情 |
| GET | `/api/admin/questions` | LeadViewer | 题库列表 |
| POST | `/api/admin/modules` | ContentManager | 新增/更新模块 |
| POST | `/api/admin/questions` | ContentManager | 新增/更新题目 |
| GET | `/api/admin/cases` | LeadViewer | 案例列表 |
| POST | `/api/admin/cases` | ContentManager | 新增案例 |
| GET | `/api/admin/channels` | LeadViewer | 渠道列表 |
| POST | `/api/admin/channels` | ContentManager | 新增渠道 |
| GET | `/api/admin/analytics/summary` | LeadViewer | 统计看板 |
| GET | `/api/admin/events` | LeadViewer | 埋点事件列表 |

---

## 八、前端状态机

```
intro → info → questionnaire → report
                   ↑ 草稿保存 PUT /draft
                   ↓ 提交 POST /submit → 评分 + 报告

路由判断（无 Vue Router，靠路径）：
  /admin          → 后台（登录 / 管理面板）
  /report/:token  → 公开报告页
  /               → 客户端自测流程
```

---

## 九、报告数据流

```
提交问卷 → score_submission()
  → compute_scores()          # 纯函数评分
  → 写入 DimensionScore       # 持久化各维度得分
  → 写入 DiagnosisSubmission  # 总分/等级
  → generate_report_content()
    → select_recommendations()  # 按低分维度 + 行业匹配案例
    → build_report_payload()    # 组装结构化 JSON
    → call_deepseek()           # 异步调用 AI
    → render_fallback_html()    # AI 失败时用模板
  → 写入 Report (html_content + summary_json)
  → 返回 { score, report } 给前端
```

报告页渲染：前端 `score-strip` 分数卡片 → `ReportCharts` 柱状图+雷达图 → `report-html` 服务端 HTML → PDF 下载链接

---

## 十、安全措施

- 密码：`pbkdf2_sha256` 哈希
- JWT：HS256 签名，720 分钟过期
- SECRET_KEY：`.env` 必须配置，启动时校验
- 生产环境禁止 SQLite（启动时检查）
- 登录接口限流 5 次/分钟（slowapi）
- 全局异常处理（不泄露内部错误信息）
- CORS 白名单控制
- 默认管理员密码启动时弹警告

---

## 十一、部署方式

```bash
# 1. 配置环境变量
cp .env.production .env
# 编辑 .env：填入 DATABASE_URL、SECRET_KEY、DEEPSEEK_API_KEY、域名

# 2. 启动
docker compose up -d --build

# 3. 访问
# 前端 http://your-domain
# 后台 http://your-domain/admin
# 默认账号 admin@example.com / Admin123!（首次登录后立即修改）
```

---

## 十二、本地开发

```powershell
# 后端
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 前端
cd frontend
npm install
npm run dev

# 访问
# 客户端 http://localhost:5173
# 后台   http://localhost:5173/admin
# 测试   cd backend && pytest
```
