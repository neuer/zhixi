<script setup lang="ts">
import api from "@/api";
import ArticlePreview from "@/components/ArticlePreview.vue";
import AsyncContent from "@/components/AsyncContent.vue";
import type { HistoryDetailResponse } from "@zhixi/openapi-client";
import axios from "axios";
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();
const loading = ref(true);
const data = ref<HistoryDetailResponse | null>(null);
const error = ref<string | null>(null);

async function loadDetail() {
  const rawId = route.params.id;
  const id = Number(Array.isArray(rawId) ? rawId[0] : rawId);
  if (Number.isNaN(id) || id <= 0) {
    error.value = "无效的记录 ID";
    loading.value = false;
    return;
  }

  loading.value = true;
  try {
    const resp = await api.get<HistoryDetailResponse>(`/history/${id}`);
    data.value = resp.data;
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.status === 404) {
      error.value = "记录不存在";
    } else {
      error.value = "加载失败，下拉刷新重试";
    }
  } finally {
    loading.value = false;
  }
}

function goBack() {
  router.push({ name: "history" });
}

onMounted(loadDetail);
</script>

<template>
  <div class="history-detail-page">
    <van-nav-bar
      title="历史详情"
      left-text="返回"
      left-arrow
      @click-left="goBack"
      :border="false"
    />

    <AsyncContent :loading="loading" :error="error">
      <template #error-action>
        <van-button round type="primary" size="small" @click="goBack">
          返回列表
        </van-button>
      </template>
      <ArticlePreview
        v-if="data"
        :digest="data.digest"
        :items="data.items"
      />
    </AsyncContent>
  </div>
</template>

<style scoped>
.history-detail-page {
  background: var(--zx-bg-card);
  min-height: 100vh;
}
</style>
