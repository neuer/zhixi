<script setup lang="ts">
import api from "@/api";
import { useApiStatus } from "@/composables/useApiStatus";
import {
  getSourceLabel,
  useSecretsManager,
} from "@/composables/useSecretsManager";
import type { SettingsResponse, SettingsUpdate } from "@zhixi/openapi-client";
import { showToast } from "vant";
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

const loading = ref(true);
const saving = ref(false);

// API 状态 & 密钥管理
const { checkingApi, apiEntries, checkApiStatus, getApiStatus } =
  useApiStatus();
const {
  secretsStatus,
  showSecretDialog,
  editingSecret,
  savingSecret,
  loadSecretsStatus,
  openSecretDialog,
  saveSecret,
  clearSecret,
} = useSecretsManager(checkApiStatus);

// 表单数据（从 SettingsResponse 派生，只取可编辑字段）
type SettingsForm = Pick<
  SettingsResponse,
  | "push_time"
  | "push_days"
  | "top_n"
  | "min_articles"
  | "publish_mode"
  | "enable_cover_generation"
  | "cover_generation_timeout"
  | "notification_webhook_url"
>;

const form = ref<SettingsForm>({
  push_time: "08:00",
  push_days: [1, 2, 3, 4, 5, 6, 7],
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
    await loadSettings();
  } finally {
    saving.value = false;
  }
}

function onTimeConfirm({ selectedValues }: { selectedValues: string[] }) {
  if (selectedValues.length < 2) return;
  form.value.push_time = `${selectedValues[0]}:${selectedValues[1]}`;
  showTimePicker.value = false;
}

function formatBackupTime(dt: string | null): string {
  if (!dt) return "暂无备份";
  return new Date(dt).toLocaleString("zh-CN");
}

onMounted(async () => {
  await Promise.all([loadSettings(), loadSecretsStatus()]);
});
</script>

<template>
  <div class="zx-page settings-page">
    <van-nav-bar title="系统设置" left-arrow @click-left="router.back()" />

    <div class="zx-page-content">
      <!-- 推送配置 -->
      <p class="zx-section-title">推送配置</p>
      <van-cell-group inset class="section-gap">
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
                class="day-checkbox"
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
      <p class="zx-section-title">发布配置</p>
      <van-cell-group inset class="section-gap">
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
      <p class="zx-section-title">通知配置</p>
      <van-cell-group inset class="section-gap">
        <van-field
          v-model="form.notification_webhook_url"
          label="Webhook URL"
          placeholder="企业微信 Webhook 地址"
          clearable
        />
      </van-cell-group>

      <!-- API 密钥管理 -->
      <p class="zx-section-title">API 密钥</p>
      <van-cell-group inset class="section-gap">
        <van-cell
          v-for="item in secretsStatus"
          :key="item.key"
          :title="item.label"
        >
          <template #value>
            <div class="secret-value">
              <template v-if="item.configured">
                <span class="secret-masked">
                  {{ item.masked }}
                </span>
                <van-tag
                  :type="item.source === 'db' ? 'primary' : 'default'"
                  size="medium"
                >
                  {{ getSourceLabel(item.source) }}
                </van-tag>
                <van-button size="mini" type="primary" plain @click="openSecretDialog(item)">
                  修改
                </van-button>
                <van-button
                  v-if="item.source === 'db'"
                  size="mini"
                  type="warning"
                  plain
                  @click="clearSecret(item)"
                >
                  清除
                </van-button>
              </template>
              <template v-else>
                <span class="secret-unconfigured">未配置</span>
                <van-button size="mini" type="primary" @click="openSecretDialog(item)">
                  配置
                </van-button>
              </template>
            </div>
          </template>
        </van-cell>
      </van-cell-group>

      <!-- API 状态检测 -->
      <p class="zx-section-title">API 状态</p>
      <van-cell-group inset class="section-gap">
        <div class="api-check-btn">
          <van-button
            size="small"
            type="default"
            :loading="checkingApi"
            @click="checkApiStatus"
          >
            检测 API 状态
          </van-button>
        </div>
        <van-cell
          v-for="entry in apiEntries"
          :key="entry.label"
          :title="entry.label"
        >
          <template #value>
            <span :style="{ color: getApiStatus(entry.data.status).color }">
              {{ getApiStatus(entry.data.status).text }}
            </span>
            <span
              v-if="entry.data.error_detail"
              class="api-error-detail"
            >
              {{ entry.data.error_detail }}
            </span>
            <span
              v-if="entry.data.latency_ms != null"
              class="api-latency"
            >
              {{ entry.data.latency_ms }}ms
            </span>
          </template>
        </van-cell>
      </van-cell-group>

      <!-- 数据库信息 -->
      <p class="zx-section-title">数据库</p>
      <van-cell-group inset class="section-gap">
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
        class="save-btn"
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

    <!-- 密钥编辑弹窗 -->
    <van-dialog
      v-model:show="showSecretDialog"
      :title="`配置 ${editingSecret.label}`"
      show-cancel-button
      :confirm-button-text="savingSecret ? '保存中...' : '保存'"
      :confirm-button-disabled="savingSecret"
      @confirm="saveSecret"
      :before-close="(action: string) => action !== 'confirm' || !savingSecret"
    >
      <div class="dialog-body">
        <van-field
          v-model="editingSecret.value"
          type="password"
          placeholder="输入新的密钥值"
          clearable
        />
      </div>
    </van-dialog>
  </div>
</template>

<style scoped>
.section-gap {
  margin-bottom: var(--zx-space-md);
}

.day-checkbox {
  margin: 2px 4px;
}

/* ── 密钥 ── */

.secret-value {
  display: flex;
  align-items: center;
  gap: var(--zx-space-sm);
  flex-wrap: wrap;
  justify-content: flex-end;
}

.secret-masked {
  color: var(--zx-text-secondary);
  font-family: var(--zx-font-mono);
  font-size: var(--zx-text-xs);
}

.secret-unconfigured {
  color: var(--zx-text-disabled);
}

/* ── API 状态 ── */

.api-check-btn {
  padding: var(--zx-space-sm) var(--zx-space-base);
}

.api-latency {
  color: var(--zx-text-disabled);
  margin-left: var(--zx-space-xs);
  font-size: var(--zx-text-xs);
}

.api-error-detail {
  color: var(--zx-danger);
  margin-left: var(--zx-space-xs);
  font-size: var(--zx-text-xs);
}

/* ── 保存按钮 ── */

.save-btn {
  margin-top: var(--zx-space-lg);
}

/* ── 弹窗 ── */

.dialog-body {
  padding: var(--zx-space-base);
}
</style>
