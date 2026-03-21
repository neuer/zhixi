import api from "@/api";
import { AUTH_TOKEN_KEY } from "@/constants";
import type { SetupStatusResponse } from "@zhixi/openapi-client";
import axios from "axios";
import {
  type RouteLocationNormalized,
  createRouter,
  createWebHistory,
} from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/setup",
      name: "setup",
      component: () => import("@/views/Setup.vue"),
    },
    {
      path: "/login",
      name: "login",
      component: () => import("@/views/Login.vue"),
    },
    {
      path: "/dashboard",
      name: "dashboard",
      component: () => import("@/views/Dashboard.vue"),
    },
    {
      path: "/accounts",
      name: "accounts",
      component: () => import("@/views/Accounts.vue"),
    },
    {
      path: "/digest",
      name: "digest",
      component: () => import("@/views/Digest.vue"),
    },
    {
      path: "/digest/edit/:type/:id",
      name: "digest-edit",
      component: () => import("@/views/DigestEdit.vue"),
    },
    {
      path: "/history",
      name: "history",
      component: () => import("@/views/History.vue"),
    },
    {
      path: "/history/:id",
      name: "history-detail",
      component: () => import("@/views/HistoryDetail.vue"),
    },
    {
      path: "/settings",
      name: "settings",
      component: () => import("@/views/Settings.vue"),
    },
    {
      path: "/costs",
      name: "costs",
      component: () => import("@/views/ApiCosts.vue"),
    },
    {
      path: "/logs",
      name: "logs",
      component: () => import("@/views/Logs.vue"),
    },
    {
      path: "/preview",
      name: "preview",
      component: () => import("@/views/Preview.vue"),
    },
    {
      path: "/",
      redirect: "/dashboard",
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: "/dashboard",
    },
  ],
});

const WHITE_LIST = ["/setup", "/login", "/preview"];
const SETUP_CACHE_TTL_MS = 5 * 60 * 1000;
let setupCache: { needSetup: boolean; fetchedAt: number } | null = null;

function isWhiteListed(to: RouteLocationNormalized): boolean {
  return WHITE_LIST.some((path) => to.path.startsWith(path));
}

router.beforeEach(async (to) => {
  if (isWhiteListed(to)) {
    return true;
  }

  if (!setupCache || Date.now() - setupCache.fetchedAt > SETUP_CACHE_TTL_MS) {
    try {
      const { data } = await api.get<SetupStatusResponse>("/setup/status");
      setupCache = { needSetup: data.need_setup, fetchedAt: Date.now() };
    } catch (e: unknown) {
      if (axios.isAxiosError(e) && e.response?.status === 401) {
        return "/login";
      }
      // 非认证错误：放行导航，让页面自身处理
      return true;
    }
  }

  if (setupCache.needSetup) {
    return "/setup";
  }

  const token = localStorage.getItem(AUTH_TOKEN_KEY);
  if (!token) {
    return "/login";
  }

  return true;
});

export default router;

/** 重置 setup 缓存（设置完成后调用）。 */
export function resetSetupCache(): void {
  setupCache = null;
}
