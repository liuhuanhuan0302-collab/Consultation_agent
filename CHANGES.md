# 改动说明 — Codex 审核用

本次改动围绕三个目标：**可视化图表**、**二维码生成**、**生产部署配置**。

---

## 一、可视化图表（柱状图 + 雷达图）

### 1. 新增 `frontend/src/components/ReportCharts.vue`

独立的 Vue SFC，接收 `dimensions: DimensionScore[]` prop，渲染两张 Chart.js 图表：

- **水平柱状图**：按得分率从低到高排列 10 个模块，颜色按风险等级区分（高风险=#ef4444，较弱=#f59e0b，良好=#3b82f6，优秀=#22c55e）
- **雷达图**：10 轴展示各维度得分率，点位同样按风险等级着色
- 桌面端两列并排，移动端（<820px）堆叠

### 2. 修改 `frontend/package.json`

新增依赖：`chart.js` ^4.4.0、`vue-chartjs` ^5.3.0

### 3. 修改 `backend/app/main.py` — `GET /api/public/reports/{public_token}`

旧的公开报告接口只返回 `html_content`，不含评分数据，所以公开链接无法渲染图表。改动：从 `summary_json` 字段解析出 `score`、`dimensions`、`low_dimensions`，一并通过 API 返回。

```python
summary = json.loads(report.summary_json or "{}")
return {
    ...
    "score": summary.get("score"),
    "dimensions": summary.get("dimensions", []),
    "low_dimensions": summary.get("low_dimensions", []),
}
```

### 4. 修改 `frontend/src/types.ts`

`Report` 类型新增三个可选字段：`score?`、`dimensions?`、`low_dimensions?`

### 5. 修改 `frontend/src/App.vue`

- 导入 `ReportCharts` 组件
- 新增 `chartDimensions` 计算属性，优先取 `score.dimensions`，回退取 `publicReport.dimensions`
- 在两处报告视图（问卷提交后 + 公开链接页）的 `.score-strip` 和 `.report-html` 之间插入 `<ReportCharts>`

---

## 二、二维码生成（渠道管理）

### 1. 新增 `backend/app/qr_code.py`

封装 `qrcode` 库，`generate_qr_png(url)` 返回 PNG 字节流。

### 2. 修改 `backend/app/main.py`

新增三个端点：

| 方法 | 路径 | 鉴权 | 说明 |
|---|---|---|---|
| GET | `/api/admin/channels` | LeadViewer | 渠道列表 |
| POST | `/api/admin/channels` | ContentManager | 新增/更新渠道 |
| GET | `/api/public/channels/{code}/qr` | **无鉴权** | 返回 QR PNG 图片 |

QR 端点无鉴权是因为 `<img>` 标签无法携带 Authorization header，且二维码只编码公开 URL，无安全风险。

### 3. 修改 `backend/app/schemas.py`

新增 `ChannelRead` 和 `ChannelUpsert` schema。

### 4. 修改 `backend/requirements.txt`

新增 `qrcode[pil]>=7.4,<8`。

### 5. 修改 `frontend/src/App.vue`

- 后台新增 "渠道" 标签页（`channels`），位于账号管理之后
- 表单：渠道编码（code）、名称、描述
- 列表：每个渠道展示 QR 图片（来自 `/api/public/channels/{code}/qr`）和基本信息
- 新增 `createChannel()`、`channels` ref、`channelForm` reactive

### 6. 修改 `frontend/src/api.ts`

新增 `channels()` 和 `createChannel()` 两个 API 方法。

### 7. 修改 `frontend/src/types.ts`

新增 `ChannelSource` 类型。

### 8. 修改 `frontend/src/styles.css`

新增 `.channel-item`、`.channel-qr img`、`.channel-info` 样式，并将 `.channel-list`、`.channel-item` 加入已有网格布局规则和共享卡片样式，与案例管理页面保持视觉一致。

---

## 三、生产部署配置

### 新增文件

| 文件 | 说明 |
|---|---|
| `backend/Dockerfile` | Python 3.12-slim，安装 Noto CJK 字体，uvicorn 4 worker |
| `frontend/Dockerfile` | 多阶段：node:20-alpine 构建产物 → nginx:alpine 运行 |
| `frontend/nginx.conf` | SPA try_files + `/api/` 反向代理到 backend:8000 |
| `docker-compose.yml` | backend + frontend 两个服务，数据库指向外部 MySQL |
| `.env.production` | 生产环境变量模板（含注释） |

nginx 的关键配置：所有 `/api/` 请求代理到后端，其他路径 fallback 到 `index.html`（支持 Vue SPA 路由 `/admin` 和 `/report/:token`）。

---

## 验证结果

- `vue-tsc --noEmit` — 通过
- `vite build` — 构建成功（278KB JS + 8.5KB CSS）
- Backend 导入检查 — 30 条路由注册成功
- `pytest` — 10/10 通过（test_scoring 9个 + test_report_fallback 1个）

---

## 四、Codex 审核后优化补充

### 1. 生产空库自动加载正式题库

新增 `backend/app/data/official_questionnaire.json`，将正式 Excel 题库固化为随后端发布的 JSON fixture。

修改 `backend/app/seed.py`：

- 启动初始化时优先读取官方题库 JSON
- 生产空库首次启动会自动创建 10 个模块、68 道正式题
- 只有官方题库文件缺失时才回退到示例题

验证结果：使用临时空 SQLite 库初始化，得到 `10` 个模块、`68` 道题，第一题为正式题库 `Q1 用户洞察 公司是否有系统性的用户研究与洞察机制？`

### 2. PDF 导出补齐图表

修改 `backend/app/pdf_service.py`：

- 从 `report.summary_json` 读取 `dimensions`
- 在 PDF 中绘制“维度得分排行”柱状图
- 在 PDF 中绘制“能力雷达图”
- 保留原有报告正文导出

验证结果：历史报告可成功导出 PDF，包含 10 个维度数据，PDF 文件头为 `%PDF`。

### 3. Docker 部署配置加固

修改 `docker-compose.yml`：

- 后端改为通过 `env_file: .env.production` 读取生产环境变量
- 移除会误导直接启动的假 MySQL 默认连接

修改 `backend/Dockerfile`：

- 移除 `--workers 4`
- 使用单 worker 启动，避免首次启动时多个 worker 并发 seed 空库

修改 `.env.production` 和 `README.md`：

- 明确 `.env.production` 是 Docker 部署要填写的生产配置
- README 增加 `docker compose up -d --build`
- 说明后端镜像已内置正式 68 题题库

### 4. 工程卫生

修改 `.gitignore`：

- 忽略 `.claude/`
- 忽略 `.idea/`
- 忽略 `backend/.idea/`

已删除本地 `.claude/` 和 `backend/.idea/` 目录，避免工具权限和 IDE 配置混入交付。

### 5. 本轮验证结果

- `pytest` — 10/10 通过
- `npm run build` — Vue 类型检查与 Vite 构建通过
- `py_compile` — `seed.py`、`pdf_service.py`、`main.py` 通过
- 临时空库 seed — 自动导入正式 68 题通过
- PDF 导出 — 图表数据渲染与 PDF 生成通过
