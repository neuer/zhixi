<script setup lang="ts">
import api from "@/api";
import ArticlePreview from "@/components/ArticlePreview.vue";
import type { HistoryDetailResponse } from "@zhixi/openapi-client";
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();
const loading = ref(true);
const data = ref<HistoryDetailResponse | null>(null);
const error = ref<string | null>(null);

async function loadDetail() {
  const id = route.params.id;
  loading.value = true;

  try {
    const resp = await api.get<HistoryDetailResponse>(`/history/${id}`);
    data.value = resp.data;
  } catch {
    error.value = "记录不存在";
  } finally {
    loading.value = false;
  }
}

function goBack() {
  router.push("/history");
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

    <div v-if="loading" class="detail-loading">
      <van-loading size="36px" vertical>加载中...</van-loading>
    </div>

    <div v-else-if="error" class="detail-empty">
      <van-empty :description="error">
        <van-button round type="primary" size="small" @click="goBack">
          返回列表
        </van-button>
      </van-empty>
    </div>

    <ArticlePreview
      v-else-if="data"
      :digest="data.digest"
      :items="data.items"
    />
  </div>
</template>

<style scoped>
.history-detail-page {
  background: #fff;
  min-height: 100vh;
}

.detail-loading {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 60vh;
}

.detail-empty {
  padding-top: 20vh;
}
</style>
