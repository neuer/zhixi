<script setup lang="ts">
import api from "@/api";
import { showToast } from "vant";
import { ref, watch } from "vue";

const props = defineProps<{ show: boolean }>();
const emit = defineEmits<{
  "update:show": [value: boolean];
  added: [];
}>();

const addForm = ref({ twitter_handle: "", weight: 1.0 });
const adding = ref(false);
const addError = ref("");
const manualMode = ref(false);
const manualForm = ref({ display_name: "", bio: "" });

function resetForm() {
  addForm.value = { twitter_handle: "", weight: 1.0 };
  manualMode.value = false;
  manualForm.value = { display_name: "", bio: "" };
  addError.value = "";
}

watch(
  () => props.show,
  (v) => {
    if (v) resetForm();
  },
);

async function handleAdd() {
  const handle = addForm.value.twitter_handle.trim().replace(/^@/, "");
  if (!handle) {
    showToast("请输入 Twitter 用户名");
    return;
  }
  if (handle.length > 50) {
    showToast("用户名长度不能超过 50");
    return;
  }
  addForm.value.twitter_handle = handle;

  adding.value = true;
  addError.value = "";
  try {
    const payload: Record<string, unknown> = {
      twitter_handle: handle,
      weight: addForm.value.weight,
    };
    if (manualMode.value) {
      payload.display_name = manualForm.value.display_name.trim() || handle;
      payload.bio = manualForm.value.bio.trim() || null;
    }

    await api.post("/accounts", payload);
    showToast("添加成功");
    emit("update:show", false);
    emit("added");
  } catch (e: unknown) {
    if (
      typeof e === "object" &&
      e !== null &&
      "response" in e &&
      typeof (e as Record<string, unknown>).response === "object"
    ) {
      const resp = (
        e as { response: { status: number; data: { allow_manual?: boolean } } }
      ).response;
      if (resp.status === 502 && resp.data?.allow_manual) {
        manualMode.value = true;
        addError.value = "X API 不可用，请手动填写信息";
        return;
      }
    }
  } finally {
    adding.value = false;
  }
}
</script>

<template>
  <van-popup
    :show="show"
    position="bottom"
    round
    :style="{ minHeight: '40vh' }"
    @update:show="emit('update:show', $event)"
    @close="resetForm"
  >
    <div class="popup-content">
      <h3 class="popup-title">添加大V账号</h3>

      <van-notice-bar
        v-if="addError"
        :color="'var(--zx-warning)'"
        :background="'var(--zx-warning-bg)'"
        left-icon="info-o"
        :text="addError"
        class="popup-notice"
      />

      <van-cell-group inset>
        <van-field
          v-model="addForm.twitter_handle"
          label="用户名"
          placeholder="Twitter handle（不含 @）"
          clearable
          :disabled="adding"
        />
        <van-cell title="权重">
          <template #value>
            <van-stepper
              v-model="addForm.weight"
              :min="0.1"
              :max="5.0"
              :step="0.1"
              :decimal-length="1"
            />
          </template>
        </van-cell>
      </van-cell-group>

      <van-cell-group v-if="manualMode" inset class="manual-group">
        <van-field
          v-model="manualForm.display_name"
          label="显示名"
          placeholder="手动输入显示名称"
          clearable
        />
        <van-field
          v-model="manualForm.bio"
          label="简介"
          placeholder="可选"
          clearable
        />
      </van-cell-group>

      <van-button
        type="primary"
        block
        size="large"
        :loading="adding"
        :disabled="adding || !addForm.twitter_handle.trim()"
        class="popup-btn"
        @click="handleAdd"
      >
        {{ manualMode ? "手动添加" : "添加" }}
      </van-button>
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

.popup-notice {
  margin-bottom: var(--zx-space-md);
}

.popup-btn {
  margin-top: var(--zx-space-base);
}

.manual-group {
  margin-top: var(--zx-space-md);
}
</style>
