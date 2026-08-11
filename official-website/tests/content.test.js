import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { selectBusinessModule, selectMetrics, toInternalHref } from "../adapters/site-content-adapter.js";
import { fetchSiteContent } from "../services/site-content.js";
import { getModuleStateContent } from "../ui/module-state.js";
import { getNextTabIndex, setUrlParameter } from "../utils/interactions.js";
import {
  formatDate,
  formatEmpty,
  formatMetric,
  formatMoney,
  formatPercent,
  formatStatus,
  formatTime,
  formatUserName,
  truncateText,
} from "../utils/formatters.js";

const contentPath = new URL("../public/data/site-content.json", import.meta.url);
const content = JSON.parse(await readFile(contentPath, "utf8"));

test("真实内容数据包含 PPT 中的核心事实", () => {
  assert.equal(content.facts.scenarioCount, 500);
  assert.equal(content.facts.agentAvailability, "7×24");
  assert.equal(content.serviceChain.length, 3);
  assert.equal(content.transformationStages.length, 5);
  assert.equal(content.contact.phone, null);
  assert.equal(content.contact.email, null);
});

test("统计选择器从真实数组计算阶段数量", () => {
  const metrics = selectMetrics(content);
  assert.equal(metrics.find((item) => item.key === "serviceChain")?.value, 3);
  assert.equal(metrics.find((item) => item.key === "transformation")?.value, 5);
  assert.equal(formatMetric(metrics[0]), "500+");
});

test("业务模块选择和站内链接校验具备兜底", () => {
  assert.equal(selectBusinessModule(content, "agent-solution")?.name, "AI Agent");
  assert.equal(toInternalHref("#solutions"), "#solutions");
  assert.equal(toInternalHref("https://invalid.example"), "#top");
});

test("统一格式化方法覆盖常用数据类型与空值", () => {
  assert.notEqual(formatDate("2026-07-21"), "资料待补充");
  assert.notEqual(formatTime("2026-07-21T08:30:00+08:00"), "资料待补充");
  assert.match(formatMoney(1200), /1,200/);
  assert.equal(formatPercent(0.256), "26%");
  assert.equal(formatUserName(""), "未设置名称");
  assert.equal(formatEmpty(null), "资料待补充");
  assert.equal(formatStatus("active", { active: "进行中" }), "进行中");
  assert.equal(truncateText("优鲲智能企业数智化", 5), "优鲲智能…");
});

test("内容读取支持成功、失败和字段缺失状态", async () => {
  const successFetch = async () => ({ ok: true, json: async () => content });
  const failedFetch = async () => ({ ok: false, json: async () => ({}) });
  const emptyFetch = async () => ({ ok: true, json: async () => ({}) });

  assert.equal((await fetchSiteContent({ url: "/content", fetchImpl: successFetch })).company.name, "优鲲智能");
  await assert.rejects(fetchSiteContent({ url: "/content", fetchImpl: failedFetch }), /CONTENT_UNAVAILABLE/);
  await assert.rejects(fetchSiteContent({ url: "/content", fetchImpl: emptyFetch }), /MISSING_REQUIRED_CONTENT/);
});

test("模块状态覆盖加载、成功、空数据、失败和重试", () => {
  assert.equal(getModuleStateContent("loading").ariaBusy, true);
  assert.equal(getModuleStateContent("success").message, "");
  assert.match(getModuleStateContent("empty").message, /整理中/);
  assert.equal(getModuleStateContent("error").canRetry, true);
});

test("Tab 键盘导航循环切换并保留现有 URL 参数", () => {
  assert.equal(getNextTabIndex(0, 4, "ArrowLeft"), 3);
  assert.equal(getNextTabIndex(3, 4, "ArrowRight"), 0);
  assert.equal(getNextTabIndex(2, 4, "Home"), 0);
  assert.equal(getNextTabIndex(1, 4, "End"), 3);
  assert.equal(
    setUrlParameter("https://example.com/?source=nav#industries", "service", "ai-training"),
    "/?source=nav&service=ai-training#industries",
  );
});
