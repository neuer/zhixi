<script setup lang="ts">
import api from "@/api";
import { getStatus } from "@/utils/status";
import type { TodayResponse } from "@zhixi/openapi-client";
import { showConfirmDialog, showToast } from "vant";
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const loading = ref(true);
const data = ref<TodayResponse | null>(null);

/** 过滤已剔除条目，按 display_order 排序。 */
const visibleItems = computed(() => {
  if (!data.value) return [];
  return data.value.items
    .filter((item) => !item.is_excluded)
    .sort((a, b) => a.display_order - b.display_order);
});

async function loadData() {
  loading.value = true;
  try {
    const resp = await api.get<TodayResponse>("/digest/today");
    data.value = resp.data;
  } catch {
    // 拦截器已处理
  } finally {
    loading.value = false;
  }
}

async function handlePublish() {
  if (!data.value?.digest) return;
  try {
    await showConfirmDialog({
      title: "确认发布",
      message: "发布后不可编辑，确认发布？",
    });
    await api.post("/digest/mark-published");
    showToast("发布成功");
    await loadData();
  } catch {
    // 取消或失败
  }
}

async function handleRegenerate() {
  if (!data.value?.digest) return;
  try {
    await showConfirmDialog({
      title: "重新生成",
      message: "将重置所有编辑并重新生成草稿，确认？",
    });
    await api.post("/digest/regenerate");
    showToast("重新生成中...");
    await loadData();
  } catch {
    // 取消或失败
  }
}

onMounted(loadData);
</script>

<template>
  <div class="digest-page">
    <van-nav-bar
      title="今日内容"
      left-text="返回"
      left-arrow
      @click-left="router.push('/')"
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

      <!-- 无草稿 -->
      <div v-if="!loading && !data?.digest" style="padding-top: 20vh">
        <van-empty description="今日草稿尚未生成" />
      </div>

      <!-- 有草稿 -->
      <template v-else-if="data?.digest">
        <div style="padding: 12px">
          <!-- 概览卡片 -->
          <van-cell-group inset style="margin-bottom: 12px">
            <van-cell title="状态">
              <template #value>
                <van-tag :type="getStatus(data.digest.status).type">
                  {{ getStatus(data.digest.status).text }}
                </van-tag>
                <span style="margin-left: 8px; color: #969799; font-size: 12px">
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
          <div v-if="data.digest.status === 'draft'" style="display: flex; gap: 8px; margin-bottom: 12px">
            <van-button type="primary" block @click="handlePublish">
              确认发布
            </van-button>
            <van-button type="default" block @click="handleRegenerate">
              重新生成
            </van-button>
          </div>

          <!-- 条目列表 -->
          <van-cell-group inset :title="`条目列表（${visibleItems.length}条）`">
            <van-cell
              v-for="(item, idx) in visibleItems"
              :key="item.id"
              :title="`${idx + 1}. ${item.snapshot_title || '无标题'}`"
              :label="item.snapshot_author_handle ? `@${item.snapshot_author_handle}` : item.snapshot_topic_type === 'aggregated' ? '聚合话题' : ''"
              is-link
              @click="router.push(`/digest/edit/${item.item_type}/${item.id}`)"
            >
              <template #value>
                <span style="color: #ff976a; font-size: 12px">
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
</style>
