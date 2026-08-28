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
const orderedDimensions = computed(() => [...props.dimensions]);

function shortName(name: string): string {
  const colon = name.indexOf("：");
  if (colon === -1) return name;
  return name.slice(0, colon);
}

function rateColor(rate: number): string {
  return rate < 0.5 ? "#c00000" : "#17365d";
}

function rateBg(rate: number): string {
  return rate < 0.5 ? "rgba(192,0,0,0.10)" : "rgba(23,54,93,0.12)";
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
      borderRadius: 0,
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
      backgroundColor: "rgba(23,54,93,0.96)",
      titleFont: { size: 13 },
      bodyFont: { size: 12 },
      padding: 10,
      cornerRadius: 0,
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
        color: "#666666",
      },
      grid: { color: "#d9e2f3" },
    },
    y: {
      grid: { display: false },
      ticks: {
        font: { size: 12, weight: 500 },
        color: "#666666",
      },
    },
  },
};

const radarData = computed(() => ({
  labels: orderedDimensions.value.map((d) => shortName(d.module_name)),
  datasets: [
    {
      label: "得分率",
      data: orderedDimensions.value.map((d) => Math.round(d.score_rate * 100)),
      backgroundColor: "rgba(23,54,93,0.13)",
      borderColor: "#17365d",
      borderWidth: 2.5,
      pointBackgroundColor: orderedDimensions.value.map((d) => rateColor(d.score_rate)),
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
      backgroundColor: "rgba(23,54,93,0.96)",
      titleFont: { size: 13 },
      bodyFont: { size: 12 },
      padding: 10,
      cornerRadius: 0,
      callbacks: {
        title: () => "",
        label: (ctx: TooltipItem<"radar">) => {
          const label = String(ctx.label ?? "");
          const dim = orderedDimensions.value.find((d) => shortName(d.module_name) === label);
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
        color: "#666666",
      },
      pointLabels: {
        font: { size: 12, weight: 500 },
        color: "#666666",
      },
      grid: { color: "#d9e2f3" },
      angleLines: { color: "#d9e2f3" },
    },
  },
};

</script>

<template>
  <div class="chart-grid" v-show="dimensions.length">
    <div class="chart-card chart-card--bar">
      <div class="chart-card-header">
        <h3>能力成熟度排行</h3>
        <p class="chart-card-sub">当前启用维度的得分率从低到高排列，快速定位薄弱环节</p>
      </div>
      <div class="chart-wrapper">
        <Bar :key="'bar-' + chartKey" :data="barData" :options="barOptions" />
      </div>
    </div>
    <div class="chart-card chart-card--radar">
      <div class="chart-card-header">
        <h3>AI 转型能力雷达图</h3>
        <p class="chart-card-sub">按当前启用维度生成，面积越大代表能力越均衡</p>
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
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  margin: 24px 0;
  min-width: 0;
  width: 100%;
}

.chart-card {
  background: #fff;
  border: 1px solid #d9e2f3;
  border-top: 1px solid #d9e2f3;
  border-radius: 0;
  box-shadow: none;
  min-width: 0;
  padding: 22px 22px 16px;
}

.chart-card-header {
  border-bottom: 1px solid #d9e2f3;
  margin-bottom: 10px;
  min-width: 0;
  padding-bottom: 9px;
}

.chart-card h3 {
  font-size: 16px;
  font-weight: 700;
  color: #2f5597;
  margin: 0 0 4px;
  letter-spacing: -0.01em;
}

.chart-card-sub {
  font-size: 12px;
  color: #666666;
  margin: 0;
}

.chart-wrapper {
  max-width: 100%;
  min-width: 0;
  overflow: hidden;
  position: relative;
  width: 100%;
  height: 370px;
}

.chart-wrapper canvas {
  display: block;
  max-width: 100% !important;
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
