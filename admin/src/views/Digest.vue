<script setup lang="ts">
import api from "@/api";
import { filterVisibleItems } from "@/utils/digest";
import { getStatus } from "@/utils/status";
import type { DigestItemResponse, TodayResponse } from "@zhixi/openapi-client";
import { showConfirmDialog, showToast } from "vant";
import { type Ref, computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const loading = ref(true);
const data = ref<TodayResponse | null>(null);
const error = ref<string | null>(null);
const publishing = ref(false);
const regenerating = ref(false);

const visibleItems = computed(() => {
  if (!data.value) return [];
  return filterVisibleItems(data.value.items);
});

async function loadData() {
  loading.value = true;
  error.value = null;
  try {
    const resp = await api.get<TodayResponse>("/digest/today");
    data.value = resp.data;
  } catch {
    error.value = "加载失败，下拉刷新重试";
  } finally {
    loading.value = false;
  }
}

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
    await loadData();
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

onMounted(loadData);
</script>

<template>
  <div class="digest-page">
    <van-nav-bar
      title="今日内容"
      left-text="返回"
      left-arrow
      @click-left="router.push({ name: 'dashboard' })"
      :border="false"
    />

    <van-pull-refresh v-model="loading" @refresh="loadData">
      <!-- 低内容提示 (US-045) -->
      <van-notice-bar
        v-if="data?.low_content_warning"
        color="#ed6a0c"
        background="#fffbe8"
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
        <div class="page-content">
          <!-- 概览卡片 -->
          <van-cell-group inset class="section-gap">
            <van-cell title="状态">
              <template #value>
                <van-tag :type="getStatus(data.digest.status).type">
                  {{ getStatus(data.digest.status).text }}
                </van-tag>
                <span class="meta-text">
                  {{ data.digest.item_count }}条 v{{ data.digest.version }}
                </span>
              </template>
            </van-cell>
            <van-cell
              v-if="data.digest.summary"
              title="导读"
              :label="data.digest.summary"
            />
          </van-cell-group>

          <!-- 操作按钮 -->
          <div v-if="data.digest.status === 'draft'" class="action-buttons">
            <van-button type="primary" block :loading="publishing" :disabled="publishing" @click="handlePublish">
              确认发布
            </van-button>
            <van-button type="default" block :loading="regenerating" :disabled="regenerating" @click="handleRegenerate">
              重新生成
            </van-button>
          </div>

          <!-- 条目列表 -->
          <van-cell-group inset :title="`条目列表（${visibleItems.length}条）`">
            <van-cell
              v-for="(item, idx) in visibleItems"
              :key="item.id"
              :title="`${idx + 1}. ${item.snapshot_title || '无标题'}`"
              :label="getItemLabel(item)"
              is-link
              @click="router.push({ name: 'digest-edit', params: { type: item.item_type, id: item.item_ref_id } })"
            >
              <template #value>
                <span class="heat-score">
                  🔥 {{ Math.round(item.snapshot_heat_score) }}
                </span>
              </template>
            </van-cell>
            <van-cell
              v-if="visibleItems.length === 0"
              title="暂无条目"
            />
          </van-cell-group>
        </div>
      </template>
    </van-pull-refresh>
  </div>
</template>

<style scoped>
.digest-page {
  background: #f7f8fa;
  min-height: 100vh;
}

.empty-state {
  padding-top: 20vh;
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

.action-buttons {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.heat-score {
  color: #ff976a;
  font-size: 12px;
}
</style>
