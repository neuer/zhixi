import api from "@/api";
import { useAsyncData } from "@/composables/useAsyncData";
import type {
  AccountListResponse,
  AccountResponse,
} from "@zhixi/openapi-client";
import { showConfirmDialog, showToast } from "vant";
import { computed } from "vue";

export function useAccountActions() {
  const {
    data: rawData,
    loading,
    refreshing,
    error,
    execute: loadAccounts,
    refresh,
  } = useAsyncData(() =>
    api
      .get<AccountListResponse>("/accounts", {
        params: { page: 1, page_size: 100 },
      })
      .then((r) => r.data),
  );

  const accounts = computed(() => rawData.value?.items ?? []);
  const total = computed(() => rawData.value?.total ?? 0);

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
        await api.put(`/accounts/${account.id}`, { is_active: false });
      } else {
        await api.put(`/accounts/${account.id}`, { is_active: true });
      }
      showToast(`已${action}`);
      await loadAccounts();
    } catch {
      // 拦截器已处理
    }
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

  return {
    accounts,
    total,
    loading,
    refreshing,
    error,
    loadAccounts,
    refresh,
    toggleActive,
    handleDelete,
  };
}

export function formatLastFetch(dt: string | null): string {
  if (!dt) return "从未抓取";
  return new Date(dt).toLocaleString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
