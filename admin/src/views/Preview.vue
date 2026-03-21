<script setup lang="ts">
import api from "@/api";
import ArticlePreview from "@/components/ArticlePreview.vue";
import type { PreviewResponse } from "@zhixi/openapi-client";
import type { AxiosError } from "axios";
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();
const loading = ref(true);
const data = ref<PreviewResponse | null>(null);
const error = ref<string | null>(null);

const isTokenMode = computed(() => !!route.query.token);

async function loadPreview() {
  const shareToken = route.query.token as string | undefined;

  if (shareToken) {
    // 签名链接模式：匿名访问
    loading.value = true;
    try {
      const resp = await api.get<PreviewResponse>(
        `/digest/preview/${shareToken}`,
      );
      data.value = resp.data;
    } catch (e) {
      const axiosErr = e as AxiosError;
      error.value =
        axiosErr.response?.status === 403
          ? "链接已失效或过期"
          : "暂无可预览的内容";
    } finally {
      loading.value = false;
    }
    return;
  }

  // 登录态模式（原逻辑）
  const jwtToken = localStorage.getItem("zhixi_token");
  if (!jwtToken) {
    error.value = "请先登录后访问预览";
    loading.value = false;
    return;
  }

  loading.value = true;
  try {
    const resp = await api.get<PreviewResponse>("/digest/preview");
    data.value = resp.data;
  } catch (_e) {
    // 401 由拦截器处理，其他错误显示提示
    if (!error.value) {
      error.value = "暂无可预览的内容";
    }
  } finally {
    loading.value = false;
  }
}

function goBack() {
  router.push("/dashboard");
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
  background: #fff;
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
