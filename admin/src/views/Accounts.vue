<script setup lang="ts">
import api from "@/api";
import type {
  AccountListResponse,
  AccountResponse,
} from "@zhixi/openapi-client";
import { showConfirmDialog, showToast } from "vant";
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const loading = ref(true);
const accounts = ref<AccountResponse[]>([]);
const total = ref(0);
const error = ref<string | null>(null);

// 添加账号弹窗
const showAddDialog = ref(false);
const addForm = ref({ twitter_handle: "", weight: 1.0 });
const adding = ref(false);
const addError = ref("");

// 手动模式（X API 不可用时降级）
const manualMode = ref(false);
const manualForm = ref({ display_name: "", bio: "" });

// 编辑权重弹窗
const showEditDialog = ref(false);
const editingAccount = ref<AccountResponse | null>(null);
const editWeight = ref(1.0);
const saving = ref(false);

async function loadAccounts() {
  loading.value = true;
  error.value = null;
  try {
    const resp = await api.get<AccountListResponse>("/accounts", {
      params: { page: 1, page_size: 100 },
    });
    accounts.value = resp.data.items;
    total.value = resp.data.total;
  } catch {
    error.value = "加载失败，下拉刷新重试";
  } finally {
    loading.value = false;
  }
}

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
    showAddDialog.value = false;
    resetAddForm();
    await loadAccounts();
  } catch (e: unknown) {
    // 502 且 allow_manual 时提示手动模式
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
    // 其他错误由拦截器处理
  } finally {
    adding.value = false;
  }
}

function resetAddForm() {
  addForm.value = { twitter_handle: "", weight: 1.0 };
  manualMode.value = false;
  manualForm.value = { display_name: "", bio: "" };
  addError.value = "";
}

function openAdd() {
  resetAddForm();
  showAddDialog.value = true;
}

function openEdit(account: AccountResponse) {
  editingAccount.value = account;
  editWeight.value = account.weight;
  showEditDialog.value = true;
}

async function handleSaveWeight() {
  if (!editingAccount.value) return;
  saving.value = true;
  try {
    await api.put(`/accounts/${editingAccount.value.id}`, {
      weight: editWeight.value,
    });
    showToast("已更新");
    showEditDialog.value = false;
    await loadAccounts();
  } catch {
    // 拦截器已处理
  } finally {
    saving.value = false;
  }
}

async function toggleActive(account: AccountResponse) {
  const action = account.is_active ? "停用" : "启用";
  try {
    await showConfirmDialog({
      title: `${action}账号`,
      message: `确定${action} @${account.twitter_handle}？`,
    });
  } catch {
    return;
  }

  try {
    if (account.is_active) {
      await api.delete(`/accounts/${account.id}`);
    } else {
      await api.put(`/accounts/${account.id}`, { is_active: true });
    }
    showToast(`已${action}`);
    await loadAccounts();
  } catch {
    // 拦截器已处理
  }
}

async function handleToggleActiveAndClose(account: AccountResponse) {
  await toggleActive(account);
  showEditDialog.value = false;
}

async function handleDelete(account: AccountResponse) {
  try {
    await showConfirmDialog({
      title: "删除账号",
      message: `确定永久删除 @${account.twitter_handle}？`,
    });
  } catch {
    return;
  }
  try {
    await api.delete(`/accounts/${account.id}`);
    showToast("已删除");
    await loadAccounts();
  } catch {
    // 拦截器已处理
  }
}

function formatLastFetch(dt: string | null): string {
  if (!dt) return "从未抓取";
  return new Date(dt).toLocaleString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

onMounted(loadAccounts);
</script>

<template>
  <div class="zx-page accounts-page">
    <van-nav-bar
      title="大V账号管理"
      left-text="返回"
      left-arrow
      @click-left="router.back()"
    >
      <template #right>
        <van-button type="primary" size="mini" @click="openAdd">
          添加
        </van-button>
      </template>
    </van-nav-bar>

    <van-pull-refresh v-model="loading" @refresh="loadAccounts">
      <van-empty v-if="!loading && error" :description="error" image="error" />

      <van-empty
        v-else-if="!loading && accounts.length === 0"
        description="暂无账号，点击右上角添加"
      />

      <div v-else class="zx-page-content">
        <p class="zx-section-title">共 {{ total }} 个账号</p>
        <div class="account-list">
          <van-swipe-cell
            v-for="account in accounts"
            :key="account.id"
          >
            <div
              class="account-card"
              @click="openEdit(account)"
            >
              <div class="account-avatar">
                {{ account.twitter_handle.charAt(0).toUpperCase() }}
              </div>
              <div class="account-info">
                <div class="account-handle">@{{ account.twitter_handle }}</div>
                <div class="account-name">{{ account.display_name }}</div>
              </div>
              <div class="account-end">
                <van-tag
                  :type="account.is_active ? 'success' : 'default'"
                  size="medium"
                >
                  {{ account.is_active ? "活跃" : "停用" }}
                </van-tag>
                <span class="weight-badge">{{ account.weight }}x</span>
                <span class="fetch-time">
                  {{ formatLastFetch(account.last_fetch_at) }}
                </span>
              </div>
            </div>
            <template #right>
              <van-button
                square
                :type="account.is_active ? 'warning' : 'success'"
                class="swipe-btn"
                @click="toggleActive(account)"
              >
                {{ account.is_active ? "停用" : "启用" }}
              </van-button>
              <van-button
                square
                type="danger"
                class="swipe-btn"
                @click="handleDelete(account)"
              >
                删除
              </van-button>
            </template>
          </van-swipe-cell>
        </div>
      </div>
    </van-pull-refresh>

    <!-- 添加账号弹窗 -->
    <van-popup
      v-model:show="showAddDialog"
      position="bottom"
      round
      :style="{ minHeight: '40vh' }"
      @close="resetAddForm"
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

        <!-- 手动模式补充信息 -->
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

    <!-- 编辑权重弹窗 -->
    <van-popup
      v-model:show="showEditDialog"
      position="bottom"
      round
      :style="{ minHeight: '30vh' }"
    >
      <div v-if="editingAccount" class="popup-content">
        <h3 class="popup-title">
          @{{ editingAccount.twitter_handle }}
        </h3>
        <p class="popup-desc">{{ editingAccount.display_name }}</p>

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
            :value="editingAccount.followers_count.toLocaleString()"
          />
          <van-cell
            title="最近抓取"
            :value="formatLastFetch(editingAccount.last_fetch_at)"
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
            :type="editingAccount.is_active ? 'warning' : 'success'"
            block
            plain
            @click="handleToggleActiveAndClose(editingAccount)"
          >
            {{ editingAccount.is_active ? "停用账号" : "启用账号" }}
          </van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
/* ── 账号列表 ── */

.account-list {
  display: flex;
  flex-direction: column;
  gap: var(--zx-space-sm);
}

.account-card {
  display: flex;
  align-items: center;
  gap: var(--zx-space-md);
  background: var(--zx-bg-card);
  border-radius: var(--zx-radius-md);
  box-shadow: var(--zx-shadow-xs);
  padding: var(--zx-space-md) var(--zx-space-base);
  cursor: pointer;
  transition: box-shadow var(--zx-duration-fast) var(--zx-easing);
}

.account-card:active {
  box-shadow: var(--zx-shadow-sm);
}

.account-avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--zx-radius-full);
  background: var(--zx-primary-bg);
  color: var(--zx-primary);
  font-weight: 700;
  font-size: var(--zx-text-base);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.account-info {
  flex: 1;
  min-width: 0;
}

.account-handle {
  font-size: var(--zx-text-base);
  font-weight: 500;
  color: var(--zx-text-primary);
}

.account-name {
  font-size: var(--zx-text-xs);
  color: var(--zx-text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-end {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--zx-space-xs);
  flex-shrink: 0;
}

.weight-badge {
  font-size: var(--zx-text-xs);
  color: var(--zx-accent);
  font-weight: 700;
}

.fetch-time {
  font-size: var(--zx-text-xs);
  color: var(--zx-text-disabled);
}

/* ── 滑动按钮 ── */

.swipe-btn {
  height: 100%;
  min-width: 64px;
  font-size: var(--zx-text-sm);
}

/* ── 弹窗 ── */

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

.popup-notice {
  margin-bottom: var(--zx-space-md);
}

.popup-btn {
  margin-top: var(--zx-space-base);
}

.manual-group {
  margin-top: var(--zx-space-md);
}

.edit-actions {
  display: flex;
  flex-direction: column;
  gap: var(--zx-space-sm);
  margin-top: var(--zx-space-base);
}
</style>
