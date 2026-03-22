<script setup lang="ts">
import api from "@/api";
import type { LogsResponse } from "@zhixi/openapi-client";
import { onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

const loading = ref(false);
const refreshing = ref(false);
const finished = ref(false);
/** 扩展日志条目：附加前端生成的唯一 _uid 用于列表 key，避免与生成类型 LogEntry 混淆 */
type LogEntryWithUid = LogsResponse["logs"][number] & { _uid: number };
const logs = ref<LogEntryWithUid[]>([]);
const selectedLevel = ref<"DEBUG" | "INFO" | "WARNING" | "ERROR">("INFO");
const pageVal = ref(1);
const pageSize = 50;
let logIdSeq = 0;

const levelOptions = [
  { text: "DEBUG", value: "DEBUG" },
  { text: "INFO", value: "INFO" },
  { text: "WARNING", value: "WARNING" },
  { text: "ERROR", value: "ERROR" },
];

const levelStyleMap: Record<string, { color: string; bg: string }> = {
  ERROR: { color: "var(--zx-danger)", bg: "var(--zx-danger-bg)" },
  CRITICAL: { color: "var(--zx-danger)", bg: "var(--zx-danger-bg)" },
  WARNING: { color: "var(--zx-warning)", bg: "var(--zx-warning-bg)" },
};
const levelStyleDefault = {
  color: "var(--zx-text-primary)",
  bg: "transparent",
};

function getLevelStyle(level: string) {
  return levelStyleMap[level] ?? levelStyleDefault;
}

// 用 let 而非 ref：isLoadingMore 仅作为并发锁防止重复请求，无需触发视图更新
let isLoadingMore = false;

async function loadLogs() {
  if (isLoadingMore || finished.value) return;
  isLoadingMore = true;
  loading.value = true;
  try {
    const resp = await api.get<LogsResponse>("/dashboard/logs", {
      params: {
        level: selectedLevel.value,
        limit: pageSize,
        offset: (pageVal.value - 1) * pageSize,
      },
    });
    const newLogs = resp.data.logs.map((log) => ({
      ...log,
      _uid: ++logIdSeq,
    }));
    if (pageVal.value === 1) {
      logs.value = newLogs;
    } else {
      logs.value.push(...newLogs);
    }
    if (newLogs.length < pageSize) {
      finished.value = true;
    }
    pageVal.value += 1;
  } catch {
    // 拦截器已处理 toast；不设 finished，允许用户滚动重试
  } finally {
    loading.value = false;
    isLoadingMore = false;
  }
}

function resetAndLoad() {
  pageVal.value = 1;
  finished.value = false;
  logs.value = [];
  logIdSeq = 0;
  refreshing.value = false;
  loadLogs();
}

watch(selectedLevel, resetAndLoad);
onMounted(loadLogs);
</script>

<template>
  <div class="zx-page logs-page">
    <van-nav-bar title="系统日志" left-arrow @click-left="router.back()" />

    <div class="filter-bar">
      <van-dropdown-menu>
        <van-dropdown-item
          v-model="selectedLevel"
          :options="levelOptions"
        />
      </van-dropdown-menu>
    </div>

    <van-pull-refresh v-model="refreshing" @refresh="resetAndLoad">
      <van-list
        v-model:loading="loading"
        :finished="finished"
        finished-text="没有更多了"
        @load="loadLogs"
      >
        <div class="log-list">
          <van-empty v-if="!logs.length && !loading" description="暂无日志" />

          <div
            v-for="log in logs"
            :key="log._uid"
            class="log-entry"
            :style="{
              color: getLevelStyle(log.level).color,
              backgroundColor: getLevelStyle(log.level).bg,
            }"
          >
            <div class="log-meta">
              <span class="log-level">{{ log.level }}</span>
              <span class="log-time">{{ log.timestamp }}</span>
              <span v-if="log.module" class="log-module">[{{ log.module }}]</span>
            </div>
            <div class="log-message">{{ log.message }}</div>
            <div v-if="log.exception" class="log-exception">{{ log.exception }}</div>
          </div>
        </div>
      </van-list>
    </van-pull-refresh>
  </div>
</template>

<style scoped>
.filter-bar {
  padding: var(--zx-space-md) var(--zx-space-md) 0;
}

.log-list {
  padding: var(--zx-space-md);
}

.log-entry {
  font-family: var(--zx-font-mono);
  font-size: var(--zx-text-xs);
  padding: var(--zx-space-sm);
  margin-bottom: var(--zx-space-xs);
  border-radius: var(--zx-radius-sm);
  border: 1px solid var(--zx-border-light);
  word-break: break-all;
}

.log-meta {
  display: flex;
  gap: var(--zx-space-sm);
  margin-bottom: var(--zx-space-xs);
  font-size: var(--zx-text-xs);
  opacity: 0.8;
}

.log-level {
  font-weight: bold;
  min-width: 60px;
}

.log-message {
  line-height: 1.4;
}

.log-exception {
  margin-top: var(--zx-space-xs);
  padding: var(--zx-space-xs);
  background: rgba(0, 0, 0, 0.03);
  border-radius: 2px;
  white-space: pre-wrap;
  font-size: var(--zx-text-xs);
}
</style>
