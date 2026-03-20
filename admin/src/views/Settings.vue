<script setup lang="ts">
import api from "@/api";
import type {
  ApiStatusResponse,
  SettingsResponse,
  SettingsUpdate,
} from "@zhixi/openapi-client";
import { closeToast, showLoadingToast, showToast } from "vant";
import { onMounted, ref } from "vue";

const loading = ref(true);
const saving = ref(false);

// 表单数据
const form = ref({
  push_time: "08:00",
  push_days: [1, 2, 3, 4, 5, 6, 7] as number[],
  top_n: 10,
  min_articles: 1,
  publish_mode: "manual",
  enable_cover_generation: false,
  cover_generation_timeout: 30,
  notification_webhook_url: "",
});

// DB 信息
const dbSizeMb = ref(0);
const lastBackupAt = ref<string | null>(null);

// API 状态
const apiStatus = ref<ApiStatusResponse | null>(null);
const checkingApi = ref(false);

// 时间选择器
const showTimePicker = ref(false);
const timeColumns = [
  Array.from({ length: 24 }, (_, i) => ({
    text: String(i).padStart(2, "0"),
    value: String(i).padStart(2, "0"),
  })),
  Array.from({ length: 60 }, (_, i) => ({
    text: String(i).padStart(2, "0"),
    value: String(i).padStart(2, "0"),
  })),
];

const dayOptions = [
  { value: 1, label: "周一" },
  { value: 2, label: "周二" },
  { value: 3, label: "周三" },
  { value: 4, label: "周四" },
  { value: 5, label: "周五" },
  { value: 6, label: "周六" },
  { value: 7, label: "周日" },
];

async function loadSettings() {
  loading.value = true;
  try {
    const resp = await api.get<SettingsResponse>("/settings");
    const d = resp.data;
    form.value = {
      push_time: d.push_time,
      push_days: d.push_days,
      top_n: d.top_n,
      min_articles: d.min_articles,
      publish_mode: d.publish_mode,
      enable_cover_generation: d.enable_cover_generation,
      cover_generation_timeout: d.cover_generation_timeout,
      notification_webhook_url: d.notification_webhook_url,
    };
    dbSizeMb.value = d.db_size_mb;
    lastBackupAt.value = d.last_backup_at ?? null;
  } catch {
    // 拦截器已处理
  } finally {
    loading.value = false;
  }
}

async function saveSettings() {
  if (form.value.push_days.length === 0) {
    showToast("至少选择一个推送日");
    return;
  }
  saving.value = true;
  try {
    const payload: SettingsUpdate = { ...form.value };
    await api.put("/settings", payload);
    showToast("配置已保存");
  } catch {
    // 拦截器已处理
  } finally {
    saving.value = false;
  }
}

async function checkApiStatus() {
  checkingApi.value = true;
  showLoadingToast({ message: "检测中...", duration: 0 });
  try {
    const resp = await api.get<ApiStatusResponse>("/settings/api-status");
    apiStatus.value = resp.data;
  } catch {
    // 拦截器已处理
  } finally {
    checkingApi.value = false;
    closeToast();
  }
}

function onTimeConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.value.push_time = `${selectedValues[0]}:${selectedValues[1]}`;
  showTimePicker.value = false;
}

function apiStatusText(status: string): string {
  if (status === "ok") return "正常";
  if (status === "error") return "异常";
  return "未配置";
}

function apiStatusColor(status: string): string {
  if (status === "ok") return "#07c160";
  if (status === "error") return "#ee0a24";
  return "#969799";
}

function formatBackupTime(dt: string | null): string {
  if (!dt) return "暂无备份";
  return new Date(dt).toLocaleString("zh-CN");
}

onMounted(loadSettings);
</script>

<template>
  <div class="settings-page">
    <van-nav-bar title="系统设置" left-arrow @click-left="$router.back()" />

    <div style="padding: 12px">
      <!-- 推送配置 -->
      <van-cell-group inset title="推送配置" style="margin-bottom: 12px">
        <van-cell
          title="推送时间"
          :value="form.push_time"
          is-link
          @click="showTimePicker = true"
        />
        <van-cell title="推送日">
          <template #value>
            <van-checkbox-group v-model="form.push_days" direction="horizontal">
              <van-checkbox
                v-for="day in dayOptions"
                :key="day.value"
                :name="day.value"
                shape="square"
                style="margin: 2px 4px"
              >
                {{ day.label }}
              </van-checkbox>
            </van-checkbox-group>
          </template>
        </van-cell>
        <van-cell title="每日条目数">
          <template #value>
            <van-stepper v-model="form.top_n" :min="1" :max="50" />
          </template>
        </van-cell>
        <van-cell title="最少条目数">
          <template #value>
            <van-stepper v-model="form.min_articles" :min="0" :max="20" />
          </template>
        </van-cell>
      </van-cell-group>

      <!-- 发布配置 -->
      <van-cell-group inset title="发布配置" style="margin-bottom: 12px">
        <van-cell title="发布模式">
          <template #value>
            <van-radio-group v-model="form.publish_mode" direction="horizontal">
              <van-radio name="manual">手动</van-radio>
              <van-radio name="api">自动</van-radio>
            </van-radio-group>
          </template>
        </van-cell>
        <van-cell title="封面图生成">
          <template #value>
            <van-switch v-model="form.enable_cover_generation" />
          </template>
        </van-cell>
        <van-cell v-if="form.enable_cover_generation" title="封面图超时(秒)">
          <template #value>
            <van-stepper
              v-model="form.cover_generation_timeout"
              :min="10"
              :max="120"
            />
          </template>
        </van-cell>
      </van-cell-group>

      <!-- 通知配置 -->
      <van-cell-group inset title="通知配置" style="margin-bottom: 12px">
        <van-field
          v-model="form.notification_webhook_url"
          label="Webhook URL"
          placeholder="企业微信 Webhook 地址"
          clearable
        />
      </van-cell-group>

      <!-- API 状态 -->
      <van-cell-group inset title="API 状态" style="margin-bottom: 12px">
        <van-button
          size="small"
          type="default"
          :loading="checkingApi"
          style="margin: 8px 16px"
          @click="checkApiStatus"
        >
          检测 API 状态
        </van-button>
        <template v-if="apiStatus">
          <van-cell title="X API">
            <template #value>
              <span :style="{ color: apiStatusColor(apiStatus.x_api.status) }">
                {{ apiStatusText(apiStatus.x_api.status) }}
              </span>
              <span
                v-if="apiStatus.x_api.latency_ms != null"
                style="color: #969799; margin-left: 4px; font-size: 12px"
              >
                {{ apiStatus.x_api.latency_ms }}ms
              </span>
            </template>
          </van-cell>
          <van-cell title="Claude API">
            <template #value>
              <span
                :style="{
                  color: apiStatusColor(apiStatus.claude_api.status),
                }"
              >
                {{ apiStatusText(apiStatus.claude_api.status) }}
              </span>
              <span
                v-if="apiStatus.claude_api.latency_ms != null"
                style="color: #969799; margin-left: 4px; font-size: 12px"
              >
                {{ apiStatus.claude_api.latency_ms }}ms
              </span>
            </template>
          </van-cell>
          <van-cell title="Gemini API">
            <template #value>
              <span
                :style="{
                  color: apiStatusColor(apiStatus.gemini_api.status),
                }"
              >
                {{ apiStatusText(apiStatus.gemini_api.status) }}
              </span>
            </template>
          </van-cell>
          <van-cell title="微信 API">
            <template #value>
              <span
                :style="{
                  color: apiStatusColor(apiStatus.wechat_api.status),
                }"
              >
                {{ apiStatusText(apiStatus.wechat_api.status) }}
              </span>
            </template>
          </van-cell>
        </template>
      </van-cell-group>

      <!-- 数据库信息 -->
      <van-cell-group inset title="数据库" style="margin-bottom: 12px">
        <van-cell title="数据库大小" :value="`${dbSizeMb} MB`" />
        <van-cell
          title="最近备份"
          :value="formatBackupTime(lastBackupAt)"
        />
      </van-cell-group>

      <!-- 保存 -->
      <van-button
        type="primary"
        block
        size="large"
        :loading="saving"
        style="margin-top: 16px"
        @click="saveSettings"
      >
        保存配置
      </van-button>
    </div>

    <!-- 时间选择弹窗 -->
    <van-popup v-model:show="showTimePicker" position="bottom" round>
      <van-picker
        title="选择推送时间"
        :columns="timeColumns"
        @confirm="onTimeConfirm"
        @cancel="showTimePicker = false"
      />
    </van-popup>
  </div>
</template>
