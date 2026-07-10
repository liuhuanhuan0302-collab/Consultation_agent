# Copilot / AI Agent 指令（项目特定）

目的：帮助 AI 编码代理快速理解本仓库的结构、关键约定与常用开发流程，便于做出安全、准确且一致的代码改动。

- **快速启动命令**
  - 开发：`npm run dev`（内部调用 `vite --host 0.0.0.0`，端口默认 `5173`）
  - 构建：`npm run build`（会先执行 `vue-tsc --noEmit`）
  - 预览：`npm run preview`

- **大局观（架构 & 责任边界）**
  - 前端为 SPA：Vue 3 + Vite + TypeScript。入口为 [src/main.ts](src/main.ts)。
  - 核心 UI 与业务逻辑主要在单文件组件 [src/App.vue](src/App.vue) 中实现：包含访客端问卷流程（session、线索提交、答题、生成报告）与管理员面板（/admin）共用同一应用。
  - HTTP 客户端封装在 [src/api.ts](src/api.ts)：统一处理 `Content-Type`、`Authorization`（从 `localStorage.admin_token` 读取）、错误解析与基础 URL（由 `VITE_API_BASE_URL` 控制）。
  - 数据契约定义在 [src/types.ts](src/types.ts)，新增接口或字段应先更新此文件以保持静态类型一致性。
  - 可视化组件在 [src/components/ReportCharts.vue](src/components/ReportCharts.vue)。新增图表应复用该组件的 Chart.js 注册与配置方式。

- **环境与后端集成要点**
  - 默认 API 基址由 `import.meta.env.VITE_API_BASE_URL` 控制（如果为空，`src/api.ts` 会使用相对路径）。
  - 本地开发时 `vite.config.ts` 已配置代理：`/api` -> `http://127.0.0.1:8000`（可在 [vite.config.ts](vite.config.ts) 中修改）。
  - `vite.config.ts` 亦配置 `allowedHosts`（用于 ngrok 等临时域名）。

- **重要运行时约定（state / storage / 路径）**
  - 本地持久化键（示例）：`diagnosis_session`、`diagnosis_lead_id`、`submission_id`、`diagnosis_answers`、`diagnosis_step`、`admin_token`。
  - 公共报告路由为 `/report/:token`；管理员入口由路径前缀 `/admin` 判断（参见 `isAdmin` 在 `src/App.vue` 中的实现）。
  - 创建会话：使用 `api.createSession()` -> POST `/api/public/sessions`；提交线索和提交问卷分别使用 `/api/public/leads` 与 `/api/public/submissions/:id/submit`。

- **代码风格与约定（项目特定）**
  - 文案与界面主要为中文。UI 文案替换或新增请使用中文字符并遵循现有短语（例如 “诊断报告”, “高风险” 等）。
  - 前端错误处理：`src/api.ts` 在非 2xx 时尝试解析 JSON 并抛出 `Error(payload.detail || '请求失败')`，上层组件通常显示 `err.message`。
  - 在 `src/App.vue` 中有较多直接对 `localStorage`、路由（history.pushState）与 DOM 滚动的操作；对该文件的改动请小心保持原有本地恢复/持久化逻辑。

- **新增代码示例（如何扩展 API）**
  - 若要新增后端接口，先在 [src/types.ts](src/types.ts) 添加返回类型，然后在 [src/api.ts](src/api.ts) 中添加方法，遵循现有 `request<T>(path, options)` 模式并返回 `Promise<T>`。

- **调试提示**
  - 若前端请求 401/授权问题：检查 `localStorage.admin_token`、`api` 的 `Authorization` 头，以及后端是否在 `/api/admin` 路径启用 token 校验。
  - 本地联调后端：确保后端监听 `127.0.0.1:8000` 或调整 `vite.config.ts` 的 proxy/target，或设置 `VITE_API_BASE_URL` 指向后端地址。

- **不要推测的内容 / 归档说明**
  - 本文件仅记录从代码可观察到的约定与流程；如果需要后端 API 的更详细语义（字段含义、枚举值等），请提供后端 OpenAPI/文档或后端代码以补充。

请审阅该草稿并指出是否需要补充后端文档、部署说明或其他未覆盖的开发流程。
