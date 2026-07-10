# API 接口清单（带中文标注）

> 所有接口前缀：开发环境 `http://localhost:8000`，生产环境 `https://你的域名`
> 标注格式：`METHOD 路径` — 功能说明 → 请求体/参数 → 返回体 → 鉴权要求

---

## 一、系统健康检查（1 个接口）

### `GET /api/health`
**功能**：系统健康检查，K8s / Docker 探活用  
**鉴权**：无  
**请求**：无参数  
**返回**：
```json
{
  "status": "ok",           // "ok"=正常 "degraded"=数据库不可用
  "environment": "development",
  "database": "ok"          // "ok" 或 "unavailable"
}
```
**测试命令**：
```bash
curl http://localhost:8000/api/health
```

---

## 二、公开接口 — 客户自测流程（9 个接口）

### 2.1 创建会话
### `POST /api/public/sessions`
**功能**：客户首次进入页面时创建匿名会话，返回 session_token 作为后续所有操作的凭证  
**鉴权**：无  
**请求体**：
```json
{
  "source_code": "wechat_mp",    // 渠道来源编码，可选，不传默认 "default"
  "metadata": {}                 // 额外信息，可选
}
```
**返回**：
```json
{
  "session_token": "a1b2c3d4e5f6..."   // 32位十六进制令牌，前端存入 localStorage
}
```
**测试命令**：
```bash
curl -X POST http://localhost:8000/api/public/sessions \
  -H "Content-Type: application/json" \
  -d '{"source_code": "default"}'
```

### 2.2 记录用户行为事件
### `POST /api/public/events`
**功能**：前端埋点，记录用户在页面上的操作行为（点击开始、查看报告等）  
**鉴权**：无  
**请求体**：
```json
{
  "session_token": "a1b2c3...",
  "lead_id": 1,                  // 可选，创建线索后才有
  "event_name": "click_start",   // 事件名：click_start / enter_site / submit_customer_info / submit_questionnaire / view_report_summary / claim_full_report
  "metadata": {}                 // 可选，额外数据
}
```
**返回**：
```json
{ "message": "tracked" }
```
**测试命令**：
```bash
curl -X POST http://localhost:8000/api/public/events \
  -H "Content-Type: application/json" \
  -d '{"session_token": "你的session_token", "event_name": "click_start"}'
```

### 2.3 获取题库
### `GET /api/public/questions`
**功能**：获取全部 10 个模块 + 68 道题目（含选项描述），前端渲染答题页  
**鉴权**：无  
**请求**：无参数  
**返回**：10 个模块的数组，每个模块含题目列表：
```json
[
  {
    "id": 1,
    "code": "M01",
    "name": "一心：以用户/客户为中心",
    "description": "以用户/客户为中心",
    "max_score": 28,
    "sort_order": 1,
    "questions": [
      {
        "id": 1,
        "code": "Q1",
        "dimension": "用户洞察",
        "text": "公司是否有系统性的用户研究与洞察机制？",
        "option_text": "0=完全没有；1=主要靠销售偶发反馈；2=有定期调研但不系统；3=有NPS+结构化用研；4=实时用户行为数据+AI闭环反馈",
        "sort_order": 1,
        "max_score": 4
      }
      // ... 每题
    ]
  }
  // ... 共 10 个模块
]
```
**测试命令**：
```bash
curl http://localhost:8000/api/public/questions
```

### 2.4 提交企业信息
### `POST /api/public/leads`
**功能**：客户填写完企业信息后提交，创建/更新线索记录，并自动创建答题提交记录  
**鉴权**：无  
**请求体**：
```json
{
  "session_token": "a1b2c3...",
  "company_name": "XX科技有限公司",       // 必填
  "industry": "制造业",                    // 必填
  "company_size": "200-1000人",            // 必填
  "annual_revenue": "1-5亿",              // 可选
  "contact_name": "张三",                  // 必填
  "position": "CTO",                       // 必填
  "phone": "13800138000",                  // 手机或微信至少填一项
  "wechat": "zhangsan_wx",                 // 手机或微信至少填一项
  "ai_focus": "智能客服、流程自动化",       // 可选，AI关注方向
  "privacy_accepted": true,                // 必填，必须为 true
  "contact_authorized": true,              // 必填
  "source_code": "wechat_mp"               // 可选，渠道来源
}
```
**返回**：
```json
{
  "lead": {
    "id": 1,
    "session_token": "a1b2c3...",
    "company_name": "XX科技有限公司",
    "industry": "制造业",
    ...
    "lead_level": "low",                   // low/medium/high，评分后更新
    "created_at": "2026-07-06T14:30:00"
  },
  "submission_id": 1                       // 后续答题和提交都要用这个 ID
}
```
**校验规则**：
- `privacy_accepted` 必须为 `true`，否则返回 422
- `phone` 和 `wechat` 至少填一个，否则返回 422
**测试命令**：
```bash
curl -X POST http://localhost:8000/api/public/leads \
  -H "Content-Type: application/json" \
  -d '{
    "session_token": "你的session_token",
    "company_name": "XX科技",
    "industry": "制造业",
    "company_size": "200-1000人",
    "contact_name": "张三",
    "position": "CTO",
    "phone": "13800138000",
    "privacy_accepted": true,
    "contact_authorized": true
  }'
```

### 2.5 保存草稿
### `PUT /api/public/submissions/{submission_id}/draft`
**功能**：客户答题过程中随时保存，支持断点续答  
**鉴权**：无  
**路径参数**：`submission_id`（从"提交企业信息"接口返回）  
**请求体**：
```json
{
  "answers": [
    { "question_id": 1, "score": 3 },
    { "question_id": 2, "score": 2 }
    // ... 已回答的题目
  ]
}
```
**返回**：
```json
{ "message": "draft saved" }
```
**测试命令**：
```bash
curl -X PUT http://localhost:8000/api/public/submissions/1/draft \
  -H "Content-Type: application/json" \
  -d '{"answers": [{"question_id": 1, "score": 3}]}'
```

### 2.6 提交问卷 + 生成报告
### `POST /api/public/submissions/{submission_id}/submit`
**功能**：客户完成全部 68 题后提交。系统执行评分、调用 DeepSeek AI 生成报告、返回报告链接。**这是核心接口，会等待 AI 生成完成，可能需要 5-45 秒。**  
**鉴权**：无  
**路径参数**：`submission_id`  
**请求体**：
```json
{
  "answers": [
    { "question_id": 1, "score": 3 },
    { "question_id": 2, "score": 2 }
    // ... 必须包含全部 68 题
  ]
}
```
**返回**：
```json
{
  "score": {
    "submission_id": 1,
    "total_score": 187,                    // 总分（满分 260）
    "max_score": 260,
    "score_rate": 0.719,                   // 得分率（0-1）
    "risk_level": "良好",                  // 高风险/较弱/良好/优秀
    "low_dimensions": [                    // 最薄弱的 3 个维度
      { "module_code": "M03", "module_name": "简练组织", "raw_score": 12, "max_score": 26, "score_rate": 0.462, "risk_level": "较弱" }
    ],
    "dimensions": [                        // 全部 10 个维度详情
      { "module_code": "M01", "module_name": "一心", "raw_score": 22, "max_score": 28, "score_rate": 0.786, "risk_level": "优秀" }
      // ... 共 10 个
    ]
  },
  "report": {
    "id": 1,
    "public_token": "f1e2d3c4...",        // 报告公开链接的 token
    "status": "generated",                 // generated=AI生成 / fallback=模板生成 / failed=失败
    "title": "XX科技有限公司 AI 原生转型诊断报告",
    "html_content": "<article class=\"report-document\">...完整HTML报告...</article>",
    "model_vendor": "deepseek",
    "model_name": "deepseek-chat",
    "created_at": "2026-07-06T14:30:45"
  }
}
```
**校验规则**：
- 如果缺少任何一题的答案，返回 422，detail 中列出缺失的 question_id
- 每题的 score 必须在 0-4 之间
**测试命令**：
```bash
curl -X POST http://localhost:8000/api/public/submissions/1/submit \
  -H "Content-Type: application/json" \
  -d '{"answers": [{"question_id": 1, "score": 3}, ...共68题...]}'
```

### 2.7 查看公开报告
### `GET /api/public/reports/{public_token}`
**功能**：通过公开链接查看诊断报告（客户分享给他人时使用）  
**鉴权**：无  
**路径参数**：`public_token`（从提交接口返回的 `report.public_token`）  
**返回**：
```json
{
  "id": 1,
  "public_token": "f1e2d3c4...",
  "status": "generated",
  "title": "XX科技有限公司 AI 原生转型诊断报告",
  "html_content": "<article>...</article>",
  "created_at": "2026-07-06T14:30:45",
  "score": {
    "total": 187,
    "max_score": 260,
    "score_rate": 0.719,
    "risk_level": "良好"
  },
  "dimensions": [
    { "module_code": "M01", "module_name": "一心", "raw_score": 22, "max_score": 28, "score_rate": 0.786, "risk_level": "优秀" }
    // ... 共 10 个
  ],
  "low_dimensions": [
    { "module_code": "M03", "module_name": "简练组织", "raw_score": 12, "max_score": 26, "score_rate": 0.462, "risk_level": "较弱" }
    // ... 最薄弱的 3 个
  ]
}
```
**测试命令**：
```bash
curl http://localhost:8000/api/public/reports/f1e2d3c4...
```

### 2.8 下载报告 PDF
### `GET /api/public/reports/{public_token}/pdf`
**功能**：下载诊断报告 PDF 文件（含柱状图和雷达图）  
**鉴权**：无  
**路径参数**：`public_token`  
**返回**：PDF 文件（二进制流），Content-Type: `application/pdf`  
**测试命令**：
```bash
curl -O http://localhost:8000/api/public/reports/f1e2d3c4.../pdf
```

### 2.9 获取渠道二维码
### `GET /api/public/channels/{code}/qr`
**功能**：获取指定渠道的二维码图片（PNG），用于打印或嵌入网页  
**鉴权**：无  
**路径参数**：`code`（渠道编码，如 `wechat_mp`、`default`）  
**返回**：PNG 图片（二进制流），Content-Type: `image/png`  
**说明**：二维码内容为 `{PUBLIC_WEB_BASE_URL}/?source={code}`，扫码后自动带渠道参数  
**测试命令**：
```bash
curl -o qr.png http://localhost:8000/api/public/channels/default/qr
```

---

## 三、管理后台接口（15 个接口）

> 所有管理接口需要 JWT 鉴权：请求头 `Authorization: Bearer {access_token}`  
> 先调用登录接口获取 token，token 有效期 720 分钟（12 小时）

### 3.1 后台登录
### `POST /api/admin/auth/login`
**功能**：后台用户登录，返回 JWT access_token  
**鉴权**：无（但有限流 5次/分钟）  
**请求体**：
```json
{
  "email": "admin@example.com",
  "password": "Admin123!"
}
```
**返回**：
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",   // JWT token
  "token_type": "bearer"
}
```
**错误**：401 "账号或密码错误"  
**限流**：同一 IP 每分钟最多 5 次  
**测试命令**：
```bash
curl -X POST http://localhost:8000/api/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "Admin123!"}'
```

### 3.2 获取当前用户信息
### `GET /api/admin/me`
**功能**：校验 token 有效性，返回当前登录用户信息  
**鉴权**：Bearer Token（任意角色）  
**请求头**：`Authorization: Bearer {token}`  
**返回**：
```json
{
  "id": 1,
  "email": "admin@example.com",
  "name": "系统管理员",
  "role": "admin",
  "is_active": true,
  "created_at": "2026-07-01T10:00:00"
}
```
**测试命令**：
```bash
curl http://localhost:8000/api/admin/me \
  -H "Authorization: Bearer 你的token"
```

### 3.3 创建后台用户
### `POST /api/admin/users`
**功能**：管理员创建新的后台用户  
**鉴权**：`admin` 角色  
**请求体**：
```json
{
  "email": "operator@example.com",
  "name": "运营小王",
  "role": "operator",            // admin / operator / sales / consultant
  "password": "ChangeMe123!"     // 最少 8 位
}
```
**返回**：同 3.2 的用户对象  
**错误**：409 "Email already exists"  
**测试命令**：
```bash
curl -X POST http://localhost:8000/api/admin/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 你的token" \
  -d '{"email": "test@test.com", "name": "测试", "role": "sales", "password": "Test1234!"}'
```

### 3.4 列出后台用户
### `GET /api/admin/users`
**功能**：管理员查看所有后台用户列表  
**鉴权**：`admin` 角色  
**返回**：用户对象数组  
**测试命令**：
```bash
curl http://localhost:8000/api/admin/users \
  -H "Authorization: Bearer 你的token"
```

### 3.5 线索列表
### `GET /api/admin/leads`
**功能**：查看所有客户线索（支持按行业、等级、来源筛选）  
**鉴权**：`admin` / `operator` / `sales` / `consultant`  
**查询参数**（可选）：
- `industry` — 行业筛选，如 `制造业`
- `lead_level` — 线索等级，`low` / `medium` / `high`
- `source_code` — 来源渠道，如 `wechat_mp`
**返回**：最多 500 条，按创建时间倒序  
```json
[
  {
    "id": 1,
    "session_token": "a1b2c3...",
    "company_name": "XX科技有限公司",
    "industry": "制造业",
    "company_size": "200-1000人",
    "contact_name": "张三",
    "position": "CTO",
    "phone": "13800138000",
    "wechat": null,
    "ai_focus": "智能客服",
    "source_code": "default",
    "lead_level": "medium",
    "created_at": "2026-07-06T14:30:00"
  }
]
```
**测试命令**：
```bash
# 全部线索
curl http://localhost:8000/api/admin/leads \
  -H "Authorization: Bearer 你的token"

# 筛选制造业 + 高意向
curl "http://localhost:8000/api/admin/leads?industry=%E5%88%B6%E9%80%A0%E4%B8%9A&lead_level=high" \
  -H "Authorization: Bearer 你的token"
```

### 3.6 导出线索 CSV
### `GET /api/admin/leads/export`
**功能**：导出全部线索为 CSV 文件  
**鉴权**：`admin` / `operator` / `sales`  
**返回**：CSV 文件下载（Content-Type: `text/csv`）  
**CSV 列头**：公司, 行业, 规模, 联系人, 职位, 手机, 微信, 来源, 线索等级, 创建时间  
**测试命令**：
```bash
curl -o leads.csv http://localhost:8000/api/admin/leads/export \
  -H "Authorization: Bearer 你的token"
```

### 3.7 查看报告详情
### `GET /api/admin/reports/{report_id}`
**功能**：后台查看某份诊断报告的完整内容（含 HTML 和结构化摘要）  
**鉴权**：`admin` / `operator` / `sales` / `consultant`  
**路径参数**：`report_id`（数字 ID，非 public_token）  
**返回**：
```json
{
  "id": 1,
  "public_token": "f1e2d3c4...",
  "title": "XX科技有限公司 AI 原生转型诊断报告",
  "status": "generated",
  "html_content": "<article>...</article>",
  "summary": { "score": {...}, "dimensions": [...], "low_dimensions": [...], "cases": [...] },
  "created_at": "2026-07-06T14:30:45"
}
```
**测试命令**：
```bash
curl http://localhost:8000/api/admin/reports/1 \
  -H "Authorization: Bearer 你的token"
```

### 3.8 查看题库
### `GET /api/admin/questions`
**功能**：后台查看所有模块和题目（含非激活题）  
**鉴权**：`admin` / `operator` / `sales` / `consultant`  
**返回**：同 2.3 结构  
**测试命令**：
```bash
curl http://localhost:8000/api/admin/questions \
  -H "Authorization: Bearer 你的token"
```

### 3.9 新增/更新模块
### `POST /api/admin/modules`
**功能**：创建或更新题库模块  
**鉴权**：`admin` / `operator`  
**请求体**：
```json
{
  "code": "M11",
  "name": "新模块",
  "description": "模块描述",
  "max_score": 30,
  "sort_order": 11,
  "is_active": true
}
```
**返回**：模块对象  
**说明**：如果 `code` 已存在则更新，不存在则新增  
**测试命令**：
```bash
curl -X POST http://localhost:8000/api/admin/modules \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 你的token" \
  -d '{"code": "M11", "name": "测试模块", "max_score": 20, "sort_order": 11, "is_active": true}'
```

### 3.10 新增/更新题目
### `POST /api/admin/questions`
**功能**：在指定模块下创建或更新题目  
**鉴权**：`admin` / `operator`  
**请求体**：
```json
{
  "module_code": "M01",
  "code": "Q1",
  "dimension": "用户洞察",
  "text": "公司是否有系统性的用户研究与洞察机制？",
  "option_text": "0=完全没有；1=主要靠销售偶发反馈；2=有定期调研但不系统；3=有NPS+结构化用研；4=实时用户行为数据+AI闭环反馈",
  "sort_order": 1,
  "max_score": 4,
  "is_active": true
}
```
**返回**：题目对象  
**错误**：404 如果 module_code 不存在  
**测试命令**：
```bash
curl -X POST http://localhost:8000/api/admin/questions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 你的token" \
  -d '{"module_code": "M01", "code": "Q99", "text": "测试题", "sort_order": 99, "max_score": 4, "is_active": true}'
```

### 3.11 案例列表
### `GET /api/admin/cases`
**功能**：查看所有 AI 场景案例  
**鉴权**：`admin` / `operator` / `sales` / `consultant`  
**返回**：
```json
[
  {
    "id": 1,
    "title": "智能客服知识库",
    "industry": "通用",
    "function_area": "客户服务",
    "module_code": "M01",
    "maturity": "MVP",
    "roi_level": "high",
    "difficulty": "medium",
    "description": "用企业 FAQ、产品资料和服务 SOP 搭建客服助手...",
    "expected_benefit": "提升响应速度，沉淀高频问题...",
    "priority_tag": "闪电战",
    "is_active": true,
    "created_at": "2026-07-01T10:00:00"
  }
]
```
**测试命令**：
```bash
curl http://localhost:8000/api/admin/cases \
  -H "Authorization: Bearer 你的token"
```

### 3.12 新增案例
### `POST /api/admin/cases`
**功能**：创建新的 AI 场景案例  
**鉴权**：`admin` / `operator`  
**请求体**：
```json
{
  "title": "智能排产优化",
  "industry": "制造业",
  "function_area": "生产调度",
  "module_code": "M06",
  "maturity": "MVP",
  "roi_level": "high",
  "difficulty": "medium",
  "description": "基于历史订单数据训练排产模型...",
  "expected_benefit": "减少产线空闲时间 20%...",
  "priority_tag": "攻坚战",
  "is_active": true
}
```
**返回**：案例对象  
**测试命令**：
```bash
curl -X POST http://localhost:8000/api/admin/cases \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 你的token" \
  -d '{"title": "测试案例", "industry": "通用", "function_area": "测试", "module_code": "M01", "description": "测试描述", "expected_benefit": "测试收益"}'
```

### 3.13 渠道列表
### `GET /api/admin/channels`
**功能**：查看所有推广渠道  
**鉴权**：`admin` / `operator` / `sales` / `consultant`  
**返回**：
```json
[
  {
    "id": 1,
    "code": "default",
    "name": "默认渠道",
    "description": "官网和默认二维码入口",
    "is_active": true,
    "created_at": "2026-07-01T10:00:00"
  }
]
```
**测试命令**：
```bash
curl http://localhost:8000/api/admin/channels \
  -H "Authorization: Bearer 你的token"
```

### 3.14 新增渠道
### `POST /api/admin/channels`
**功能**：创建或更新推广渠道（创建后可调用 2.9 获取该渠道的二维码）  
**鉴权**：`admin` / `operator`  
**请求体**：
```json
{
  "code": "wechat_mp",
  "name": "微信公众号",
  "description": "公众号菜单栏入口",
  "is_active": true
}
```
**返回**：渠道对象  
**测试命令**：
```bash
curl -X POST http://localhost:8000/api/admin/channels \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 你的token" \
  -d '{"code": "offline_event", "name": "线下活动", "description": "展会扫码入口"}'
```

### 3.15 统计分析看板
### `GET /api/admin/analytics/summary`
**功能**：后台首页统计看板  
**鉴权**：`admin` / `operator` / `sales` / `consultant`  
**返回**：
```json
{
  "visit_uv": 328,                      // 独立访客数（进入页面的人数）
  "started_count": 156,                 // 点击"开始自测"的人数
  "info_completed_count": 98,           // 完成企业信息填写的人数
  "questionnaire_completed_count": 42,  // 完成全部 68 题的人数
  "report_generated_count": 41,         // 成功生成报告的数量
  "report_claimed_count": 28,           // 下载 PDF 的数量
  "high_intent_leads": 15,              // 高意向线索数（有联系方式+至少2个低分维度）
  "lead_count": 98                      // 线索总数
}
```
**指标说明**：
- 漏斗：visit_uv → started → info_completed → questionnaire_completed → report_generated
- 高意向线索判定：客户留了手机或微信 + 诊断结果中有至少 2 个维度得分率低于 50%
**测试命令**：
```bash
curl http://localhost:8000/api/admin/analytics/summary \
  -H "Authorization: Bearer 你的token"
```

---

## 四、鉴权角色权限速查表

| 角色 | 可访问接口 |
|---|---|
| `admin` | 所有管理接口（包括创建用户） |
| `operator` | 管理题库、案例、渠道；查看线索、报告、统计 |
| `sales` | 查看线索（含导出）、查看报告、查看统计 |
| `consultant` | 查看线索、查看报告、查看统计 |

---

## 五、完整自测流程（curl 脚本）

```bash
BASE=http://localhost:8000

# 1. 创建会话
SESSION=$(curl -s -X POST $BASE/api/public/sessions \
  -H "Content-Type: application/json" \
  -d '{"source_code": "default"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['session_token'])")
echo "SESSION: $SESSION"

# 2. 获取题库
curl -s $BASE/api/public/questions | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d)} 个模块, {sum(len(m[\"questions\"]) for m in d)} 道题')"

# 3. 提交企业信息
RESULT=$(curl -s -X POST $BASE/api/public/leads \
  -H "Content-Type: application/json" \
  -d "{
    \"session_token\": \"$SESSION\",
    \"company_name\": \"测试公司\",
    \"industry\": \"制造业\",
    \"company_size\": \"200-1000人\",
    \"contact_name\": \"张三\",
    \"position\": \"CTO\",
    \"phone\": \"13800138000\",
    \"privacy_accepted\": true,
    \"contact_authorized\": true
  }")
SUBMISSION_ID=$(echo $RESULT | python3 -c "import sys,json; print(json.load(sys.stdin)['submission_id'])")
echo "SUBMISSION_ID: $SUBMISSION_ID"

# 4. 提交问卷（全部 68 题打满分 4）
ANSWERS="["
for i in $(seq 1 68); do
  [ $i -gt 1 ] && ANSWERS="$ANSWERS,"
  ANSWERS="$ANSWERS{\"question_id\": $i, \"score\": 4}"
done
ANSWERS="$ANSWERS]"

REPORT=$(curl -s -X POST $BASE/api/public/submissions/$SUBMISSION_ID/submit \
  -H "Content-Type: application/json" \
  -d "{\"answers\": $ANSWERS}")
TOKEN=$(echo $REPORT | python3 -c "import sys,json; print(json.load(sys.stdin)['report']['public_token'])")
SCORE=$(echo $REPORT | python3 -c "import sys,json; print(json.load(sys.stdin)['score']['total_score'])")
echo "总分: $SCORE / 260"
echo "报告链接: $BASE/api/public/reports/$TOKEN"

# 5. 查看报告
curl -s $BASE/api/public/reports/$TOKEN | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'标题: {d[\"title\"]}'); print(f'维度数: {len(d[\"dimensions\"])}')"

# 6. 下载 PDF
curl -s -o report.pdf $BASE/api/public/reports/$TOKEN/pdf && echo "PDF 已下载"
```
