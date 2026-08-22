import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { DIAGNOSIS_URL, QR_CODE_URL } from "../config.js";

const htmlPath = new URL("../index.html", import.meta.url);
const html = await readFile(htmlPath, "utf8");

test("AI 能力测评位于解决方案和转型路径之间", () => {
  const solutionsIndex = html.indexOf('id="solutions"');
  const assessmentIndex = html.indexOf('id="ai-assessment"');
  const scenesIndex = html.indexOf('id="scenes"');

  assert.ok(solutionsIndex < assessmentIndex);
  assert.ok(assessmentIndex < scenesIndex);
});

test("AI 能力测评使用有效链接和后端实时二维码", () => {
  const diagnosisUrl = new URL(DIAGNOSIS_URL, "https://youyuexinxi.com.cn");
  assert.equal(diagnosisUrl.pathname, "/diagnosis/");
  assert.equal(diagnosisUrl.searchParams.get("source"), "OFFICIAL_WEBSITE");
  assert.equal(QR_CODE_URL, "/api/public/channels/OFFICIAL_WEBSITE/qr");
  assert.match(html, /data-component="AiAssessmentSection"/);
  assert.match(html, /data-assessment-qr/);
  assert.match(html, /api\/public\/channels\/OFFICIAL_WEBSITE\/qr/);
});

test("首页提供可关闭的创始人来信，并可进入官网", () => {
  assert.match(html, /data-founder-letter/);
  assert.match(html, /data-founder-letter-close/);
  assert.match(html, /进入官网/);
});

test("创始人来信保留完整的五个章节与结尾邀请", () => {
  assert.match(html, /1\.0 第一曲线/);
  assert.match(html, /2\.0 新的起点/);
  assert.match(html, /3\.0 泥土中生发梦想/);
  assert.match(html, /4\.0 带着成果踏上征途/);
  assert.match(html, /5\.0 星星之火，共同燎原/);
  assert.match(html, /帮助更多组织从传统组织走向真正的 AI 原生组织/);
});
