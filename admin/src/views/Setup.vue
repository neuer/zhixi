<script setup lang="ts">
import api from "@/api";
import { AUTH_TOKEN_KEY } from "@/constants";
import { resetSetupCache } from "@/router";
import type { LoginResponse } from "@zhixi/openapi-client";
import { showToast } from "vant";
import { ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const password = ref("");
const confirmPassword = ref("");
const webhookUrl = ref("");
const submitting = ref(false);
const step = ref(1);

function validatePassword(): string | null {
  const pwd = password.value;
  if (!pwd.trim()) return "请输入管理员密码";
  if (pwd.length < 8) return "密码长度至少 8 位";
  if (!/[A-Z]/.test(pwd)) return "密码必须包含大写字母";
  if (!/[a-z]/.test(pwd)) return "密码必须包含小写字母";
  if (!/\d/.test(pwd)) return "密码必须包含数字";
  if (pwd !== confirmPassword.value) return "两次密码不一致";
  return null;
}

function goNextStep() {
  const err = validatePassword();
  if (err) {
    showToast(err);
    return;
  }
  step.value = 2;
}

async function handleSubmit() {
  const err = validatePassword();
  if (err) {
    showToast(err);
    return;
  }

  submitting.value = true;
  try {
    await api.post("/setup/init", {
      password: password.value,
      notification_webhook_url: webhookUrl.value.trim() || null,
    });
    resetSetupCache();

    // 自动登录
    const resp = await api.post<LoginResponse>("/auth/login", {
      username: "admin",
      password: password.value,
    });
    localStorage.setItem(AUTH_TOKEN_KEY, resp.data.token);
    showToast("初始化完成");
    router.replace({ name: "dashboard" });
  } catch {
    // 拦截器已处理
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="setup-page">
    <div class="setup-header">
      <div class="logo-mark">智</div>
      <h1 class="setup-title">智曦</h1>
      <p class="setup-subtitle">AI 知识日报平台</p>
    </div>

    <div class="setup-body">
      <div class="step-indicator">
        <div class="step-dot" :class="{ active: step >= 1 }" />
        <div class="step-line" :class="{ active: step >= 2 }" />
        <div class="step-dot" :class="{ active: step >= 2 }" />
      </div>

      <!-- 第一步：设置密码 -->
      <template v-if="step === 1">
        <h2 class="form-heading">设置管理员密码</h2>
        <p class="form-desc">首次使用需要设置密码，用于后续登录管理后台</p>

        <van-cell-group inset class="form-group">
          <van-field
            v-model="password"
            type="password"
            label="密码"
            placeholder="至少 8 位，含大小写字母和数字"
            clearable
            maxlength="128"
          />
          <van-field
            v-model="confirmPassword"
            type="password"
            label="确认密码"
            placeholder="再次输入密码"
            clearable
            maxlength="128"
            @keyup.enter="goNextStep"
          />
        </van-cell-group>

        <van-button
          type="primary"
          block
          size="large"
          class="next-btn"
          :disabled="!password || !confirmPassword"
          @click="goNextStep"
        >
          下一步
        </van-button>
      </template>

      <!-- 第二步：可选配置 -->
      <template v-if="step === 2">
        <h2 class="form-heading">通知配置（可选）</h2>
        <p class="form-desc">配置企业微信 Webhook，用于接收系统通知</p>

        <van-cell-group inset class="form-group">
          <van-field
            v-model="webhookUrl"
            label="Webhook"
            placeholder="企业微信 Webhook URL"
            clearable
          />
        </van-cell-group>

        <van-button
          type="primary"
          block
          size="large"
          class="next-btn"
          :loading="submitting"
          :disabled="submitting"
          @click="handleSubmit"
        >
          完成设置
        </van-button>

        <van-button
          type="default"
          block
          size="large"
          class="back-btn"
          :disabled="submitting"
          @click="step = 1"
        >
          上一步
        </van-button>
      </template>
    </div>
  </div>
</template>

<style scoped>
.setup-page {
  min-height: 100vh;
  background: linear-gradient(175deg, #f0f4ff 0%, #fafbff 40%, #fff 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0 20px;
}

.setup-header {
  text-align: center;
  padding-top: 15vh;
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

.setup-title {
  font-size: 24px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0 0 4px;
}

.setup-subtitle {
  font-size: 13px;
  color: #8c8ca1;
  margin: 0;
}

.setup-body {
  width: 100%;
  max-width: 400px;
}

.step-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin-bottom: 24px;
}

.step-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #d0d5dd;
  transition: background 0.2s;
}

.step-dot.active {
  background: #3b5bdb;
}

.step-line {
  width: 40px;
  height: 2px;
  background: #d0d5dd;
  transition: background 0.2s;
}

.step-line.active {
  background: #3b5bdb;
}

.form-heading {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0 0 6px;
}

.form-desc {
  font-size: 13px;
  color: #8c8ca1;
  margin: 0 0 16px;
  line-height: 1.5;
}

.form-group {
  margin-bottom: 20px;
}

.next-btn {
  margin-bottom: 10px;
}

.back-btn {
  margin-bottom: 20px;
}
</style>
