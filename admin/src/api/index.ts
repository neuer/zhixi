import router from "@/router";
import axios, { type AxiosError } from "axios";
import { showToast } from "vant";

interface ApiError {
  detail: string;
}

const api = axios.create({
  baseURL: "/api",
  timeout: 300000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("zhixi_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail ?? "未知错误";

    if (status === 401) {
      localStorage.removeItem("zhixi_token");
      router.push("/login");
      showToast("登录已过期，请重新登录");
    } else if (status === 409 || status === 423) {
      showToast(detail);
    } else {
      showToast(`操作失败：${detail}`);
    }

    return Promise.reject(error);
  },
);

export default api;
