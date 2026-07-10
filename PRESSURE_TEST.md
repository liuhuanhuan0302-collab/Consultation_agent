# 压力测试说明

本项目压测建议分两类：

1. 基础链路压测：扫码进入、获取题库、提交企业信息、保存草稿。
2. 完整链路压测：额外提交完整 68 题并生成报告。

基础链路适合测 100 并发。完整链路会触发评分、报告生成和可能的大模型调用，建议单独小并发测试。

## 一、压测前准备

后端不要使用 `--reload` 开发模式压测。

本地或服务器启动后端：

```powershell
cd E:\Consultation_agent\backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

服务器 Linux 上建议：

```bash
cd /opt/consultation_agent/backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

压测前先确认健康检查正常：

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/health
```

服务器上：

```bash
curl http://127.0.0.1:8000/api/health
```

## 二、数据库连接池建议

100 并发建议在后端 `.env` 增加：

```env
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
DB_POOL_TIMEOUT=30
```

如果 MySQL 和后端在同一台 2 核 4G 服务器上，不建议再继续调大太多。

## 三、基础链路压测

从小到大跑，不要直接 100。

```powershell
cd E:\Consultation_agent\backend
.venv\Scripts\python.exe scripts\load_test.py --host http://127.0.0.1:8000 --users 20 --concurrency 10
.venv\Scripts\python.exe scripts\load_test.py --host http://127.0.0.1:8000 --users 60 --concurrency 30
.venv\Scripts\python.exe scripts\load_test.py --host http://127.0.0.1:8000 --users 100 --concurrency 50
.venv\Scripts\python.exe scripts\load_test.py --host http://127.0.0.1:8000 --users 200 --concurrency 100
```

如果压服务器公网地址：

```powershell
.venv\Scripts\python.exe scripts\load_test.py --host http://你的服务器公网IP --users 200 --concurrency 100
```

## 四、完整链路压测

完整提交会生成报告，可能调用 DeepSeek，不建议一上来 100 并发。

```powershell
.venv\Scripts\python.exe scripts\load_test.py --host http://127.0.0.1:8000 --users 10 --concurrency 3 --full-submit
.venv\Scripts\python.exe scripts\load_test.py --host http://127.0.0.1:8000 --users 30 --concurrency 5 --full-submit
```

正式活动前，如果要测完整链路，建议先临时不配置 `DEEPSEEK_API_KEY`，让报告走模板兜底，避免模型接口成为压测瓶颈。

## 五、通过标准

基础链路 100 并发建议达到：

- 成功率：99% 以上
- P95：小于 1500ms
- 不能出现大量 500 / 502 / 数据库连接超时

完整报告链路建议达到：

- 成功率：95% 以上
- 报告生成可慢一些，但不要整体失败
- 模型失败时要能回退模板报告

## 六、压测后检查

压测会写入测试线索，`source_code` 为 `load_test`。

可以在 MySQL 中清理：

```sql
DELETE FROM tracking_events WHERE session_token IN (
  SELECT session_token FROM company_leads WHERE source_code = 'load_test'
);
DELETE FROM company_leads WHERE source_code = 'load_test';
```

如果有外键限制，请先清理关联表，或使用测试库压测。
