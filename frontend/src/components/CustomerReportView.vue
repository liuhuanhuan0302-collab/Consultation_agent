<script setup lang="ts">
import { computed } from "vue";

import type { DimensionScore } from "../types";
import ReportCharts from "./ReportCharts.vue";

const props = defineProps<{
  companyName: string;
  reportId: number | null;
  createdAt: string | null;
  score: { total: number; max: number; rate: number } | null;
  dimensions: DimensionScore[];
  html: string;
  adminPreview?: boolean;
}>();

const normalizedCompany = computed(() => props.companyName.trim() || "企业");
const shortCompany = computed(() => normalizedCompany.value.replace(
  /(?:集团股份有限公司|集团有限责任公司|股份有限公司|有限责任公司|集团有限公司|有限公司)$/,
  "",
).trim() || normalizedCompany.value);
const titleLengthClass = computed(() => {
  const length = Array.from(shortCompany.value.replace(/\s+/g, "")).length;
  if (length > 16) return "hero-title--extra-long";
  if (length > 10) return "hero-title--long";
  return "";
});
const reportNumber = computed(() => props.reportId === null
  ? "RPT-UNKNOWN"
  : `RPT-${String(props.reportId).padStart(6, "0")}`);
const reportDate = computed(() => {
  if (!props.createdAt) return "未记录";
  const date = new Date(props.createdAt);
  if (Number.isNaN(date.getTime())) return "未记录";
  const parts = new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "numeric",
    day: "numeric",
    timeZone: "Asia/Shanghai",
  }).formatToParts(date);
  const value = (type: Intl.DateTimeFormatPartTypes) => parts.find((item) => item.type === type)?.value || "";
  return `${value("year")} 年 ${value("month")} 月 ${value("day")} 日`;
});
const scoreRate = computed(() => Math.max(0, Math.min(100, Math.round((props.score?.rate || 0) * 100))));
</script>

<template>
  <section :class="['customer-report-view', { 'customer-report-view--admin': adminPreview }]">
    <header class="report-hero report-a4-page report-cover-page">
      <div class="hero-content">
        <p class="hero-company">{{ normalizedCompany }}</p>
        <h1 :class="['hero-title', titleLengthClass]">
          <span>{{ shortCompany }} AI 原生转型</span>
          <span>诊断报告</span>
        </h1>
        <p class="hero-subtitle">从诊断共识走向可执行的 AI 转型路径</p>
        <div class="hero-rule"></div>
        <dl class="hero-meta">
          <div><dt>评估对象</dt><dd>{{ normalizedCompany }}</dd></div>
          <div><dt>报告类型</dt><dd>AI 原生企业转型诊断报告</dd></div>
          <div><dt>评估范围</dt><dd>企业 AI 原生能力成熟度与转型路径</dd></div>
          <div><dt>报告编号</dt><dd>{{ reportNumber }}</dd></div>
          <div><dt>出具日期</dt><dd>{{ reportDate }}</dd></div>
        </dl>
        <p class="hero-statement">让 AI 从局部工具走向企业级生产力</p>
        <slot name="cover-actions"></slot>
      </div>
    </header>

    <section class="report-a4-page report-body-page">
      <div class="report-page-header">{{ normalizedCompany }} | AI 原生转型诊断报告</div>
      <section v-if="score" class="report-score-overview">
        <h2>诊断结果概览</h2>
        <div class="report-score-strip">
          <div><span>诊断得分</span><strong>{{ score.total }} / {{ score.max }}</strong></div>
          <div><span>综合得分率</span><strong>{{ scoreRate }}%</strong></div>
        </div>
        <div class="report-score-progress" aria-hidden="true"><span :style="{ width: `${scoreRate}%` }"></span></div>
      </section>
      <ReportCharts v-if="dimensions.length" :dimensions="dimensions" />
      <article class="report-html report-document" data-body-style="reference_consulting_body_v2" v-html="html" />
      <div class="report-page-footer">企业 AI 转型诊断</div>
    </section>
  </section>
</template>
