<script setup lang="ts">
import api from "@/api";
import type { DashboardOverviewResponse } from "@zhixi/openapi-client";
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const loading = ref(true);
const data = ref<DashboardOverviewResponse | null>(null);

const statusMap: Record<string, { text: string; color: string }> = {
  completed: { text: "已完成", color: "#07c160" },
  running: { text: "运行中", color: "#1989fa" },
  failed: { text: "失败", color: "#ee0a24" },
  skipped: { text: "已跳过", color: "#969799" },
  draft: { text: "待审核", color: "#ff976a" },
  published: { text: "已发布", color: "#07c160" },
};

function getStatus(status: string | null | undefined) {
  if (!status) return { text: "无记录", color: "#969799" };
  return statusMap[status] ?? { text: status, color: "#969799" };
}

async function loadData() {
  loading.value = true;
  try {
    const resp = await api.get<DashboardOverviewResponse>(
      "/dashboard/overview",
    );
    data.value = resp.data;
  } catch {
    // 错误已由拦截器处理
  } finally {
    loading.value = false;
  }
}

function goDigest() {
  router.push("/digest");
}

function goSettings() {
  router.push("/settings");
}

function goAccounts() {
  router.push("/accounts");
}

onMounted(loadData);
</script>

<template>
  <div class="dashboard-page">
    <van-nav-bar title="智曦管理后台" />

    <van-pull-refresh v-model="loading" @refresh="loadData">
      <!-- 告警 -->
      <template v-if="data?.alerts?.length">
        <van-notice-bar
          v-for="(alert, idx) in data.alerts"
          :key="idx"
          color="#ee0a24"
          background="#fff0f0"
          left-icon="warning-o"
          :text="`[${alert.job_type}] ${alert.error_message || '任务失败'}`"
          style="margin-bottom: 4px"
        />
      </template>

      <div style="padding: 12px">
        <!-- Pipeline 状态 -->
        <van-cell-group inset title="今日状态" style="margin-bottom: 12px">
          <van-cell title="Pipeline">
            <template #value>
              <van-tag
                :type="
                  getStatus(data?.pipeline_status?.status).color === '#ee0a24'
                    ? 'danger'
                    : getStatus(data?.pipeline_status?.status).color ===
                        '#07c160'
                      ? 'success'
                      : getStatus(data?.pipeline_status?.status).color ===
                          '#1989fa'
                        ? 'primary'
                        : 'default'
                "
              >
                {{ getStatus(data?.pipeline_status?.status).text }}
              </van-tag>
            </template>
          </van-cell>
          <van-cell title="日报">
            <template #value>
              <van-tag
                :type="
                  getStatus(data?.digest_status?.status).color === '#07c160'
                    ? 'success'
                    : getStatus(data?.digest_status?.status).color === '#ff976a'
                      ? 'warning'
                      : getStatus(data?.digest_status?.status).color ===
                          '#ee0a24'
                        ? 'danger'
                        : 'default'
                "
              >
                {{ getStatus(data?.digest_status?.status).text }}
              </van-tag>
              <span
                v-if="data?.digest_status?.item_count"
                style="margin-left: 8px; color: #969799; font-size: 12px"
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
          style="margin-bottom: 12px"
        />

        <!-- 成本卡片 -->
        <van-cell-group inset title="今日 API 成本" style="margin-bottom: 12px">
          <template #title>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>今日 API 成本</span>
              <span style="color: #1989fa; font-size: 12px; cursor: pointer" @click="router.push('/costs')">查看详情 &gt;</span>
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
            :value="`$${svc.estimated_cost.toFixed(4)}`"
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
          style="margin-bottom: 12px"
          @click="goDigest"
        >
          审核今日内容
        </van-button>

        <van-grid :column-num="3" :gutter="10" style="margin-bottom: 12px">
          <van-grid-item icon="friends-o" text="大V管理" @click="goAccounts" />
          <van-grid-item icon="setting-o" text="系统设置" @click="goSettings" />
          <van-grid-item icon="description" text="系统日志" @click="router.push('/logs')" />
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
                :type="
                  record.status === 'published'
                    ? 'success'
                    : record.status === 'draft'
                      ? 'warning'
                      : record.status === 'failed'
                        ? 'danger'
                        : 'default'
                "
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
    </van-pull-refresh>
  </div>
</template>
