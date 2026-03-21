<script setup lang="ts">
import api from "@/api";
import { getStatus } from "@/utils/status";
import type { DashboardOverviewResponse } from "@zhixi/openapi-client";
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const loading = ref(true);
const data = ref<DashboardOverviewResponse | null>(null);
const error = ref<string | null>(null);

async function loadData() {
  loading.value = true;
  error.value = null;
  try {
    const resp = await api.get<DashboardOverviewResponse>(
      "/dashboard/overview",
    );
    data.value = resp.data;
  } catch {
    error.value = "加载失败，下拉刷新重试";
  } finally {
    loading.value = false;
  }
}

onMounted(loadData);
</script>

<template>
  <div class="dashboard-page">
    <van-nav-bar title="智曦管理后台" />

    <van-pull-refresh v-model="loading" @refresh="loadData">
      <!-- 错误态 -->
      <van-empty v-if="!loading && error" :description="error" image="error" />

      <template v-else>
      <!-- 告警 -->
      <template v-if="data?.alerts?.length">
        <van-notice-bar
          v-for="(alert, idx) in data.alerts"
          :key="idx"
          color="#ee0a24"
          background="#fff0f0"
          left-icon="warning-o"
          :text="`[${alert.job_type}] ${alert.error_message || '任务失败'}`"
          class="alert-gap"
        />
      </template>

      <div class="page-content">
        <!-- Pipeline 状态 -->
        <van-cell-group inset title="今日状态" class="section-gap">
          <van-cell title="Pipeline">
            <template #value>
              <van-tag
                :type="getStatus(data?.pipeline_status?.status).type"
              >
                {{ getStatus(data?.pipeline_status?.status).text }}
              </van-tag>
            </template>
          </van-cell>
          <van-cell title="日报">
            <template #value>
              <van-tag
                :type="getStatus(data?.digest_status?.status).type"
              >
                {{ getStatus(data?.digest_status?.status).text }}
              </van-tag>
              <span
                v-if="data?.digest_status?.item_count"
                class="meta-text"
              >
                {{ data.digest_status.item_count }}条 v{{
                  data.digest_status.version
                }}
              </span>
            </template>
          </van-cell>
        </van-cell-group>

        <!-- 低内容提示 (US-045) -->
        <van-notice-bar
          v-if="data?.digest_status?.low_content_warning"
          color="#ed6a0c"
          background="#fffbe8"
          left-icon="info-o"
          :text="`今日资讯较少（${data.digest_status.item_count}条）`"
          class="section-gap"
        />

        <!-- 成本卡片 -->
        <van-cell-group inset title="今日 API 成本" class="section-gap">
          <template #title>
            <div class="cost-title">
              <span>今日 API 成本</span>
              <span class="cost-detail-link" @click="router.push({ name: 'costs' })">查看详情 &gt;</span>
            </div>
          </template>
          <van-cell
            title="总费用（估算）"
            :value="`$${data?.today_cost?.total_cost?.toFixed(4) ?? '0.0000'}`"
          />
          <van-cell
            v-for="svc in data?.today_cost?.by_service ?? []"
            :key="svc.service"
            :title="svc.service"
            :label="`${svc.call_count}次调用 · ${svc.total_tokens} tokens`"
            :value="`$${(svc.estimated_cost ?? 0).toFixed(4)}`"
          />
          <van-cell
            v-if="!data?.today_cost?.by_service?.length"
            title="暂无调用记录"
          />
        </van-cell-group>

        <!-- 操作按钮 -->
        <van-button
          type="primary"
          block
          size="large"
          class="section-gap"
          @click="router.push({ name: 'digest' })"
        >
          审核今日内容
        </van-button>

        <van-grid :column-num="3" :gutter="10" class="section-gap">
          <van-grid-item icon="friends-o" text="大V管理" @click="router.push({ name: 'accounts' })" />
          <van-grid-item icon="setting-o" text="系统设置" @click="router.push({ name: 'settings' })" />
          <van-grid-item icon="description" text="系统日志" @click="router.push({ name: 'logs' })" />
        </van-grid>

        <!-- 近 7 天记录 -->
        <van-cell-group inset title="近 7 天推送记录">
          <van-cell
            v-for="record in data?.recent_7_days ?? []"
            :key="record.date"
            :title="record.date"
            :label="`${record.item_count}条 · v${record.version}`"
          >
            <template #value>
              <van-tag
                :type="getStatus(record.status).type"
              >
                {{ getStatus(record.status).text }}
              </van-tag>
            </template>
          </van-cell>
          <van-cell
            v-if="!data?.recent_7_days?.length"
            title="暂无推送记录"
          />
        </van-cell-group>
      </div>
      </template>
    </van-pull-refresh>
  </div>
</template>

<style scoped>
.alert-gap {
  margin-bottom: 4px;
}

.page-content {
  padding: 12px;
}

.section-gap {
  margin-bottom: 12px;
}

.meta-text {
  margin-left: 8px;
  color: #969799;
  font-size: 12px;
}

.cost-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.cost-detail-link {
  color: #1989fa;
  font-size: 12px;
  cursor: pointer;
}
</style>
