import api from "@/api";
import type { ApiStatusResponse } from "@zhixi/openapi-client";
import { closeToast, showLoadingToast } from "vant";
import { computed, ref } from "vue";

const apiStatusMap: Record<string, { text: string; color: string }> = {
  ok: { text: "正常", color: "var(--zx-success)" },
  error: { text: "异常", color: "var(--zx-danger)" },
};
const apiStatusDefault = { text: "未配置", color: "var(--zx-text-disabled)" };

export function useApiStatus() {
  const apiStatus = ref<ApiStatusResponse | null>(null);
  const checkingApi = ref(false);

  const apiEntries = computed(() => {
    if (!apiStatus.value) return [];
    return [
      { label: "X API", data: apiStatus.value.x_api },
      { label: "Claude API", data: apiStatus.value.claude_api },
      { label: "Gemini API", data: apiStatus.value.gemini_api },
      { label: "微信 API", data: apiStatus.value.wechat_api },
    ].filter((e) => e.data != null);
  });

  async function checkApiStatus() {
    checkingApi.value = true;
    showLoadingToast({ message: "检测中...", duration: 0 });
    try {
      const resp = await api.get<ApiStatusResponse>("/settings/api-status");
      apiStatus.value = resp.data;
      closeToast();
    } catch {
      closeToast();
    } finally {
      checkingApi.value = false;
    }
  }

  function getApiStatus(status: string) {
    return apiStatusMap[status] ?? apiStatusDefault;
  }

  return {
    apiStatus,
    checkingApi,
    apiEntries,
    checkApiStatus,
    getApiStatus,
  };
}
