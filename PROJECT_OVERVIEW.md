# 咨询诊断 Agent — 项目全貌文档

> 用于让 GPT / Codex / 新成员快速了解项目全貌，包含架构、数据流、文件结构、API 清单、评分逻辑。
> 本文档按 2026-08-23 的实际代码同步；分层规则以 `backend/ARCHITECTURE.md` 为准。

---

## 一、项目简介

AI 原生企业转型就绪度诊断工具。客户扫码进入 → 填写企业信息 → 完成 68 题问卷 → 系统评分 → 联网检索企业公开情报（带证据校验）→ DeepSeek 生成诊断报告 → 邮件发送 PDF。后台可管理题库、案例、渠道、线索、用户、API 网关配置。

**技术栈**：FastAPI + SQLAlchemy（后端） / Vue 3 + Vite + Chart.js（前端） / DeepSeek API（AI 报告与企业情报） / 外部搜索或 DeepSeek 原生联网搜索（企业情报） / 服务端渲染 PDF（浏览器渲染 + 兜底）

---

## 二、文件目录

```
E:\Consultation_agent\
├── .env.production / .env.staging.example   # 环境变量模板
├── docker-compose.yml           # Docker 编排
├── README.md / PROJECT_OVERVIEW.md
├── docs/coordination/           # 多智能体协调协议（PROTOCOL / SPEC / STATE / OWNERSHIP）
│
├── backend/
│   ├── alembic.ini              # Alembic 迁移配置
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py              # FastAPI 入口：CORS、限流、异常处理、启动校验；
│   │   │                        #   development 环境在进程内启动报告队列 worker
│   │   ├── config.py            # 兼容再导出 → app.core.config
│   │   ├── database.py          # 兼容再导出 → app.db
│   │   ├── seed.py              # 初始数据：管理员、正式题库、案例、渠道
│   │   ├── api/v1/
│   │   │   ├── router.py        # 聚合 health + public + admin 三个路由
│   │   │   └── endpoints/
│   │   │       ├── health.py    # GET /api/health
│   │   │       ├── public.py    # 11 个公开端点（会话/线索/答卷/报告/二维码）
│   │   │       └── admin/       # 管理端点按域拆分
│   │   │           ├── _shared.py      # 后台共用限流器
│   │   │           ├── auth.py         # 登录/登出/me/改密
│   │   │           ├── users.py        # 用户管理
│   │   │           ├── leads.py        # 线索管理（列表/导出/详情/邮箱/删除/检索）
│   │   │           ├── questions.py    # 题库与模块管理
│   │   │           ├── cases.py        # 案例管理
│   │   │           ├── channels.py     # 渠道管理
│   │   │           ├── reports.py      # 报告详情
│   │   │           ├── analytics.py    # 统计看板与埋点
│   │   │           └── api_gateway.py  # 搜索/LLM 网关配置与连通性测试
│   │   ├── schemas/             # Pydantic 契约，按域拆分（auth/lead/questionnaire/report/...）
│   │   ├── models/              # ORM 实体，按域拆分（user/lead/questionnaire/report/case/channel/gateway/audit）
│   │   ├── repositories/        # 数据访问层
│   │   │   ├── consult_repo.py      # Lead / Submission / Report / 统计 查询与级联删除
│   │   │   ├── lead_repo.py         # 线索详情/投递/队列位置/导出审计
│   │   │   ├── submission_repo.py   # 答卷锁读/答案写入/报告创建
│   │   │   ├── questionnaire_repo.py# 模块/题目 查询
│   │   │   ├── case_repo.py         # 案例 查询
│   │   │   ├── user_repo.py         # 用户 查询
│   │   │   └── qr_code_repo.py      # 渠道 查询
│   │   ├── service/             # 业务编排层
│   │   │   ├── scoring.py           # 评分引擎（纯函数）
│   │   │   ├── diagnosis.py         # 评分编排、线索等级判定
│   │   │   ├── submission_service.py# 问卷提交工作流与事务边界
│   │   │   ├── company_research.py  # 企业情报：搜索 + DeepSeek 提炼 + 证据校验
│   │   │   ├── reporting.py         # 结构化报告生成（模板校验重试）
│   │   │   ├── report_analysis.py   # 报告证据数据组装
│   │   │   ├── report_content.py    # 报告内容兼容清洗
│   │   │   ├── report_queue.py      # 报告投递队列（原子认领、退避重试）
│   │   │   ├── pdf_service.py       # PDF 渲染与校验（浏览器渲染 + 兜底）
│   │   │   ├── email_service.py     # SMTP 发送
│   │   │   ├── lead_service.py      # 线索管理工作流
│   │   │   ├── lead_export_service.py # Word 档案导出
│   │   │   └── api_gateway_service.py # 搜索/LLM 网关配置与密钥加密
│   │   ├── core/                # config.py、security.py
│   │   ├── db/                  # database.py（engine/session）、init_db.py
│   │   ├── utils/               # auth / security / exceptions / logging_utils / qr_code / request / time_utils
│   │   └── data/
│   │       └── official_questionnaire.json  # 正式题库（10 模块 68 题）
│   ├── migrations/versions/     # Alembic：initial、normalize_legacy_schema、add_lead_city、default_search_to_deepseek
│   ├── scripts/                 # report_worker.py、import_questionnaire.py、migrate_database.py 等
│   └── tests/                   # 23 个测试文件（角色矩阵、企业情报证据、答卷服务、投递闸门等）
│
├── frontend/
│   ├── Caddyfile                # 静态托管 + /api/ 反代
│   ├── index.html / package.json / vite.config.ts
│   └── src/
│       ├── App.vue              # 单文件 SPA（全部视图逻辑）
│       ├── api.ts               # fetch 封装
│       ├── types.ts             # TypeScript 类型定义
│       ├── styles.css
│       ├── components/ReportCharts.vue  # Chart.js 柱状图 + 雷达图
│       ├── composables/         # useAdmin / useQuestionnaire / useReportView / feedback
│       └── utils/               # appPaths / format / reportHtml
│
└── official-website/            # 官网（原生 JS，config.js + founder.html 等页面）
```

---

## 三、架构分层

```
HTTP 请求
  → main.py（CORS / 限流 / 异常处理）
    → api/v1/endpoints/（路由层：参数校验、鉴权、HTTP 映射、响应序列化）
      → service/（业务编排、事务边界、外部集成）
        → repositories/（SQLAlchemy 查询与持久化）
          → models/（ORM 实体）
```

**原则**：

- 端点不写业务编排与复杂查询，只做 HTTP 相关处理。
- service 不依赖 FastAPI（不导入/抛出 HTTPException），领域错误以普通异常抛出，由端点层映射为 HTTP 状态码。
- 所有 DB 查询经 repository。
- `app/config.py`、`app/database.py` 仅为兼容再导出；`app/models/__init__.py`、`app/schemas/__init__.py` 保留兼容导出。

---

## 四、数据库模型（按域文件拆分）

| 域 | 文件 | 模型 |
|---|---|---|
| 用户与角色 | `models/user.py` | `User`（admin/operator/sales/consultant，pbkdf2_sha256 密码）、`Role` |
| 线索 | `models/lead.py` | `CompanyLead`（公司信息、联系方式、来源、等级、诉求摘要） |
| 问卷 | `models/questionnaire.py` | `QuestionModule`、`Question`、`DiagnosisSubmission`、`QuestionAnswer`、`DimensionScore`、`SubmissionStatus` |
| 报告与投递 | `models/report.py` | `Report`（HTML + summary_json + company_research_json + 生成/检索/PDF 状态字段）、`ReportDeliveryJob`（队列任务）、`Recommendation`、`AiConversationMessage`、`ReportTemplate`、各状态枚举 |
| 案例 | `models/case.py` | `CaseStudy` |
| 渠道 | `models/channel.py` | `ChannelSource` |
| 网关配置 | `models/gateway.py` | `GatewayApiConfig`（搜索/LLM 配置，密钥加密存储） |
| 审计与埋点 | `models/audit.py` | `TrackingEvent`、`OperationLog`、`ExportLog` |

---

## 五、内置题库（10 个模块 68 题，满分随题库动态计算）

| 编码 | 名称 | 题数 | 模块满分 |
|---|---|---|---|
| M01 | 一心：以用户/客户为中心 | 7 | 28 |
| M02 | 三简①：简化业务 | 7 | 28 |
| M03 | 三简②：简练组织 | 7 | 26 |
| M04 | 三简③：简单团队 | 7 | 28 |
| M05 | 五化①：流程化 | 6 | 24 |
| M06 | 五化②：自动化 | 6 | 24 |
| M07 | 五化③：数字化 | 7 | 28 |
| M08 | 五化④：智能化 | 7 | 28 |
| M09 | 五化⑤：生态化 | 7 | 28 |
| M10 | 五差就绪度综合诊断 | 7 | 28 |

> 满分由启用模块的 `max_score` 动态求和（当前数据合计 270），不写死 260；`scoring.py` 的 `TOTAL_MAX_SCORE = 260` 仅为兼容常量。

---

## 六、评分算法（`service/scoring.py`，纯函数）

```python
# 每模块得分 = (该模块实际得分 / 该模块题目总分) × 模块满分，四舍五入
# 总分 = 参与答题的各模块得分之和，满分随实际题库动态计算
# 总分等级按得分率换算（兼容历史阈值）：
rate <= 0.25 → 高风险；rate <= 0.50 → 较弱；rate <= 0.75 → 良好；rate > 0.75 → 优秀
# 维度等级：
<0.25 → 高风险；<0.50 → 较弱；<0.75 → 良好；>=0.75 → 优秀
```

线索等级（`service/diagnosis.py`）：有联系方式 + 至少 2 个维度得分率 < 0.5 → high；有联系方式 → medium；无联系方式 → low。诉求摘要优先取客户填写的 `ai_focus`，缺省时按低分维度生成。

---

## 七、API 清单（43 个端点，按实际路由同步）

### 公开端点（无需鉴权）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查（含数据库探测） |
| POST | `/api/public/sessions` | 创建匿名会话（20/小时） |
| POST | `/api/public/events` | 记录用户行为埋点 |
| GET | `/api/public/questions` | 获取活跃模块及题目 |
| POST | `/api/public/leads` | 创建/更新线索，生成答卷记录（10/小时，同邮箱限 3/小时） |
| PUT | `/api/public/submissions/{id}/draft` | 保存草稿答案 |
| POST | `/api/public/submissions/{id}/submit` | 提交问卷 → 评分 → 入队（3/小时，IP+会话） |
| GET | `/api/public/submissions/{id}/report` | 查询本次提交的报告状态 |
| GET | `/api/public/sessions/report` | 按会话恢复最近报告（兼容旧版本） |
| GET | `/api/public/reports/{token}` | 公开查看报告（含 score/dimensions） |
| POST | `/api/public/reports/{token}/regenerate` | 本地开发提示词测试（仅 development + 回环地址，6/小时） |
| GET | `/api/public/channels/{code}/qr` | 获取渠道二维码图片 |

> PDF 不提供公开下载端点：报告 PDF 由队列 worker 生成后邮件发送。

### 管理端点（Bearer 或 HttpOnly Cookie，均需 JWT）

| 方法 | 路径 | 角色守卫 | 说明 |
|---|---|---|---|
| POST | `/api/admin/auth/login` | 无（限流 5/分钟） | 登录，写入 HttpOnly Cookie |
| POST | `/api/admin/auth/logout` | 无 | 登出 |
| GET | `/api/admin/me` | 登录用户 | 当前用户信息 |
| POST | `/api/admin/auth/change-password` | 登录用户 | 修改自己的密码 |
| POST | `/api/admin/users` | AdminOnly | 创建后台用户 |
| GET | `/api/admin/users` | AdminOnly | 用户列表 |
| GET | `/api/admin/leads` | LeadViewer | 线索列表（行业/等级/渠道筛选） |
| GET | `/api/admin/leads/export` | LeadExporter | 导出线索 CSV |
| PUT | `/api/admin/leads/{id}/diagnostic-email` | AdminOnly | 更正诊断邮箱并重新入队 |
| GET | `/api/admin/leads/{id}/export/word` | LeadExporter | 导出客户 Word 档案 |
| GET | `/api/admin/leads/{id}` | LeadViewer | 线索详情（含报告/投递状态） |
| DELETE | `/api/admin/leads/{id}` | AdminOnly | 删除线索及全部关联数据 |
| POST | `/api/admin/leads/{id}/research` | AdminOnly | 手动触发企业情报检索（异步，force 重新生成） |
| GET | `/api/admin/reports/{id}` | ReportViewer | 报告详情（HTML + summary + 顾问消息） |
| GET | `/api/admin/questions` | LeadViewer | 题库列表 |
| POST | `/api/admin/modules` | ContentManager | 新增/更新模块 |
| DELETE | `/api/admin/modules/{id}` | ContentManager | 归档模块 |
| POST | `/api/admin/questions` | ContentManager | 新增/更新题目 |
| DELETE | `/api/admin/questions/{id}` | ContentManager | 归档题目 |
| GET | `/api/admin/cases` | LeadViewer | 案例列表 |
| POST | `/api/admin/cases` | ContentManager | 新增案例 |
| GET | `/api/admin/channels` | LeadViewer | 渠道列表 |
| POST | `/api/admin/channels` | ContentManager | 新增/更新渠道 |
| DELETE | `/api/admin/channels/{id}` | ContentManager | 删除渠道 |
| GET | `/api/admin/analytics/summary` | LeadViewer | 统计看板 |
| GET | `/api/admin/events` | LeadViewer | 埋点事件列表 |
| GET | `/api/admin/api-gateway` | AdminOnly | 网关配置 |
| PUT | `/api/admin/api-gateway/search` | AdminOnly | 更新搜索网关 |
| PUT | `/api/admin/api-gateway/llm` | AdminOnly | 更新 LLM 网关 |
| POST | `/api/admin/api-gateway/test-search` | AdminOnly | 搜索连通性测试 |
| POST | `/api/admin/api-gateway/test-llm` | AdminOnly | LLM 连通性测试 |

### 角色守卫（`utils/auth.py`）

| 守卫 | 允许角色 |
|---|---|
| `AdminOnly` | admin |
| `ContentManager` | admin, operator |
| `LeadViewer` | admin, operator, sales, consultant |
| `LeadExporter` | admin, operator, sales |
| `ReportViewer` | admin, operator, sales, consultant |

认证：Bearer 头或 HttpOnly 会话 Cookie 任一即可；缺失/无效/过期/禁用/畸形 sub → 401；角色不在允许列表 → 403。`tests/test_authorization_matrix.py` 用真实路由覆盖全部守卫与两种认证路径。

---

## 八、核心调用链

### 问卷提交（`public.py` → `submission_service.py`）

```
POST /submit（端点：会话归属、限流、HTTP 映射、后台任务调度）
  → submission_service.submit_questionnaire（事务边界）
      行级锁读(FOR UPDATE) → 完整性校验 → 队列容量检查
      → 保存答案 → 规则评分 → 创建 pending 报告 → 入队 → 提交
      （MySQL 死锁 1205/1213 自动重试 3 次）
  → 后台任务 process_job_then_next
  → report_queue.process_report_delivery_job
      → company_research.research_company（证据失败 → 退避重试 → 人工审核）
      → reporting.generate_report_content（信号量限并发，模板校验最多 3 次）
      → pdf_service.render_report_pdf_bytes（+校验）
      → email_service.send_report_pdf_email
```

服务异常 → HTTP 映射在端点层：404（不存在）/ 409（已提交）/ 422（题目不完整）/ 503（队列满）。

### 线索管理（`admin/leads.py` → `lead_service.py`）

```
端点（角色守卫）→ lead_service.*
  → lead_repo（详情/投递/队列位置/顾问消息/导出审计）
  → consult_repo（列表、级联删除）
  → lead_export_service（Word 档案）
  → company_research（后台异步检索）
  → report_queue（更正邮箱后重新入队）
```

---

## 九、企业情报证据规则（`service/company_research.py`）

- **可信来源集合**：仅搜索提供商本次返回的机器可读引用——外部搜索（bocha / serpapi / custom）信任 `search_company_web()` 的结果；deepseek 原生搜索信任 Responses API 的 `sources` / `citations` / `annotations` / `web_search_call` 结果。
- **模型来源不直接可信**：模型输出的 `sources` 条目必须经 URL 规范化（仅 http/https、必须带 host、拒绝凭据）后与可信集合精确匹配才会保留；未匹配的 URL 不落库；`source_refs` 同步重排。
- **结构校验**：`sources` 非空且每条含 title+url；`source_refs` 必须存在、键限于结构化字段；事实栏（公司介绍/营收规模/产品与服务/行业特点/发展现状）必须有非空、去重、范围内的整数序号；标记"暂未检索到可靠公开信息"的栏目不得伪造引用；分析栏（挑战/AI 机会/综合分析）不强制引用，展示时标明为 AI 分析而非已核实事实。
- **缓存复用**：仅 `evidence_version == 1` 且通过校验的历史情报可复用，否则重新检索。
- **展示**：HTML 报告与 Word 导出均按栏目标注具体"来源 N"编号，并在文末给出去重来源列表；内容经转义后展示。

### 失败关闭规则

1. 检索/校验失败 → `research_status = failed`，原因写入 `generation_error`；投递任务按 `2 × attempts` 分钟退避重试。
2. 重试耗尽（`max_attempts`）→ 报告 `failed`、`research_status = review` → 人工审核；不生成、不发送无证据的最终报告。
3. 报告生成：固定六段模板完整性校验，最多带反馈重试 3 次；仍不完整 → `failed` 转人工审核（不再用模板报告直接发送）。
4. PDF 投递闸门：必须包含全部客户章节，拒绝损坏/过小 PDF。
5. 公开接口失败只返回通用提示文案，内部错误详情仅后台可见。

---

## 十、安全措施

- 密码：`pbkdf2_sha256` 哈希
- JWT：HS256 签名，默认 720 分钟过期；`SECRET_KEY` 启动时校验（禁止默认值）
- 生产环境禁止 SQLite（启动时检查）
- staging 环境必须连接名称以 `_test` / `_staging` 结尾的独立数据库，且必须配置 `SMTP_RECIPIENT_ALLOWLIST`（settings 加载时强制）
- 网关 API Key 加密存储（Fernet）；网关自定义地址但 Key 不可解密时禁止把 .env 密钥发往该地址
- 限流（slowapi）：登录 5/分钟、会话 20/小时、线索 10/小时、提交 3/小时（IP+会话）、本地重生成 6/小时
- 公开报告失败提示统一文案，不泄露 SMTP/外部 API/文件路径等内部细节
- CSV 导出对公式前缀单元格强制转文本（防公式注入）；Word/HTML 输出转义
- 匿名会话越权防护：答卷/报告读取必须匹配 `X-Session-Token`
- 报告队列原子认领（条件 UPDATE），多 worker 并发不会重复生成/重复发送
- 队列容量上限（`max_pending_report_jobs`，默认 100）与同邮箱线索频控（默认 3/小时）

---

## 十一、部署方式

```bash
# 1. 配置环境变量（.env.production）
# 2. 启动
docker compose up -d --build
```

后端容器启动时先执行 `alembic upgrade head`，迁移成功后才启动 API；生产空库由 Alembic 创建完整结构。报告队列在生产环境作为独立 worker 进程运行（`scripts/report_worker.py`），development 环境在 API 进程内自动启动消费者。

> 本文档未重新执行 Docker 部署验证；部署细节以 `DEPLOY_SERVER.md` 与 `docker-compose.yml` 当前内容为准。

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
