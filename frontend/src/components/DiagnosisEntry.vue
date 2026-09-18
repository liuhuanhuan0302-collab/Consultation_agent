<script setup lang="ts">
import { ArrowUpRight, FileText, Users } from "lucide-vue-next";

import { appUrl } from "../utils/appPaths";

function withSource(path: string) {
  const source = new URLSearchParams(window.location.search).get("source");
  if (!source) return appUrl(path);
  return `${appUrl(path)}?source=${encodeURIComponent(source)}`;
}

const enterpriseUrl = withSource("/enterprise/");
const organizationUrl = appUrl("/organization/");
const brandLogoUrl = `${import.meta.env.BASE_URL}brand-logo-horizontal.webp`;
</script>

<template>
  <main class="client-shell diagnosis-entry-v2">
    <section class="diagnosis-panel diagnosis-stage">
      <nav class="diagnosis-nav" aria-label="诊断入口">
        <img class="diagnosis-brand-logo" :src="brandLogoUrl" alt="优鲲智能 U-KUN AI" />
        <span class="diagnosis-nav-caption">企业诊断&nbsp;&nbsp;/&nbsp;&nbsp;组织诊断</span>
      </nav>

      <div class="diagnosis-stage-content">
        <header class="diagnosis-hero">
          <p class="diagnosis-intro">根据你的角色选择合适的诊断方式，开始填写</p>
          <h1>选择诊断类型</h1>
        </header>

        <div class="diagnosis-picker" role="group" aria-label="请选择诊断类型">
          <a class="diagnosis-choice" :href="enterpriseUrl">
            <div class="diagnosis-choice-head">
              <span class="diagnosis-choice-icon"><FileText :size="24" /></span>
              <span class="diagnosis-choice-index">01</span>
            </div>
            <div class="diagnosis-choice-copy">
              <p>Enterprise Diagnosis</p>
              <h2>企业诊断</h2>
              <span>填写企业信息并完成企业 AI 能力自测，获取原有企业诊断报告。</span>
            </div>
            <span class="diagnosis-choice-action">开始企业诊断 <ArrowUpRight :size="17" /></span>
          </a>

          <a class="diagnosis-choice diagnosis-choice--organization" :href="organizationUrl">
            <div class="diagnosis-choice-head">
              <span class="diagnosis-choice-icon"><Users :size="24" /></span>
              <span class="diagnosis-choice-index">02</span>
            </div>
            <div class="diagnosis-choice-copy">
              <p>Organization Diagnosis</p>
              <h2>组织诊断</h2>
              <span>以员工视角反馈组织体验，完成 68 题组织诊断问卷。</span>
            </div>
            <span class="diagnosis-choice-action">开始组织诊断 <ArrowUpRight :size="17" /></span>
          </a>
        </div>
      </div>
    </section>
  </main>
</template>
