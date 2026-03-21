<script setup lang="ts">
import api from "@/api";
import type {
  ApiCostsResponse,
  DailyCostsResponse,
} from "@zhixi/openapi-client";
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

const activeTab = ref(0);
const loading = ref(true);
const error = ref<string | null>(null);
const costsData = ref<ApiCostsResponse | null>(null);
const dailyData = ref<DailyCostsResponse | null>(null);

async function loadData() {
  loading.value = true;
  error.value = null;
  try {
    const [costsResp, dailyResp] = await Promise.all([
      api.get<ApiCostsResponse>("/dashboard/api-costs"),
      api.get<DailyCostsResponse>("/dashboard/api-costs/daily"),
    ]);
    costsData.value = costsResp.data;
    dailyData.value = dailyResp.data;
  } catch {
    error.value = "加载失败，下拉刷新重试";
  } finally {
    loading.value = false;
  }
}

function formatCost(cost: number | null | undefined): string {
  return `$${(cost ?? 0).toFixed(4)}`;
}

onMounted(loadData);
</script>

<template>
  <div class="zx-page costs-page">
    <van-nav-bar title="API 成本监控" left-arrow @click-left="router.back()" />

    <van-pull-refresh v-model="loading" @refresh="loadData">
      <van-notice-bar
        :color="'var(--zx-info)'"
        :background="'var(--zx-info-bg)'"
        left-icon="info-o"
        text="费用为估算值，实际费用以服务商账单为准"
      />

      <!-- 加载失败 -->
      <div v-if="!loading && error" class="empty-state">
        <van-empty :description="error" image="error" />
      </div>

      <div v-else class="zx-page-content">
        <!-- 今日 / 本月切换 -->
        <van-tabs v-model:active="activeTab" class="section-gap">
          <van-tab title="今日">
            <div class="cost-highlight">
              <span class="cost-label">总费用（估算）</span>
              <span class="cost-value">{{ formatCost(costsData?.today?.total_cost ?? 0) }}</span>
            </div>
            <van-cell-group inset>
              <van-cell
                v-for="svc in costsData?.today?.by_service ?? []"
                :key="svc.service"
                :title="svc.service"
                :label="`${svc.call_count}次调用 · ${svc.total_tokens} tokens`"
                :value="formatCost(svc.estimated_cost)"
              />
              <van-cell
                v-if="!costsData?.today?.by_service?.length"
                title="今日暂无调用记录"
              />
            </van-cell-group>
          </van-tab>

          <van-tab title="本月">
            <div class="cost-highlight">
              <span class="cost-label">总费用（估算）</span>
              <span class="cost-value">{{ formatCost(costsData?.this_month?.total_cost ?? 0) }}</span>
            </div>
            <van-cell-group inset>
              <van-cell
                v-for="svc in costsData?.this_month?.by_service ?? []"
                :key="svc.service"
                :title="svc.service"
                :label="`${svc.call_count}次调用 · ${svc.total_tokens} tokens`"
                :value="formatCost(svc.estimated_cost)"
              />
              <van-cell
                v-if="!costsData?.this_month?.by_service?.length"
                title="本月暂无调用记录"
              />
            </van-cell-group>
          </van-tab>
        </van-tabs>

        <!-- 30 天趋势 -->
        <p class="zx-section-title">近 30 天趋势</p>
        <van-cell-group inset>
          <van-cell
            v-for="day in dailyData?.days ?? []"
            :key="day.date"
            :title="day.date"
            :value="formatCost(day.total_cost)"
          >
            <template #label>
              <span v-if="day.claude_cost > 0">Claude {{ formatCost(day.claude_cost) }}</span>
              <span v-if="day.x_cost > 0"> · X {{ formatCost(day.x_cost) }}</span>
              <span v-if="day.gemini_cost > 0"> · Gemini {{ formatCost(day.gemini_cost) }}</span>
            </template>
          </van-cell>
          <van-cell
            v-if="!dailyData?.days?.length"
            title="暂无成本记录"
          />
        </van-cell-group>
      </div>
    </van-pull-refresh>
  </div>
</template>

<style scoped>
.empty-state {
  padding-top: 20vh;
}

.section-gap {
  margin-bottom: var(--zx-space-base);
}

.cost-highlight {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: var(--zx-space-lg) var(--zx-space-base) var(--zx-space-md);
}

.cost-label {
  font-size: var(--zx-text-sm);
  color: var(--zx-text-tertiary);
}

.cost-value {
  font-family: var(--zx-font-display);
  font-size: var(--zx-text-2xl);
  font-weight: 700;
  color: var(--zx-text-primary);
}
</style>
