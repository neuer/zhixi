<script setup lang="ts">
import api from "@/api";
import type { PerspectiveItem } from "@/utils/digest";
import { parsePerspectives } from "@/utils/digest";
import type {
  DigestItemResponse,
  MessageResponse,
  TodayResponse,
} from "@zhixi/openapi-client";
import { showConfirmDialog, showToast } from "vant";
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();

const VALID_ITEM_TYPES = ["tweet", "topic"] as const;
type ItemType = (typeof VALID_ITEM_TYPES)[number];

const itemType = computed<ItemType | null>(() => {
  const raw = route.params.type as string;
  return VALID_ITEM_TYPES.includes(raw as ItemType) ? (raw as ItemType) : null;
});
const itemRefId = computed(() => Number(route.params.id));

const loading = ref(true);
const refreshing = ref(false);
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

const parsedPerspectives = computed<PerspectiveItem[]>(() =>
  parsePerspectives(form.value.perspectives || null),
);

async function loadItem() {
  loading.value = true;
  error.value = null;

  if (
    itemType.value === null ||
    Number.isNaN(itemRefId.value) ||
    itemRefId.value <= 0
  ) {
    error.value = "无效的条目参数（type 必须为 tweet 或 topic）";
    loading.value = false;
    return;
  }

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
    error.value = "加载失败，下拉刷新重试";
  } finally {
    loading.value = false;
    refreshing.value = false;
  }
}

async function handleSave() {
  if (!item.value) return;
  saving.value = true;
  try {
    const fieldMap: Array<{
      key: keyof typeof form.value;
      snapshot: keyof DigestItemResponse;
    }> = [
      { key: "title", snapshot: "snapshot_title" },
      { key: "translation", snapshot: "snapshot_translation" },
      { key: "summary", snapshot: "snapshot_summary" },
      { key: "perspectives", snapshot: "snapshot_perspectives" },
      { key: "comment", snapshot: "snapshot_comment" },
    ];

    const payload: Record<string, string> = {};
    for (const { key, snapshot } of fieldMap) {
      if (form.value[key] !== ((item.value[snapshot] as string | null) ?? "")) {
        payload[key] = form.value[key];
      }
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
    await api.post<MessageResponse>(
      `/digest/${endpoint}/${itemType.value}/${itemRefId.value}`,
    );
    showToast(`已${action}`);
    router.back();
  } catch {
    // 拦截器已处理
  }
}

onMounted(loadItem);
</script>

<template>
  <div class="zx-page edit-page">
    <van-nav-bar
      title="编辑内容"
      left-text="返回"
      left-arrow
      @click-left="router.back()"
    />

    <van-pull-refresh v-model="refreshing" @refresh="loadItem">
      <van-empty v-if="!loading && error" :description="error" image="error" />

      <template v-else-if="item">
        <div class="zx-page-content">
          <!-- 条目信息卡 -->
          <div class="info-card zx-card section-gap">
            <div class="info-row">
              <span class="info-label">类型</span>
              <span class="info-value">{{ isTopic ? '聚合话题' : '推文' }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">热度</span>
              <span class="info-heat">🔥 {{ Math.round(item.snapshot_heat_score) }}</span>
            </div>
            <div v-if="item.snapshot_author_handle" class="info-row">
              <span class="info-label">作者</span>
              <span class="info-value">@{{ item.snapshot_author_handle }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">状态</span>
              <div>
                <van-tag v-if="item.is_excluded" type="warning">已剔除</van-tag>
                <van-tag v-else-if="item.is_pinned" type="primary">置顶</van-tag>
                <van-tag v-else type="success">正常</van-tag>
              </div>
            </div>
          </div>

          <!-- 不可编辑提示 -->
          <van-notice-bar
            v-if="!isEditable"
            :color="'var(--zx-text-tertiary)'"
            :background="'var(--zx-bg-elevated)'"
            left-icon="info-o"
            text="当前草稿非 draft 状态，不可编辑"
            class="section-gap"
          />

          <!-- 编辑表单 -->
          <p class="zx-section-title">内容编辑</p>
          <van-cell-group inset class="section-gap">
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
            <!-- 各方观点：可编辑时显示 JSON textarea，只读时渲染可读列表 -->
            <van-field
              v-if="isTopic && isEditable"
              v-model="form.perspectives"
              label="各方观点"
              type="textarea"
              placeholder="JSON 格式"
              :rows="4"
              autosize
              maxlength="5000"
            />
            <template v-if="isTopic && !isEditable && parsedPerspectives.length">
              <div class="perspectives-section">
                <div class="perspectives-header">各方观点</div>
                <div
                  v-for="(p, pi) in parsedPerspectives"
                  :key="pi"
                  class="perspective-item"
                >
                  <div v-if="p.author || p.handle" class="perspective-author">
                    {{ p.author }}<span v-if="p.handle" class="perspective-handle">@{{ p.handle }}</span>
                  </div>
                  <div class="perspective-text">{{ p.viewpoint }}</div>
                </div>
              </div>
            </template>
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
.section-gap {
  margin-bottom: var(--zx-space-base);
}

/* ── 信息卡片 ── */

.info-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--zx-space-sm) 0;
}

.info-row + .info-row {
  border-top: 1px solid var(--zx-border-light);
}

.info-label {
  font-size: var(--zx-text-sm);
  color: var(--zx-text-tertiary);
}

.info-value {
  font-size: var(--zx-text-sm);
  color: var(--zx-text-secondary);
}

.info-heat {
  color: var(--zx-accent);
  font-weight: 700;
  font-size: var(--zx-text-base);
}

/* ── 各方观点只读展示 ── */

.perspectives-section {
  background: var(--zx-bg-card);
  border-radius: var(--zx-radius-md);
  box-shadow: var(--zx-shadow-xs);
  padding: var(--zx-space-base);
  margin-bottom: var(--zx-space-base);
}

.perspectives-header {
  font-size: var(--zx-text-sm);
  color: var(--zx-primary);
  font-weight: 600;
  margin-bottom: var(--zx-space-md);
  letter-spacing: 0.03em;
}

.perspective-item {
  padding: var(--zx-space-md);
  background: var(--zx-bg-elevated);
  border-radius: var(--zx-radius-sm);
  border-left: 3px solid var(--zx-primary-lighter);
  margin-bottom: var(--zx-space-sm);
}

.perspective-item:last-child {
  margin-bottom: 0;
}

.perspective-author {
  font-size: var(--zx-text-sm);
  font-weight: 600;
  color: var(--zx-text-primary);
  margin-bottom: var(--zx-space-xs);
}

.perspective-handle {
  color: var(--zx-text-tertiary);
  font-weight: 400;
  margin-left: var(--zx-space-xs);
}

.perspective-text {
  font-size: var(--zx-text-sm);
  color: var(--zx-text-secondary);
  line-height: 1.6;
}

/* ── 操作按钮 ── */

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: var(--zx-space-sm);
  margin-top: var(--zx-space-xs);
}
</style>
