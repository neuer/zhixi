<script setup lang="ts">
import api from "@/api";
import type { LogsResponse } from "@zhixi/openapi-client";
import { onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

const loading = ref(true);
const logs = ref<LogsResponse["logs"]>([]);
const selectedLevel = ref("INFO");

const levelOptions = [
  { text: "DEBUG", value: "DEBUG" },
  { text: "INFO", value: "INFO" },
  { text: "WARNING", value: "WARNING" },
  { text: "ERROR", value: "ERROR" },
];

function levelColor(level: string): string {
  switch (level) {
    case "ERROR":
    case "CRITICAL":
      return "#ee0a24";
    case "WARNING":
      return "#ff976a";
    default:
      return "#323233";
  }
}

function levelBg(level: string): string {
  switch (level) {
    case "ERROR":
    case "CRITICAL":
      return "#fff0f0";
    case "WARNING":
      return "#fffbe8";
    default:
      return "transparent";
  }
}

async function loadLogs() {
  loading.value = true;
  try {
    const resp = await api.get<LogsResponse>("/dashboard/logs", {
      params: { level: selectedLevel.value, limit: 200 },
    });
    logs.value = resp.data.logs;
  } catch {
    // 错误已由拦截器处理
  } finally {
    loading.value = false;
  }
}

watch(selectedLevel, loadLogs);
onMounted(loadLogs);
</script>

<template>
  <div class="logs-page">
    <van-nav-bar title="系统日志" left-arrow @click-left="router.back()" />

    <div style="padding: 12px 12px 0">
      <van-dropdown-menu>
        <van-dropdown-item
          v-model="selectedLevel"
          :options="levelOptions"
        />
      </van-dropdown-menu>
    </div>

    <van-pull-refresh v-model="loading" @refresh="loadLogs">
      <div class="log-list" style="padding: 12px">
        <van-empty v-if="!logs.length && !loading" description="暂无日志" />

        <div
          v-for="(log, idx) in logs"
          :key="log.timestamp + '-' + idx"
          class="log-entry"
          :style="{
            color: levelColor(log.level),
            backgroundColor: levelBg(log.level),
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
    </van-pull-refresh>
  </div>
</template>

<style scoped>
.log-entry {
  font-family: "SF Mono", "Menlo", "Monaco", "Courier New", monospace;
  font-size: 12px;
  padding: 8px;
  margin-bottom: 4px;
  border-radius: 4px;
  border: 1px solid #ebedf0;
  word-break: break-all;
}

.log-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 11px;
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
  margin-top: 4px;
  padding: 4px;
  background: rgba(0, 0, 0, 0.03);
  border-radius: 2px;
  white-space: pre-wrap;
  font-size: 11px;
}
</style>
