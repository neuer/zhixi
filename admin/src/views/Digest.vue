<script setup lang="ts">
import api from "@/api";
import { useAsyncData } from "@/composables/useAsyncData";
import { filterVisibleItems } from "@/utils/digest";
import { getStatus } from "@/utils/status";
import type { DigestItemResponse, TodayResponse } from "@zhixi/openapi-client";
import { showConfirmDialog, showToast } from "vant";
import { type Ref, computed, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const publishing = ref(false);
const regenerating = ref(false);

const { data, loading, refreshing, error, execute, refresh } = useAsyncData(
  () => api.get<TodayResponse>("/digest/today").then((r) => r.data),
);

const visibleItems = computed(() => {
  if (!data.value) return [];
  return filterVisibleItems(data.value.items);
});

function getItemLabel(item: DigestItemResponse): string {
  if (item.snapshot_author_handle) return `@${item.snapshot_author_handle}`;
  if (item.snapshot_topic_type === "aggregated") return "聚合话题";
  return "";
}

/** 通用确认后执行函数，减少 handlePublish/handleRegenerate 重复代码。 */
async function confirmAndExecute(options: {
  title: string;
  message: string;
  apiPath: string;
  successMsg: string;
  loadingRef: Ref<boolean>;
}) {
  if (!data.value?.digest || options.loadingRef.value) return;
  try {
    await showConfirmDialog({ title: options.title, message: options.message });
  } catch {
    return; // 用户取消
  }
  options.loadingRef.value = true;
  try {
    await api.post(options.apiPath);
    showToast(options.successMsg);
  } catch {
    // API 失败已由拦截器处理
  } finally {
    options.loadingRef.value = false;
    await execute();
  }
}

function handlePublish() {
  return confirmAndExecute({
    title: "确认发布",
    message: "发布后不可编辑，确认发布？",
    apiPath: "/digest/mark-published",
    successMsg: "发布成功",
    loadingRef: publishing,
  });
}

function handleRegenerate() {
  return confirmAndExecute({
    title: "重新生成",
    message: "将重置所有编辑并重新生成草稿，确认？",
    apiPath: "/digest/regenerate",
    successMsg: "重新生成中...",
    loadingRef: regenerating,
  });
}

async function handleExclude(item: DigestItemResponse) {
  try {
    await showConfirmDialog({
      title: "剔除条目",
      message: `确定剔除「${item.snapshot_title || "该条目"}」？`,
    });
  } catch {
    return;
  }
  try {
    await api.post(`/digest/exclude/${item.item_type}/${item.item_ref_id}`);
    showToast("已剔除");
    await execute();
  } catch {
    // 拦截器已处理
  }
}
</script>

<template>
  <div class="zx-page digest-page">
    <van-nav-bar
      title="今日内容"
      left-text="返回"
      left-arrow
      @click-left="router.push({ name: 'dashboard' })"
      :border="false"
    />

    <van-pull-refresh v-model="refreshing" @refresh="refresh">
      <!-- 低内容提示 (US-045) -->
      <van-notice-bar
        v-if="data?.low_content_warning"
        :color="'var(--zx-warning)'"
        :background="'var(--zx-warning-bg)'"
        left-icon="info-o"
        :text="`今日资讯较少（${data.digest?.item_count ?? 0}条）`"
      />

      <!-- 加载失败 -->
      <div v-if="!loading && error" class="empty-state">
        <van-empty :description="error" image="error" />
      </div>

      <!-- 无草稿 -->
      <div v-else-if="!loading && !data?.digest" class="empty-state">
        <van-empty description="今日草稿尚未生成" />
      </div>

      <!-- 有草稿 -->
      <template v-else-if="data?.digest">
        <div class="zx-page-content">
          <!-- 概览卡片 -->
          <div class="overview-card zx-card section-gap">
            <div class="overview-row">
              <span class="overview-label">状态</span>
              <div class="overview-value">
                <van-tag :type="getStatus(data.digest.status).type">
                  {{ getStatus(data.digest.status).text }}
                </van-tag>
                <span class="zx-meta-text">
                  {{ data.digest.item_count }}条 v{{ data.digest.version }}
                </span>
              </div>
            </div>
            <p
              v-if="data.digest.summary"
              class="overview-summary"
            >
              {{ data.digest.summary }}
            </p>
          </div>

          <!-- 操作按钮 -->
          <div v-if="data.digest.status === 'draft'" class="action-buttons section-gap">
            <van-button type="primary" block :loading="publishing" :disabled="publishing" @click="handlePublish">
              确认发布
            </van-button>
            <van-button type="default" block :loading="regenerating" :disabled="regenerating" @click="handleRegenerate">
              重新生成
            </van-button>
          </div>

          <!-- 条目列表 -->
          <p class="zx-section-title">条目列表（{{ visibleItems.length }}条）</p>
          <div class="item-list">
            <van-swipe-cell
              v-for="(item, idx) in visibleItems"
              :key="item.id"
              :disabled="data?.digest?.status !== 'draft'"
            >
              <div
                class="item-card"
                @click="router.push({ name: 'digest-edit', params: { type: item.item_type, id: item.item_ref_id } })"
              >
                <div class="item-index">{{ idx + 1 }}</div>
                <div class="item-body">
                  <div class="item-title">{{ item.snapshot_title || '无标题' }}</div>
                  <div class="item-meta">
                    <span v-if="getItemLabel(item)" class="item-author">{{ getItemLabel(item) }}</span>
                    <span class="item-heat">{{ Math.round(item.snapshot_heat_score) }}</span>
                  </div>
                </div>
                <van-icon name="arrow" class="item-arrow" />
              </div>
              <template #right>
                <van-button
                  square
                  type="danger"
                  class="swipe-btn"
                  @click="handleExclude(item)"
                >
                  剔除
                </van-button>
              </template>
            </van-swipe-cell>
          </div>
          <div
            v-if="visibleItems.length === 0"
            class="zx-card"
            style="text-align: center; color: var(--zx-text-tertiary); padding: 24px"
          >
            暂无条目
          </div>
        </div>
      </template>
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

/* ── 概览卡片 ── */

.overview-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.overview-label {
  font-size: var(--zx-text-sm);
  color: var(--zx-text-tertiary);
}

.overview-value {
  display: flex;
  align-items: center;
  gap: var(--zx-space-sm);
}

.overview-summary {
  margin: var(--zx-space-md) 0 0;
  padding-top: var(--zx-space-md);
  border-top: 1px solid var(--zx-border-light);
  font-size: var(--zx-text-sm);
  color: var(--zx-text-secondary);
  line-height: 1.6;
}

/* ── 操作按钮 ── */

.action-buttons {
  display: flex;
  gap: var(--zx-space-sm);
}

/* ── 滑动按钮 ── */

.swipe-btn {
  height: 100%;
  min-width: 64px;
  font-size: var(--zx-text-sm);
}

/* ── 条目列表 ── */

.item-list {
  display: flex;
  flex-direction: column;
  gap: var(--zx-space-sm);
}

.item-card {
  display: flex;
  align-items: center;
  gap: var(--zx-space-md);
  background: var(--zx-bg-card);
  border-radius: var(--zx-radius-md);
  box-shadow: var(--zx-shadow-xs);
  padding: var(--zx-space-md) var(--zx-space-base);
  cursor: pointer;
  transition: box-shadow var(--zx-duration-fast) var(--zx-easing);
}

.item-card:active {
  box-shadow: var(--zx-shadow-sm);
}

.item-index {
  width: 24px;
  height: 24px;
  border-radius: var(--zx-radius-sm);
  background: var(--zx-accent);
  color: var(--zx-text-inverse);
  font-size: var(--zx-text-xs);
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.item-body {
  flex: 1;
  min-width: 0;
}

.item-title {
  font-size: var(--zx-text-base);
  font-weight: 500;
  color: var(--zx-text-primary);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.item-meta {
  display: flex;
  align-items: center;
  gap: var(--zx-space-sm);
  margin-top: var(--zx-space-xs);
  font-size: var(--zx-text-xs);
  color: var(--zx-text-tertiary);
}

.item-heat {
  color: var(--zx-accent);
  font-weight: 600;
}

.item-heat::before {
  content: "热度 ";
  font-weight: 400;
}

.item-arrow {
  color: var(--zx-text-disabled);
  font-size: 14px;
  flex-shrink: 0;
}
</style>
