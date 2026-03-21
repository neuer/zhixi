<script setup lang="ts">
import api from "@/api";
import { formatDate, formatWeekday } from "@/utils/format";
import { getStatus } from "@/utils/status";
import type {
  HistoryListItem,
  HistoryListResponse,
} from "@zhixi/openapi-client";
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const loading = ref(false);
const refreshing = ref(false);
const finished = ref(false);
const items = ref<HistoryListItem[]>([]);
const page = ref(1);
const pageSize = 20;

let isLoadingMore = false;

async function loadMore() {
  if (isLoadingMore || finished.value) return;
  isLoadingMore = true;
  loading.value = true;

  try {
    const resp = await api.get<HistoryListResponse>("/history", {
      params: { page: page.value, page_size: pageSize },
    });
    const data = resp.data;

    if (page.value === 1) {
      items.value = data.items;
    } else {
      items.value.push(...data.items);
    }

    if (items.value.length >= data.total) {
      finished.value = true;
    }
    page.value += 1;
  } catch {
    // 拦截器已处理，不置 finished 以便用户可重试
  } finally {
    loading.value = false;
    isLoadingMore = false;
  }
}

async function onRefresh() {
  page.value = 1;
  finished.value = false;
  items.value = [];
  refreshing.value = false;
  await loadMore();
}

function goDetail(id: number) {
  router.push({ name: "history-detail", params: { id } });
}

function goBack() {
  router.push({ name: "dashboard" });
}

onMounted(loadMore);
</script>

<template>
  <div class="history-page">
    <van-nav-bar
      title="推送历史"
      left-text="返回"
      left-arrow
      @click-left="goBack"
    />

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <van-list
        v-model:loading="loading"
        :finished="finished"
        finished-text="没有更多了"
        @load="loadMore"
      >
        <van-cell
          v-for="item in items"
          :key="item.id"
          :title="`${formatDate(item.digest_date, false)} ${formatWeekday(item.digest_date)}`"
          :label="`${item.item_count}条 · v${item.version}`"
          is-link
          @click="goDetail(item.id)"
        >
          <template #value>
            <van-tag :type="getStatus(item.status).type">
              {{ getStatus(item.status).text }}
            </van-tag>
          </template>
        </van-cell>

        <van-empty v-if="!loading && items.length === 0" description="暂无历史记录" />
      </van-list>
    </van-pull-refresh>
  </div>
</template>

<style scoped>
.history-page {
  background: #f5f5f5;
  min-height: 100vh;
}
</style>
