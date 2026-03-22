<script setup lang="ts">
import api from "@/api";
import { formatLastFetch } from "@/composables/useAccountActions";
import type { AccountResponse } from "@zhixi/openapi-client";
import { showToast } from "vant";
import { ref, watch } from "vue";

const props = defineProps<{
  show: boolean;
  account: AccountResponse | null;
}>();

const emit = defineEmits<{
  "update:show": [value: boolean];
  saved: [];
  toggled: [account: AccountResponse];
}>();

const editWeight = ref(1.0);
const saving = ref(false);

watch(
  () => props.account,
  (acc) => {
    if (acc) editWeight.value = acc.weight;
  },
);

async function handleSaveWeight() {
  if (!props.account) return;
  saving.value = true;
  try {
    await api.put(`/accounts/${props.account.id}`, {
      weight: editWeight.value,
    });
    showToast("已更新");
    emit("update:show", false);
    emit("saved");
  } catch {
    // 拦截器已处理
  } finally {
    saving.value = false;
  }
}

function handleToggle() {
  if (!props.account) return;
  emit("toggled", props.account);
  emit("update:show", false);
}
</script>

<template>
  <van-popup
    :show="show"
    position="bottom"
    round
    :style="{ minHeight: '30vh' }"
    @update:show="emit('update:show', $event)"
  >
    <div v-if="account" class="popup-content">
      <h3 class="popup-title">
        @{{ account.twitter_handle }}
      </h3>
      <p class="popup-desc">{{ account.display_name }}</p>

      <van-cell-group inset>
        <van-cell title="权重">
          <template #value>
            <van-stepper
              v-model="editWeight"
              :min="0.1"
              :max="5.0"
              :step="0.1"
              :decimal-length="1"
            />
          </template>
        </van-cell>
        <van-cell
          title="粉丝数"
          :value="account.followers_count.toLocaleString()"
        />
        <van-cell
          title="最近抓取"
          :value="formatLastFetch(account.last_fetch_at)"
        />
      </van-cell-group>

      <div class="edit-actions">
        <van-button
          type="primary"
          block
          :loading="saving"
          @click="handleSaveWeight"
        >
          保存权重
        </van-button>
        <van-button
          :type="account.is_active ? 'warning' : 'success'"
          block
          plain
          @click="handleToggle"
        >
          {{ account.is_active ? "停用账号" : "启用账号" }}
        </van-button>
      </div>
    </div>
  </van-popup>
</template>

<style scoped>
.popup-content {
  padding: var(--zx-space-lg) var(--zx-space-base);
}

.popup-title {
  font-family: var(--zx-font-display);
  font-size: var(--zx-text-lg);
  font-weight: 600;
  color: var(--zx-text-primary);
  margin: 0 0 var(--zx-space-xs);
}

.popup-desc {
  font-size: var(--zx-text-sm);
  color: var(--zx-text-tertiary);
  margin: 0 0 var(--zx-space-base);
}

.edit-actions {
  display: flex;
  flex-direction: column;
  gap: var(--zx-space-sm);
  margin-top: var(--zx-space-base);
}
</style>
