<script setup lang="ts">
import { Check, ChevronLeft, ChevronRight, Users } from "lucide-vue-next";

import { useOrganizationQuestionnaire } from "../composables/useOrganizationQuestionnaire";

const brandLogoUrl = `${import.meta.env.BASE_URL}brand-logo-horizontal.webp`;

const {
  step,
  info,
  modules,
  moduleIndex,
  suggestions,
  suggestionsLoading,
  suggestionsOpen,
  autocompleteMessage,
  busy,
  draftSaving,
  draftSaved,
  error,
  missingNotice,
  questions,
  currentModule,
  answeredCount,
  progress,
  allAnswered,
  parseOptionLabels,
  getGlobalIndex,
  moduleDone,
  isAnswerSelected,
  handleCompanyInput,
  handleCompanyFocus,
  handleCompanyBlur,
  selectCompany,
  startOrganization,
  selectAnswer,
  goToModule,
  goNextModule,
  goPrevModule,
  submitOrganization,
  finish,
} = useOrganizationQuestionnaire();
</script>

<template>
  <main class="client-shell organization-shell organization-shell-v2">
    <section class="diagnosis-panel organization-panel organization-stage">
      <nav class="organization-nav" aria-label="当前诊断类型">
        <img class="organization-brand-logo" :src="brandLogoUrl" alt="优鲲智能 U-KUN AI" />
        <span class="organization-nav-caption">组织诊断 · ORGANIZATION</span>
      </nav>

      <div class="organization-stage-content" :class="`organization-stage-content--${step}`">
        <header class="client-header organization-hero">
          <div class="organization-hero-copy">
            <p class="organization-intro">从组织成员视角，记录真实的工作体验与反馈</p>
            <h1>组织诊断</h1>
            <p class="organization-hero-caption">填写基本信息，开启 68 题组织体验问卷</p>
          </div>
          <span class="organization-hero-icon" aria-hidden="true"><Users :size="28" /></span>
        </header>

        <div v-if="error" class="alert organization-alert" role="alert">{{ error }}</div>

        <form v-if="step === 'info'" class="form-grid organization-info-form" @submit.prevent="startOrganization">
          <div class="organization-form-field organization-company-field">
            <label for="organization-company-name">企业名称 <span class="required-mark">*</span></label>
            <input
              id="organization-company-name"
              v-model="info.company_name_input"
              required
              autocomplete="organization"
              placeholder="请输入企业名称"
              @input="handleCompanyInput"
              @focus="handleCompanyFocus"
              @blur="handleCompanyBlur"
            />
            <div v-if="suggestionsOpen" class="company-suggestions" role="listbox" aria-label="企业名称候选">
              <div v-if="suggestionsLoading" class="company-suggestions-message">正在匹配已有企业...</div>
              <button
                v-for="item in suggestions"
                :key="item.company_name"
                type="button"
                role="option"
                class="company-suggestion"
                @mousedown.prevent
                @click="selectCompany(item.company_name)"
              >
                {{ item.company_name }}
              </button>
              <div v-if="!suggestionsLoading && autocompleteMessage" class="company-suggestions-message">
                {{ autocompleteMessage }}
              </div>
            </div>
            <span class="field-hint">输入至少 2 个字后自动匹配已有企业；没有匹配也可以继续。</span>
          </div>
          <div class="organization-form-field">
            <label for="organization-respondent-name">姓名 <span class="required-mark">*</span></label>
            <input id="organization-respondent-name" v-model="info.respondent_name" required autocomplete="name" placeholder="请输入姓名" />
          </div>
          <div class="organization-form-field">
            <label for="organization-department">部门 <span class="required-mark">*</span></label>
            <input id="organization-department" v-model="info.department" required placeholder="例如：信息技术部" />
          </div>
          <div class="organization-form-field">
            <label for="organization-position">职位 <span class="required-mark">*</span></label>
            <input id="organization-position" v-model="info.position" required placeholder="例如：部门负责人" />
          </div>
          <button class="primary wide organization-start-button" :disabled="busy" type="submit">
            <span>{{ busy ? "准备中..." : "开始组织诊断" }}</span>
            <ChevronRight v-if="!busy" :size="18" />
          </button>
        </form>

        <section v-else-if="step === 'questionnaire' && currentModule" class="questionnaire organization-questionnaire">
        <div class="progress-row">
          <div>
            <strong class="progress-title">
              <span class="phase-badge">阶段 {{ moduleIndex + 1 }} / {{ modules.length }}</span>
              {{ currentModule.name }}
              <span class="score-badge">{{ currentModule.max_score }}分</span>
            </strong>
            <span>{{ currentModule.description }}</span>
            <span v-if="draftSaving" class="draft-indicator">正在保存草稿...</span>
            <span v-else-if="draftSaved" class="draft-indicator">草稿已保存</span>
          </div>
          <strong>{{ answeredCount }}/{{ questions.length }}</strong>
        </div>
        <div class="progress-bar"><span :style="{ width: `${progress * 100}%` }" /></div>

        <div class="module-nav">
          <button
            v-for="(module, index) in modules"
            :key="module.id"
            type="button"
            class="module-dot"
            :class="{ active: index === moduleIndex, done: moduleDone(module) }"
            :aria-label="`跳转到阶段 ${index + 1}：${module.name}`"
            @click="goToModule(index)"
          >
            {{ index + 1 }}
          </button>
        </div>

        <div v-if="missingNotice" class="alert organization-missing-notice" role="status">{{ missingNotice }}</div>

        <div class="question-list">
          <div v-for="(question, questionIndex) in currentModule.questions" :id="`organization-question-${question.id}`" :key="question.id" class="question-row">
            <div class="question-copy">
              <p class="question-text">{{ getGlobalIndex(currentModule, questionIndex) }}. {{ question.text }}</p>
              <div class="score-options">
                <label
                  v-for="option in parseOptionLabels(question.option_text)"
                  :key="option.value"
                  class="score-option"
                  :class="{ selected: isAnswerSelected(question.id, option.value) }"
                >
                  <input
                    class="score-radio"
                    type="radio"
                    :name="`organization-question-${question.id}`"
                    :checked="isAnswerSelected(question.id, option.value)"
                    @change="selectAnswer(question.id, option.value)"
                  />
                  <span class="option-score">{{ option.value }}</span>
                  <span class="option-label">{{ option.label }}</span>
                  <span class="option-check"><Check :size="16" /></span>
                </label>
              </div>
            </div>
          </div>
        </div>

        <footer class="step-actions">
          <button class="secondary" type="button" :disabled="moduleIndex === 0 || busy" @click="goPrevModule"><ChevronLeft :size="18" /> 上一组</button>
          <span class="step-hint">{{ moduleIndex + 1 }} / {{ modules.length }}</span>
          <button v-if="moduleIndex < modules.length - 1" class="primary" type="button" :disabled="draftSaving || busy" @click="goNextModule">下一组 <ChevronRight :size="18" /></button>
          <button v-else class="primary" type="button" :disabled="busy || !allAnswered" @click="submitOrganization">
            {{ busy ? "提交中..." : allAnswered ? "提交组织诊断" : `还剩 ${questions.length - answeredCount} 题未答` }}
          </button>
        </footer>
        </section>

        <section v-else-if="step === 'success'" class="submitted-card organization-success-card">
          <div class="submitted-icon"><Check :size="34" /></div>
          <h2>提交成功</h2>
          <p>感谢您完成本次组织诊断。</p>
          <p>您的反馈已成功保存，将用于后续组织综合分析。</p>
          <button class="secondary" type="button" @click="finish">完成</button>
        </section>
      </div>
    </section>
  </main>
</template>
