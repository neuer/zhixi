<script setup lang="ts">
import api from "@/api";
import type { DigestItemResponse, TodayResponse } from "@zhixi/openapi-client";
import { showConfirmDialog, showToast } from "vant";
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();

const itemType = computed(() => route.params.type as string);
const itemRefId = computed(() => Number(route.params.id));

const loading = ref(true);
const saving = ref(false);
const error = ref<string | null>(null);
const item = ref<DigestItemResponse | null>(null);
const digestStatus = ref<string | null>(null);

// 表单数据
const form = ref({
  title: "",
  translation: "",
  summary: "",
  perspectives: "",
  comment: "",
});

const isEditable = computed(() => digestStatus.value === "draft");

const isTopic = computed(
  () => item.value?.snapshot_topic_type === "aggregated",
);

async function loadItem() {
  loading.value = true;
  error.value = null;
  try {
    const resp = await api.get<TodayResponse>("/digest/today");
    digestStatus.value = resp.data.digest?.status ?? null;

    const found = resp.data.items.find(
      (i) =>
        i.item_type === itemType.value && i.item_ref_id === itemRefId.value,
    );
    if (!found) {
      error.value = "条目不存在";
      return;
    }
    item.value = found;
    form.value = {
      title: found.snapshot_title ?? "",
      translation: found.snapshot_translation ?? "",
      summary: found.snapshot_summary ?? "",
      perspectives: found.snapshot_perspectives ?? "",
      comment: found.snapshot_comment ?? "",
    };
  } catch {
    error.value = "加载失败";
  } finally {
    loading.value = false;
  }
}

async function handleSave() {
  if (!item.value) return;
  saving.value = true;
  try {
    const payload: Record<string, string | null> = {};
    if (form.value.title !== (item.value.snapshot_title ?? "")) {
      payload.title = form.value.title || null;
    }
    if (form.value.translation !== (item.value.snapshot_translation ?? "")) {
      payload.translation = form.value.translation || null;
    }
    if (form.value.summary !== (item.value.snapshot_summary ?? "")) {
      payload.summary = form.value.summary || null;
    }
    if (form.value.perspectives !== (item.value.snapshot_perspectives ?? "")) {
      payload.perspectives = form.value.perspectives || null;
    }
    if (form.value.comment !== (item.value.snapshot_comment ?? "")) {
      payload.comment = form.value.comment || null;
    }

    if (Object.keys(payload).length === 0) {
      showToast("没有修改");
      return;
    }

    const resp = await api.put<DigestItemResponse>(
      `/digest/item/${itemType.value}/${itemRefId.value}`,
      payload,
    );
    item.value = resp.data;
    showToast("已保存");
    router.back();
  } catch {
    // 拦截器已处理
  } finally {
    saving.value = false;
  }
}

async function handleExclude() {
  if (!item.value) return;
  const action = item.value.is_excluded ? "恢复" : "剔除";
  try {
    await showConfirmDialog({
      title: `${action}条目`,
      message: `确定${action}该条目？`,
    });
  } catch {
    return;
  }

  try {
    const endpoint = item.value.is_excluded ? "restore" : "exclude";
    await api.post(`/digest/${endpoint}/${itemType.value}/${itemRefId.value}`);
    showToast(`已${action}`);
    router.back();
  } catch {
    // 拦截器已处理
  }
}

onMounted(loadItem);
</script>

<template>
  <div class="edit-page">
    <van-nav-bar
      title="编辑内容"
      left-text="返回"
      left-arrow
      @click-left="router.back()"
    />

    <van-pull-refresh v-model="loading" @refresh="loadItem">
      <van-empty v-if="!loading && error" :description="error" image="error" />

      <template v-else-if="item">
        <div class="page-content">
          <!-- 条目信息卡 -->
          <van-cell-group inset class="section-gap">
            <van-cell
              title="类型"
              :value="isTopic ? '聚合话题' : '推文'"
            />
            <van-cell title="热度">
              <template #value>
                <span class="heat-score">
                  🔥 {{ Math.round(item.snapshot_heat_score) }}
                </span>
              </template>
            </van-cell>
            <van-cell
              v-if="item.snapshot_author_handle"
              title="作者"
              :value="`@${item.snapshot_author_handle}`"
            />
            <van-cell title="状态">
              <template #value>
                <van-tag v-if="item.is_excluded" type="warning">已剔除</van-tag>
                <van-tag v-else-if="item.is_pinned" type="primary">置顶</van-tag>
                <van-tag v-else type="success">正常</van-tag>
              </template>
            </van-cell>
          </van-cell-group>

          <!-- 不可编辑提示 -->
          <van-notice-bar
            v-if="!isEditable"
            color="#969799"
            background="#f7f8fa"
            left-icon="info-o"
            text="当前草稿非 draft 状态，不可编辑"
            class="section-gap"
          />

          <!-- 编辑表单 -->
          <van-cell-group inset title="内容编辑" class="section-gap">
            <van-field
              v-model="form.title"
              label="标题"
              placeholder="条目标题"
              clearable
              :disabled="!isEditable"
              maxlength="200"
              show-word-limit
            />
            <van-field
              v-if="!isTopic"
              v-model="form.translation"
              label="翻译"
              type="textarea"
              placeholder="中文翻译"
              :rows="4"
              autosize
              :disabled="!isEditable"
              maxlength="5000"
              show-word-limit
            />
            <van-field
              v-if="isTopic"
              v-model="form.summary"
              label="摘要"
              type="textarea"
              placeholder="话题摘要"
              :rows="3"
              autosize
              :disabled="!isEditable"
              maxlength="2000"
              show-word-limit
            />
            <van-field
              v-if="isTopic"
              v-model="form.perspectives"
              label="各方观点"
              type="textarea"
              placeholder="JSON 格式"
              :rows="4"
              autosize
              :disabled="!isEditable"
              maxlength="5000"
            />
            <van-field
              v-model="form.comment"
              label="点评"
              type="textarea"
              placeholder="AI 点评内容"
              :rows="3"
              autosize
              :disabled="!isEditable"
              maxlength="2000"
              show-word-limit
            />
          </van-cell-group>

          <!-- 操作按钮 -->
          <div v-if="isEditable" class="action-buttons">
            <van-button
              type="primary"
              block
              size="large"
              :loading="saving"
              :disabled="saving"
              @click="handleSave"
            >
              保存修改
            </van-button>
            <van-button
              :type="item.is_excluded ? 'success' : 'warning'"
              block
              plain
              @click="handleExclude"
            >
              {{ item.is_excluded ? "恢复条目" : "剔除条目" }}
            </van-button>
          </div>
        </div>
      </template>
    </van-pull-refresh>
  </div>
</template>

<style scoped>
.edit-page {
  background: #f7f8fa;
  min-height: 100vh;
}

.page-content {
  padding: 12px;
}

.section-gap {
  margin-bottom: 12px;
}

.heat-score {
  color: #ff976a;
  font-size: 14px;
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 4px;
}
</style>
