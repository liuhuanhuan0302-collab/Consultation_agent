<script setup lang="ts">
import { computed, ref, watch, nextTick, shallowRef } from "vue";
import { Bar, Radar } from "vue-chartjs";
import {
  Chart as ChartJS,
  BarController,
  BarElement,
  CategoryScale,
  Filler,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  RadialLinearScale,
  RadarController,
  Tooltip,
} from "chart.js";
import type { TooltipItem } from "chart.js";
import type { DimensionScore } from "../types";

ChartJS.register(
  BarController,
  BarElement,
  CategoryScale,
  LinearScale,
  RadarController,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
);

const props = defineProps<{
  dimensions: DimensionScore[];
}>();

const chartKey = ref(0);

watch(
  () => props.dimensions,
  () => {
    chartKey.value += 1;
  },
  { deep: true },
);

const sorted = computed(() =>
  [...props.dimensions].sort((a, b) => a.score_rate - b.score_rate),
);

function shortName(name: string): string {
  const colon = name.indexOf("：");
  if (colon === -1) return name;
  return name.slice(0, colon);
}

function rateColor(rate: number): string {
  if (rate < 0.25) return "#ef4444";
  if (rate < 0.5) return "#f59e0b";
  if (rate < 0.75) return "#3b82f6";
  return "#22c55e";
}

function rateBg(rate: number): string {
  if (rate < 0.25) return "rgba(239,68,68,0.20)";
  if (rate < 0.5) return "rgba(245,158,11,0.20)";
  if (rate < 0.75) return "rgba(59,130,246,0.18)";
  return "rgba(34,197,94,0.18)";
}

function rateLabel(rate: number): string {
  if (rate < 0.25) return "高风险";
  if (rate < 0.5) return "较弱";
  if (rate < 0.75) return "良好";
  return "优秀";
}

function tooltipValue(raw: unknown): number {
  return typeof raw === "number" ? raw : Number(raw) || 0;
}

const barData = computed(() => ({
  labels: sorted.value.map((d) => shortName(d.module_name)),
  datasets: [
    {
      label: "得分率",
      data: sorted.value.map((d) => Math.round(d.score_rate * 100)),
      backgroundColor: sorted.value.map((d) => rateBg(d.score_rate)),
      borderColor: sorted.value.map((d) => rateColor(d.score_rate)),
      borderWidth: 1.5,
      borderRadius: 4,
      barPercentage: 0.7,
    },
  ],
}));

const barOptions = {
  indexAxis: "y" as const,
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration: 600 },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: "rgba(15,23,42,0.92)",
      titleFont: { size: 13 },
      bodyFont: { size: 12 },
      padding: 10,
      cornerRadius: 6,
      callbacks: {
        title: (ctx: TooltipItem<"bar">[]) => {
          const idx = ctx[0]?.dataIndex;
          if (idx === undefined) return "";
          return sorted.value[idx]?.module_name ?? "";
        },
        label: (ctx: TooltipItem<"bar">) => {
          const idx = ctx.dataIndex;
          const dim = sorted.value[idx];
          return `${tooltipValue(ctx.raw)}% · ${dim ? rateLabel(dim.score_rate) : ""}`;
        },
      },
    },
  },
  scales: {
    x: {
      min: 0,
      max: 100,
      ticks: {
        callback: (v: string | number) => `${v}%`,
        font: { size: 11 },
        color: "#94a3b8",
      },
      grid: { color: "#f1f5f9" },
    },
    y: {
      grid: { display: false },
      ticks: {
        font: { size: 12, weight: 500 },
        color: "#475569",
      },
    },
  },
};

const radarData = computed(() => ({
  labels: sorted.value.map((d) => shortName(d.module_name)),
  datasets: [
    {
      label: "得分率",
      data: sorted.value.map((d) => Math.round(d.score_rate * 100)),
      backgroundColor: "rgba(59,130,246,0.15)",
      borderColor: "#3b82f6",
      borderWidth: 2.5,
      pointBackgroundColor: sorted.value.map((d) => rateColor(d.score_rate)),
      pointBorderColor: "#ffffff",
      pointBorderWidth: 2,
      pointRadius: 5,
      pointHoverRadius: 8,
      pointHoverBorderWidth: 3,
    },
  ],
}));

const radarOptions = {
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration: 600 },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: "rgba(15,23,42,0.92)",
      titleFont: { size: 13 },
      bodyFont: { size: 12 },
      padding: 10,
      cornerRadius: 6,
      callbacks: {
        title: () => "",
        label: (ctx: TooltipItem<"radar">) => {
          const label = String(ctx.label ?? "");
          const dim = sorted.value.find((d) => shortName(d.module_name) === label);
          const name = dim?.module_name ?? label;
          return `${name}: ${tooltipValue(ctx.raw)}% · ${dim ? rateLabel(dim.score_rate) : ""}`;
        },
      },
    },
  },
  scales: {
    r: {
      beginAtZero: true,
      min: 0,
      max: 100,
      ticks: {
        stepSize: 20,
        backdropColor: "transparent",
        font: { size: 10 },
        color: "#94a3b8",
      },
      pointLabels: {
        font: { size: 12, weight: 500 },
        color: "#475569",
      },
      grid: { color: "#e2e8f0" },
      angleLines: { color: "#e2e8f0" },
    },
  },
};
</script>

<template>
  <div class="chart-grid" v-show="dimensions.length">
    <div class="chart-card chart-card--bar">
      <div class="chart-card-header">
        <span class="card-accent"></span>
        <h3>十维能力成熟度排行</h3>
        <p class="chart-card-sub">各维度得分率从低到高排列，快速定位薄弱环节</p>
      </div>
      <div class="chart-wrapper">
        <Bar :key="'bar-' + chartKey" :data="barData" :options="barOptions" />
      </div>
    </div>
    <div class="chart-card chart-card--radar">
      <div class="chart-card-header">
        <span class="card-accent" style="background:linear-gradient(135deg,#8b5cf6,#6366f1)"></span>
        <h3>AI 转型能力雷达图</h3>
        <p class="chart-card-sub">十维度全景扫描，面积越大代表能力越均衡</p>
      </div>
      <div class="chart-wrapper">
        <Radar :key="'radar-' + chartKey" :data="radarData" :options="radarOptions" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.chart-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin: 24px 0;
}

.chart-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 24px 24px 18px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
}

.chart-card-header {
  margin-bottom: 10px;
}

.card-accent {
  display: block;
  width: 32px;
  height: 4px;
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
  border-radius: 2px;
  margin-bottom: 14px;
}

.chart-card h3 {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 4px;
  letter-spacing: -0.01em;
}

.chart-card-sub {
  font-size: 12px;
  color: #94a3b8;
  margin: 0;
}

.chart-wrapper {
  position: relative;
  width: 100%;
  height: 370px;
}

@media (max-width: 820px) {
  .chart-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .chart-wrapper {
    height: 300px;
  }

  .chart-card {
    padding: 18px 16px 14px;
  }
}
</style>
