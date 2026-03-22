import { AUTH_TOKEN_KEY } from "@/constants";
import type { ValidationError } from "@zhixi/openapi-client";
import axios, { type AxiosError } from "axios";
import { showToast } from "vant";

interface ApiError {
  detail: string | ValidationError[];
}

function extractDetail(
  rawDetail: string | ValidationError[] | undefined,
): string {
  if (typeof rawDetail === "string") return rawDetail;
  if (Array.isArray(rawDetail)) return rawDetail.map((e) => e.msg).join("; ");
  return "未知错误";
}

let isRedirectingToLogin = false;

const api = axios.create({
  baseURL: "/api",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(AUTH_TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    // 网络级错误（无 response）
    if (!error.response) {
      if (error.code === "ECONNABORTED") {
        showToast("请求超时，请稍后重试");
      } else if (error.code === "ERR_NETWORK") {
        showToast("网络连接失败，请检查网络");
      } else {
        showToast("网络异常，请稍后重试");
      }
      return Promise.reject(error);
    }

    const status = error.response.status;
    const detail = extractDetail(error.response.data?.detail);

    if (status === 401) {
      // 签名链接路径不跳转登录
      const requestUrl = error.config?.url ?? "";
      if (requestUrl.includes("/digest/preview/")) {
        return Promise.reject(error);
      }

      if (!isRedirectingToLogin) {
        isRedirectingToLogin = true;
        localStorage.removeItem(AUTH_TOKEN_KEY);
        const { default: router } = await import("@/router");
        router.push("/login");
        showToast("登录已过期，请重新登录");
        // 导航完成后重置标志，比固定 setTimeout 更可靠
        const unregister = router.afterEach(() => {
          isRedirectingToLogin = false;
          unregister();
        });
      }
    } else if (status === 409 || status === 423) {
      showToast(detail);
    } else {
      showToast(`操作失败：${detail}`);
    }

    return Promise.reject(error);
  },
);

export default api;
