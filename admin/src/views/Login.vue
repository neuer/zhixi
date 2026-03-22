<script setup lang="ts">
import api from "@/api";
import { AUTH_TOKEN_KEY } from "@/constants";
import type { LoginResponse } from "@zhixi/openapi-client";
import { showToast } from "vant";
import { ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const username = ref("");
const password = ref("");
const submitting = ref(false);

async function handleLogin() {
  if (!password.value.trim()) {
    showToast("请输入密码");
    return;
  }

  submitting.value = true;
  try {
    const resp = await api.post<LoginResponse>("/auth/login", {
      username: username.value,
      password: password.value,
    });
    localStorage.setItem(AUTH_TOKEN_KEY, resp.data.token);
    password.value = "";
    showToast("登录成功");
    router.replace({ name: "dashboard" });
  } catch {
    // 拦截器已处理
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-header">
      <div class="logo-mark">智</div>
      <h1 class="login-title">智曦</h1>
      <p class="login-subtitle">AI 知识日报平台</p>
    </div>

    <div class="login-body">
      <van-cell-group inset class="form-group">
        <van-field
          v-model="username"
          label="用户名"
          placeholder="admin"
          clearable
          left-icon="manager-o"
        />
        <van-field
          v-model="password"
          type="password"
          label="密码"
          placeholder="输入管理员密码"
          clearable
          left-icon="lock"
          @keyup.enter="handleLogin"
        />
      </van-cell-group>

      <van-button
        type="primary"
        block
        size="large"
        class="login-btn"
        :loading="submitting"
        :disabled="submitting || !password"
        @click="handleLogin"
      >
        登录
      </van-button>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  background: linear-gradient(
    175deg,
    var(--zx-primary-bg) 0%,
    #f7f8fc 40%,
    var(--zx-bg-card) 100%
  );
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0 var(--zx-space-lg);
}

.login-header {
  text-align: center;
  padding-top: 20vh;
  margin-bottom: var(--zx-space-2xl);
}

.logo-mark {
  width: 60px;
  height: 60px;
  margin: 0 auto var(--zx-space-md);
  border-radius: var(--zx-radius-md);
  background: var(--zx-primary);
  color: var(--zx-text-inverse);
  font-size: 28px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  letter-spacing: -1px;
  box-shadow: var(--zx-shadow-md);
}

.login-title {
  font-family: var(--zx-font-display);
  font-size: var(--zx-text-2xl);
  font-weight: 700;
  color: var(--zx-text-primary);
  margin: 0 0 var(--zx-space-xs);
}

.login-subtitle {
  font-size: var(--zx-text-sm);
  color: var(--zx-text-tertiary);
  margin: 0;
  letter-spacing: 0.08em;
}

.login-body {
  width: 100%;
  max-width: 400px;
}

.form-group {
  margin-bottom: var(--zx-space-xl);
}

.login-btn {
  margin-bottom: var(--zx-space-lg);
  font-weight: 500;
  letter-spacing: 0.05em;
}
</style>
