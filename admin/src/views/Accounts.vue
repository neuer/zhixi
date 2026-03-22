<script setup lang="ts">
import AccountAddPopup from "@/components/AccountAddPopup.vue";
import AccountEditPopup from "@/components/AccountEditPopup.vue";
import {
  formatLastFetch,
  useAccountActions,
} from "@/composables/useAccountActions";
import type { AccountResponse } from "@zhixi/openapi-client";
import { ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const {
  accounts,
  total,
  loading,
  refreshing,
  error,
  loadAccounts,
  refresh,
  toggleActive,
  handleDelete,
} = useAccountActions();

const showAddDialog = ref(false);
const showEditDialog = ref(false);
const editingAccount = ref<AccountResponse | null>(null);

function openEdit(account: AccountResponse) {
  editingAccount.value = account;
  showEditDialog.value = true;
}

async function handleToggled(account: AccountResponse) {
  await toggleActive(account);
}
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
        <van-button type="primary" size="mini" @click="showAddDialog = true">
          添加
        </van-button>
      </template>
    </van-nav-bar>

    <van-pull-refresh v-model="refreshing" @refresh="refresh">
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

    <AccountAddPopup
      v-model:show="showAddDialog"
      @added="loadAccounts()"
    />

    <AccountEditPopup
      v-model:show="showEditDialog"
      :account="editingAccount"
      @saved="loadAccounts()"
      @toggled="handleToggled"
    />
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
</style>
