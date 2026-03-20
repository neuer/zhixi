import api from "@/api";
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
let setupStatus: boolean | null = null;

function isWhiteListed(to: RouteLocationNormalized): boolean {
  return WHITE_LIST.some((path) => to.path.startsWith(path));
}

router.beforeEach(async (to) => {
  if (isWhiteListed(to)) {
    return true;
  }

  if (setupStatus === null) {
    try {
      const { data } = await api.get<{ need_setup: boolean }>("/setup/status");
      setupStatus = data.need_setup;
    } catch {
      return "/login";
    }
  }

  if (setupStatus) {
    return "/setup";
  }

  const token = localStorage.getItem("zhixi_token");
  if (!token) {
    return "/login";
  }

  return true;
});

export default router;

/** 重置 setup 缓存（设置完成后调用）。 */
export function resetSetupCache(): void {
  setupStatus = null;
}
