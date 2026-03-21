<script setup lang="ts">
import api from "@/api";
import { AUTH_TOKEN_KEY } from "@/constants";
import type { LoginResponse } from "@zhixi/openapi-client";
import { showToast } from "vant";
import { ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const username = ref("admin");
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
  background: linear-gradient(175deg, #f0f4ff 0%, #fafbff 40%, #fff 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0 20px;
}

.login-header {
  text-align: center;
  padding-top: 20vh;
  margin-bottom: 36px;
}

.logo-mark {
  width: 56px;
  height: 56px;
  margin: 0 auto 12px;
  border-radius: 14px;
  background: #3b5bdb;
  color: #fff;
  font-size: 26px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  letter-spacing: -1px;
}

.login-title {
  font-size: 24px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0 0 4px;
}

.login-subtitle {
  font-size: 13px;
  color: #8c8ca1;
  margin: 0;
}

.login-body {
  width: 100%;
  max-width: 400px;
}

.form-group {
  margin-bottom: 24px;
}

.login-btn {
  margin-bottom: 20px;
}
</style>
