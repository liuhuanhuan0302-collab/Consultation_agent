import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { DIAGNOSIS_URL } from "../config.js";

const htmlPath = new URL("../index.html", import.meta.url);
const html = await readFile(htmlPath, "utf8");

test("AI 能力测评位于解决方案和转型路径之间", () => {
  const solutionsIndex = html.indexOf('id="solutions"');
  const assessmentIndex = html.indexOf('id="ai-assessment"');
  const scenesIndex = html.indexOf('id="scenes"');

  assert.ok(solutionsIndex < assessmentIndex);
  assert.ok(assessmentIndex < scenesIndex);
});

test("AI 能力测评使用有效链接和本地二维码资源", () => {
  assert.doesNotThrow(() => new URL(DIAGNOSIS_URL));
  assert.match(html, /data-component="AiAssessmentSection"/);
  assert.match(html, /assets\/ai-assessment-qr\.png/);
});
