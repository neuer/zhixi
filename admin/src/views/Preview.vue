<script setup lang="ts">
import api from "@/api";
import ArticlePreview from "@/components/ArticlePreview.vue";
import type { PreviewResponse } from "@zhixi/openapi-client";
import axios from "axios";
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();
const loading = ref(true);
const data = ref<PreviewResponse | null>(null);
const error = ref<string | null>(null);

const isTokenMode = computed(() => !!route.query.token);

async function loadPreview() {
  const rawToken = route.query.token;
  const shareToken = Array.isArray(rawToken) ? rawToken[0] : rawToken;
  const url = shareToken ? `/digest/preview/${shareToken}` : "/digest/preview";

  loading.value = true;
  error.value = null;
  try {
    const resp = await api.get<PreviewResponse>(url);
    data.value = resp.data;
  } catch (e) {
    if (shareToken && axios.isAxiosError(e) && e.response?.status === 403) {
      error.value = "链接已失效或过期";
    } else {
      error.value = "暂无可预览的内容";
    }
  } finally {
    loading.value = false;
  }
}

function goBack() {
  router.push({ name: "dashboard" });
}

onMounted(loadPreview);
</script>

<template>
  <div class="preview-page">
    <!-- 顶部导航 -->
    <van-nav-bar
      title="内容预览"
      :left-text="isTokenMode ? '' : '返回'"
      :left-arrow="!isTokenMode"
      @click-left="isTokenMode ? undefined : goBack()"
      :border="false"
    />

    <!-- 加载态 -->
    <div v-if="loading" class="preview-loading">
      <van-loading size="36px" vertical>加载中...</van-loading>
    </div>

    <!-- 错误态 -->
    <div v-else-if="error" class="preview-empty">
      <van-empty :description="error">
        <van-button
          v-if="!isTokenMode"
          round
          type="primary"
          size="small"
          @click="goBack"
        >
          返回首页
        </van-button>
      </van-empty>
    </div>

    <!-- 预览内容 -->
    <ArticlePreview
      v-else-if="data"
      :digest="data.digest"
      :items="data.items"
    />
  </div>
</template>

<style scoped>
.preview-page {
  background: var(--zx-bg-card);
  min-height: 100vh;
}

.preview-loading {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 60vh;
}

.preview-empty {
  padding-top: 20vh;
}
</style>
