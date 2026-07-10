# API 接口测试手册

> 服务地址：`http://localhost:8000`  
> 默认管理员：`admin@example.com` / `Admin123!`  
> 跑 `curl` 之前确保后端已启动：`cd backend && uvicorn app.main:app --reload --port 8000`

---

## 一、先确认服务活着

```bash
curl http://localhost:8000/api/health
# 预期返回 → {"status":"ok","environment":"development","database":"ok"}
```

---

## 二、完整客户自测流程（一次跑通，拿到报告）

### 第 1 步：创建会话 —— 拿到 session_token

```bash
curl -s -X POST http://localhost:8000/api/public/sessions \
  -H "Content-Type: application/json" \
  -d '{"source_code": "default"}'
```
**说明**：客户首次打开页面时调用，返回 `session_token`，后面全部用这个。

**预期返回**：
```json
{"session_token": "abc123def456..."}
```

---

### 第 2 步：获取题库 —— 看看 10 模块 68 题长什么样

```bash
curl -s http://localhost:8000/api/public/questions | python -c "import sys,json; d=json.load(sys.stdin); print(f'模块数: {len(d)}'); [print(f'  {m[\"code\"]} {m[\"name\"]}: {len(m[\"questions\"])}题') for m in d]"
```
**说明**：获取全部题目，前端靠这个渲染答题页。

**预期输出**：
```
模块数: 10
  M01 一心：以用户/客户为中心: 7题
  M02 简化业务：业务聚焦与差异化: 7题
  ...
  M10 五差就绪度：...: 7题
```

---

### 第 3 步：提交企业信息 —— 拿到 submission_id

```bash
curl -s -X POST http://localhost:8000/api/public/leads \
  -H "Content-Type: application/json" \
  -d '{
    "session_token": "你的session_token",
    "company_name": "XX科技有限公司",
    "industry": "制造业",
    "company_size": "200-1000人",
    "contact_name": "张三",
    "position": "CTO",
    "phone": "13800138000",
    "privacy_accepted": true,
    "contact_authorized": true
  }'
```
**说明**：客户填完企业信息后提交，`submission_id` 用于后续答题。

**校验规则**：
- `privacy_accepted` 必须为 `true`
- `phone` 或 `wechat` 至少填一个

---

### 第 4 步：保存草稿（可选）—— 答了一部分先存起来

```bash
curl -s -X PUT http://localhost:8000/api/public/submissions/1/draft \
  -H "Content-Type: application/json" \
  -d '{"answers": [{"question_id": 1, "score": 3}, {"question_id": 2, "score": 4}]}'
```
**说明**：随时保存，同一个 `question_id` 再次提交会覆盖。

---

### 第 5 步：提交全部问卷 —— 评分 + 生成报告

```bash
curl -s -X POST http://localhost:8000/api/public/submissions/1/submit \
  -H "Content-Type: application/json" \
  -d '{
    "answers": [
      {"question_id": 1, "score": 3}, {"question_id": 2, "score": 4},
      {"question_id": 3, "score": 2}, {"question_id": 4, "score": 3},
      {"question_id": 5, "score": 4}, {"question_id": 6, "score": 2},
      {"question_id": 7, "score": 3}, {"question_id": 8, "score": 4},
      {"question_id": 9, "score": 2}, {"question_id": 10, "score": 3},
      {"question_id": 11, "score": 4}, {"question_id": 12, "score": 1},
      {"question_id": 13, "score": 3}, {"question_id": 14, "score": 4},
      {"question_id": 15, "score": 2}, {"question_id": 16, "score": 3},
      {"question_id": 17, "score": 4}, {"question_id": 18, "score": 2},
      {"question_id": 19, "score": 3}, {"question_id": 20, "score": 4},
      {"question_id": 21, "score": 1}, {"question_id": 22, "score": 3},
      {"question_id": 23, "score": 4}, {"question_id": 24, "score": 2},
      {"question_id": 25, "score": 3}, {"question_id": 26, "score": 4},
      {"question_id": 27, "score": 2}, {"question_id": 28, "score": 3},
      {"question_id": 29, "score": 4}, {"question_id": 30, "score": 1},
      {"question_id": 31, "score": 3}, {"question_id": 32, "score": 4},
      {"question_id": 33, "score": 2}, {"question_id": 34, "score": 3},
      {"question_id": 35, "score": 4}, {"question_id": 36, "score": 2},
      {"question_id": 37, "score": 3}, {"question_id": 38, "score": 4},
      {"question_id": 39, "score": 1}, {"question_id": 40, "score": 3},
      {"question_id": 41, "score": 4}, {"question_id": 42, "score": 2},
      {"question_id": 43, "score": 3}, {"question_id": 44, "score": 4},
      {"question_id": 45, "score": 2}, {"question_id": 46, "score": 3},
      {"question_id": 47, "score": 4}, {"question_id": 48, "score": 1},
      {"question_id": 49, "score": 3}, {"question_id": 50, "score": 4},
      {"question_id": 51, "score": 2}, {"question_id": 52, "score": 3},
      {"question_id": 53, "score": 4}, {"question_id": 54, "score": 2},
      {"question_id": 55, "score": 3}, {"question_id": 56, "score": 4},
      {"question_id": 57, "score": 1}, {"question_id": 58, "score": 3},
      {"question_id": 59, "score": 4}, {"question_id": 60, "score": 2},
      {"question_id": 61, "score": 3}, {"question_id": 62, "score": 4},
      {"question_id": 63, "score": 2}, {"question_id": 64, "score": 3},
      {"question_id": 65, "score": 4}, {"question_id": 66, "score": 1},
      {"question_id": 67, "score": 3}, {"question_id": 68, "score": 4}
    ]
  }'
```
**说明**：提交全部 68 题答案（每题 0-4 分），系统会依次：保存答案 → 评分 → 调用 DeepSeek AI 生成报告。**这一步要等 5-45 秒**。

**预期返回**（取出关键字段看）：
```bash
# 用这条命令提取关键信息
curl -s -X POST http://localhost:8000/api/public/submissions/1/submit \
  -H "Content-Type: application/json" \
  -d '...上面那堆 answers...' | python -c "
import sys,json
d = json.load(sys.stdin)
s = d['score']
r = d['report']
print(f'总分: {s[\"total_score\"]}/260')
print(f'等级: {s[\"risk_level\"]}')
print(f'得分率: {round(s[\"score_rate\"]*100)}%')
print(f'低分维度: {[x[\"module_name\"] for x in s[\"low_dimensions\"]]}')
print(f'报告链接: /api/public/reports/{r[\"public_token\"]}')
print(f'报告状态: {r[\"status\"]}')
"
```

---

### 第 6 步：查看报告 —— 公开链接

```bash
curl -s http://localhost:8000/api/public/reports/你的public_token | python -c "
import sys,json
d = json.load(sys.stdin)
print(f'标题: {d[\"title\"]}')
print(f'维度数: {len(d.get(\"dimensions\", []))}')
print(f'评分: {d.get(\"score\", {})}')
"
```

---

### 第 7 步：下载 PDF

```bash
curl -o report.pdf http://localhost:8000/api/public/reports/你的public_token/pdf
# 检查文件大小
ls -lh report.pdf
```

---

### 第 8 步：获取渠道二维码

```bash
curl -o qr.png http://localhost:8000/api/public/channels/default/qr
# 打开 qr.png 看看是不是二维码
```

---

## 三、管理后台接口

### 第 9 步：登录 —— 拿 admin token

```bash
curl -s -X POST http://localhost:8000/api/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "Admin123!"}'
```
**说明**：用默认管理员登录。同一 IP 每分钟最多 5 次。

**把返回的 token 存到变量**：
```bash
TOKEN="你的access_token"
```

---

### 第 10 步：获取当前用户信息

```bash
curl -s http://localhost:8000/api/admin/me \
  -H "Authorization: Bearer $TOKEN"
```
**说明**：验证 token 是否有效。有没有角色权限都行。

---

### 第 11 步：线索列表

```bash
# 全部线索
curl -s http://localhost:8000/api/admin/leads \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool | head -20

# 只要高意向
curl -s "http://localhost:8000/api/admin/leads?lead_level=high" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

---

### 第 12 步：导出线索 CSV

```bash
curl -s -o leads.csv http://localhost:8000/api/admin/leads/export \
  -H "Authorization: Bearer $TOKEN"
cat leads.csv
```

---

### 第 13 步：统计分析看板

```bash
curl -s http://localhost:8000/api/admin/analytics/summary \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```
**说明**：看转化漏斗——访客 → 开始测评 → 完成信息 → 完成问卷 → 生成报告 → 下载 PDF。

---

### 第 14 步：题库管理

```bash
# 查看全部题目
curl -s http://localhost:8000/api/admin/questions \
  -H "Authorization: Bearer $TOKEN" | python -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d)}个模块'); print(f'总计{sum(len(m[\"questions\"]) for m in d)}题')"

# 新增一个模块（只有 admin/operator 能做）
curl -s -X POST http://localhost:8000/api/admin/modules \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"code": "M99", "name": "测试模块", "max_score": 10, "sort_order": 99, "is_active": true}' | python -m json.tool
```

---

### 第 15 步：渠道管理

```bash
# 查看渠道
curl -s http://localhost:8000/api/admin/channels \
  -H "Authorization: Bearer $TOKEN"

# 新增渠道
curl -s -X POST http://localhost:8000/api/admin/channels \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"code": "wechat_mp", "name": "微信公众号", "description": "菜单栏扫码入口"}'

# 生成这个渠道的二维码
curl -o wechat_qr.png http://localhost:8000/api/public/channels/wechat_mmp/qr
```

---

### 第 16 步：案例管理

```bash
# 查看案例
curl -s http://localhost:8000/api/admin/cases \
  -H "Authorization: Bearer $TOKEN" | python -c "import sys,json; [print(f'{c[\"title\"]} [{c[\"industry\"]}] {c[\"priority_tag\"]}') for c in json.load(sys.stdin)]"

# 新增案例
curl -s -X POST http://localhost:8000/api/admin/cases \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"title": "智能排产优化", "industry": "制造业", "function_area": "生产调度", "module_code": "M06", "description": "基于历史订单数据...", "expected_benefit": "减少空闲时间20%"}'
```

---

### 第 17 步：用户管理（仅 admin）

```bash
# 新增后台用户
curl -s -X POST http://localhost:8000/api/admin/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"email": "sales@test.com", "name": "销售小李", "role": "sales", "password": "Test1234!"}'

# 查看所有用户
curl -s http://localhost:8000/api/admin/users \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

---

## 四、一键测试脚本

把下面这几行存为 `test_api.sh`，跑一遍：

```bash
#!/bin/bash
BASE=http://localhost:8000

echo "=== 1. 健康检查 ==="
curl -s $BASE/api/health | python -m json.tool

echo -e "\n=== 2. 创建会话 ==="
SESSION=$(curl -s -X POST $BASE/api/public/sessions -H "Content-Type: application/json" -d '{"source_code":"test"}' | python -c "import sys,json; print(json.load(sys.stdin)['session_token'])")
echo "SESSION: $SESSION"

echo -e "\n=== 3. 提交企业信息 ==="
RES=$(curl -s -X POST $BASE/api/public/leads -H "Content-Type: application/json" -d "{\"session_token\":\"$SESSION\",\"company_name\":\"测试公司\",\"industry\":\"制造业\",\"company_size\":\"200-1000人\",\"contact_name\":\"测试\",\"position\":\"CEO\",\"phone\":\"13800138000\",\"privacy_accepted\":true,\"contact_authorized\":true}")
SID=$(echo $RES | python -c "import sys,json; print(json.load(sys.stdin)['submission_id'])")
echo "SUBMISSION_ID: $SID"

echo -e "\n=== 4. 提交问卷（全 4 分）==="
ANSWERS="["
for i in $(seq 1 68); do
  [ $i -gt 1 ] && ANSWERS="$ANSWERS,"
  ANSWERS="$ANSWERS{\"question_id\":$i,\"score\":4}"
done
ANSWERS="$ANSWERS]"
echo "提交中（等待 AI 生成，最多 45 秒）..."
R=$(curl -s -X POST $BASE/api/public/submissions/$SID/submit -H "Content-Type: application/json" -d "{\"answers\":$ANSWERS}")
TOKEN=$(echo $R | python -c "import sys,json; print(json.load(sys.stdin)['report']['public_token'])")
echo "报告 token: $TOKEN"

echo -e "\n=== 5. 管理员登录 ==="
ADMIN_TOKEN=$(curl -s -X POST $BASE/api/admin/auth/login -H "Content-Type: application/json" -d '{"email":"admin@example.com","password":"Admin123!"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo -e "\n=== 6. 统计看板 ==="
curl -s $BASE/api/admin/analytics/summary -H "Authorization: Bearer $ADMIN_TOKEN" | python -m json.tool

echo -e "\n=== 全部通过！==="
echo "报告链接: http://localhost:5173/report/$TOKEN"
```
