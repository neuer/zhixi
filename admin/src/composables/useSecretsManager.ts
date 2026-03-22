import api from "@/api";
import type {
  SecretStatusItem,
  SecretsStatusResponse,
} from "@zhixi/openapi-client";
import { showConfirmDialog, showToast } from "vant";
import { ref } from "vue";

export function useSecretsManager(onSecretChanged?: () => Promise<void>) {
  const secretsStatus = ref<SecretStatusItem[]>([]);
  const showSecretDialog = ref(false);
  const editingSecret = ref({ key: "", label: "", value: "" });
  const savingSecret = ref(false);

  async function loadSecretsStatus() {
    try {
      const resp = await api.get<SecretsStatusResponse>(
        "/settings/secrets-status",
      );
      secretsStatus.value = resp.data.items;
    } catch {
      showToast("密钥状态加载失败");
    }
  }

  function openSecretDialog(item: SecretStatusItem) {
    editingSecret.value = { key: item.key, label: item.label, value: "" };
    showSecretDialog.value = true;
  }

  async function saveSecret() {
    if (!editingSecret.value.value.trim()) {
      showToast("请输入密钥值");
      return;
    }
    savingSecret.value = true;
    try {
      await api.put("/settings/secrets", {
        [editingSecret.value.key]: editingSecret.value.value.trim(),
      });
      showToast("密钥已保存");
      showSecretDialog.value = false;
      await loadSecretsStatus();
      await onSecretChanged?.();
    } catch {
      // 拦截器已处理
    } finally {
      savingSecret.value = false;
    }
  }

  async function clearSecret(item: SecretStatusItem) {
    try {
      await showConfirmDialog({
        title: "清除密钥",
        message: `确定清除 ${item.label} 的 DB 配置？将恢复使用 .env 中的值（如有）。`,
      });
    } catch {
      // 用户取消确认对话框
      return;
    }
    try {
      await api.delete(`/settings/secrets/${item.key}`);
      showToast("密钥已清除");
      await loadSecretsStatus();
      await onSecretChanged?.();
    } catch {
      // 拦截器已处理 API 错误
    }
  }

  return {
    secretsStatus,
    showSecretDialog,
    editingSecret,
    savingSecret,
    loadSecretsStatus,
    openSecretDialog,
    saveSecret,
    clearSecret,
  };
}

export function getSourceLabel(source: string): string {
  if (source === "db") return "后台配置";
  if (source === "env") return "环境变量";
  return "";
}
