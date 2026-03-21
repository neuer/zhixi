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
const costsData = ref<ApiCostsResponse | null>(null);
const dailyData = ref<DailyCostsResponse | null>(null);

async function loadData() {
  loading.value = true;
  try {
    const [costsResp, dailyResp] = await Promise.all([
      api.get<ApiCostsResponse>("/dashboard/api-costs"),
      api.get<DailyCostsResponse>("/dashboard/api-costs/daily"),
    ]);
    costsData.value = costsResp.data;
    dailyData.value = dailyResp.data;
  } catch {
    // 错误已由拦截器处理
  } finally {
    loading.value = false;
  }
}

function formatCost(cost: number): string {
  return `$${cost.toFixed(4)}`;
}

onMounted(loadData);
</script>

<template>
  <div class="costs-page">
    <van-nav-bar title="API 成本监控" left-arrow @click-left="router.back()" />

    <van-pull-refresh v-model="loading" @refresh="loadData">
      <van-notice-bar
        color="#1989fa"
        background="#ecf9ff"
        left-icon="info-o"
        text="费用为估算值，实际费用以服务商账单为准"
      />

      <div style="padding: 12px">
        <!-- 今日 / 本月切换 -->
        <van-tabs v-model:active="activeTab" style="margin-bottom: 12px">
          <van-tab title="今日">
            <van-cell-group inset style="margin-top: 12px">
              <van-cell
                title="总费用（估算）"
                :value="formatCost(costsData?.today?.total_cost ?? 0)"
              />
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
            <van-cell-group inset style="margin-top: 12px">
              <van-cell
                title="总费用（估算）"
                :value="formatCost(costsData?.this_month?.total_cost ?? 0)"
              />
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
        <van-cell-group inset title="近 30 天趋势">
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
