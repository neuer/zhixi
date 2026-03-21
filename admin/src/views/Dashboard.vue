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
  <div class="zx-page dashboard-page">
    <van-nav-bar title="智曦管理后台">
      <template #title>
        <span class="nav-brand">智曦管理后台</span>
      </template>
    </van-nav-bar>

    <van-pull-refresh v-model="loading" @refresh="loadData">
      <!-- 错误态 -->
      <van-empty v-if="!loading && error" :description="error" image="error" />

      <template v-else>
      <!-- 告警 -->
      <template v-if="data?.alerts?.length">
        <van-notice-bar
          v-for="(alert, idx) in data.alerts"
          :key="idx"
          :color="'var(--zx-danger)'"
          :background="'var(--zx-danger-bg)'"
          left-icon="warning-o"
          :text="`[${alert.job_type}] ${alert.error_message || '任务失败'}`"
          class="alert-gap"
        />
      </template>

      <div class="zx-page-content">
        <!-- 状态卡片 -->
        <div class="status-row">
          <div class="status-card">
            <span class="status-label">Pipeline</span>
            <van-tag
              :type="getStatus(data?.pipeline_status?.status).type"
              size="medium"
            >
              {{ getStatus(data?.pipeline_status?.status).text }}
            </van-tag>
          </div>
          <div class="status-card">
            <span class="status-label">日报</span>
            <div class="status-value">
              <van-tag
                :type="getStatus(data?.digest_status?.status).type"
                size="medium"
              >
                {{ getStatus(data?.digest_status?.status).text }}
              </van-tag>
              <span
                v-if="data?.digest_status?.item_count"
                class="zx-meta-text"
              >
                {{ data.digest_status.item_count }}条 v{{
                  data.digest_status.version
                }}
              </span>
            </div>
          </div>
        </div>

        <!-- 低内容提示 (US-045) -->
        <van-notice-bar
          v-if="data?.digest_status?.low_content_warning"
          :color="'var(--zx-warning)'"
          :background="'var(--zx-warning-bg)'"
          left-icon="info-o"
          :text="`今日资讯较少（${data.digest_status.item_count}条）`"
          class="section-gap"
        />

        <!-- 成本卡片 -->
        <div class="cost-card zx-card section-gap">
          <div class="cost-header">
            <span class="cost-title">今日 API 成本</span>
            <span class="cost-detail-link" @click="router.push({ name: 'costs' })">详情</span>
          </div>
          <div class="cost-amount">
            ${{ data?.today_cost?.total_cost?.toFixed(4) ?? '0.0000' }}
          </div>
          <div
            v-for="svc in data?.today_cost?.by_service ?? []"
            :key="svc.service"
            class="cost-service"
          >
            <span class="cost-svc-name">{{ svc.service }}</span>
            <span class="cost-svc-detail">{{ svc.call_count }}次 · {{ svc.total_tokens }} tokens</span>
            <span class="cost-svc-amount">${{ (svc.estimated_cost ?? 0).toFixed(4) }}</span>
          </div>
          <div
            v-if="!data?.today_cost?.by_service?.length"
            class="cost-empty"
          >
            暂无调用记录
          </div>
        </div>

        <!-- 操作按钮 -->
        <van-button
          type="primary"
          block
          size="large"
          class="cta-btn section-gap"
          @click="router.push({ name: 'digest' })"
        >
          审核今日内容
        </van-button>

        <!-- 快捷导航 -->
        <div class="nav-grid section-gap">
          <div class="nav-item" @click="router.push({ name: 'accounts' })">
            <div class="nav-icon-wrap" style="background: var(--zx-primary-bg)">
              <van-icon name="friends-o" color="var(--zx-primary)" size="22" />
            </div>
            <span class="nav-label">大V管理</span>
          </div>
          <div class="nav-item" @click="router.push({ name: 'settings' })">
            <div class="nav-icon-wrap" style="background: var(--zx-accent-bg)">
              <van-icon name="setting-o" color="var(--zx-accent)" size="22" />
            </div>
            <span class="nav-label">系统设置</span>
          </div>
          <div class="nav-item" @click="router.push({ name: 'logs' })">
            <div class="nav-icon-wrap" style="background: var(--zx-info-bg)">
              <van-icon name="description" color="var(--zx-info)" size="22" />
            </div>
            <span class="nav-label">系统日志</span>
          </div>
        </div>

        <!-- 近 7 天记录 -->
        <p class="zx-section-title">近 7 天推送记录</p>
        <van-cell-group inset>
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
.nav-brand {
  font-family: var(--zx-font-display);
  font-size: var(--zx-text-xl);
  font-weight: 700;
  color: var(--zx-primary);
  letter-spacing: 0.05em;
}

.alert-gap {
  margin-bottom: var(--zx-space-xs);
}

.section-gap {
  margin-bottom: var(--zx-space-base);
}

/* ── 状态卡片行 ── */

.status-row {
  display: flex;
  gap: var(--zx-space-md);
  margin-bottom: var(--zx-space-base);
}

.status-card {
  flex: 1;
  background: var(--zx-bg-card);
  border-radius: var(--zx-radius-md);
  box-shadow: var(--zx-shadow-sm);
  padding: var(--zx-space-base);
  display: flex;
  flex-direction: column;
  gap: var(--zx-space-sm);
}

.status-label {
  font-size: var(--zx-text-sm);
  color: var(--zx-text-tertiary);
  font-weight: 500;
}

.status-value {
  display: flex;
  align-items: center;
  gap: var(--zx-space-sm);
}

/* ── 成本卡片 ── */

.cost-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--zx-space-sm);
}

.cost-title {
  font-size: var(--zx-text-sm);
  color: var(--zx-text-tertiary);
  font-weight: 500;
}

.cost-detail-link {
  color: var(--zx-primary-lighter);
  font-size: var(--zx-text-xs);
  cursor: pointer;
}

.cost-amount {
  font-family: var(--zx-font-display);
  font-size: var(--zx-text-2xl);
  font-weight: 700;
  color: var(--zx-text-primary);
  margin-bottom: var(--zx-space-sm);
}

.cost-service {
  display: flex;
  align-items: center;
  padding: var(--zx-space-sm) 0;
  border-top: 1px solid var(--zx-border-light);
  font-size: var(--zx-text-sm);
}

.cost-svc-name {
  color: var(--zx-text-secondary);
  min-width: 80px;
}

.cost-svc-detail {
  flex: 1;
  color: var(--zx-text-tertiary);
  font-size: var(--zx-text-xs);
}

.cost-svc-amount {
  color: var(--zx-text-primary);
  font-weight: 500;
}

.cost-empty {
  color: var(--zx-text-tertiary);
  font-size: var(--zx-text-sm);
  padding-top: var(--zx-space-xs);
}

/* ── CTA 按钮 ── */

.cta-btn {
  font-weight: 600;
  letter-spacing: 0.05em;
}

/* ── 快捷导航网格 ── */

.nav-grid {
  display: flex;
  gap: var(--zx-space-md);
}

.nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--zx-space-sm);
  background: var(--zx-bg-card);
  border-radius: var(--zx-radius-md);
  box-shadow: var(--zx-shadow-xs);
  padding: var(--zx-space-base) var(--zx-space-sm);
  cursor: pointer;
  transition: box-shadow var(--zx-duration-fast) var(--zx-easing);
}

.nav-item:active {
  box-shadow: var(--zx-shadow-md);
}

.nav-icon-wrap {
  width: 44px;
  height: 44px;
  border-radius: var(--zx-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
}

.nav-label {
  font-size: var(--zx-text-sm);
  color: var(--zx-text-secondary);
  font-weight: 500;
}
</style>
