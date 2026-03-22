<script setup lang="ts">
import api from "@/api";
import type { RawTweet } from "@zhixi/openapi-client";
import { showToast } from "vant";
import { ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

// ── 实验记录类型 ──
interface ExperimentLog {
  id: number;
  label: string;
  timestamp: string;
  latencyMs: number | null;
  status: "ok" | "error";
  summary: string;
  tweets: RawTweet[] | null;
  rawJson: string;
  expanded: boolean;
  showRaw: boolean;
}

let logIdSeq = 0;
const logs = ref<ExperimentLog[]>([]);

function addLog(
  label: string,
  status: "ok" | "error",
  latencyMs: number | null,
  summary: string,
  rawData: unknown,
  tweets: RawTweet[] | null = null,
): void {
  logs.value.unshift({
    id: ++logIdSeq,
    label,
    timestamp: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
    latencyMs,
    status,
    summary,
    tweets,
    rawJson: JSON.stringify(rawData, null, 2),
    expanded: true,
    showRaw: false,
  });
}

function toggleLog(log: ExperimentLog) {
  log.expanded = !log.expanded;
}

function toggleRaw(log: ExperimentLog) {
  log.showRaw = !log.showRaw;
}

function copyRaw(log: ExperimentLog) {
  navigator.clipboard.writeText(log.rawJson).then(() => {
    showToast("已复制");
  });
}

function clearLogs() {
  logs.value = [];
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return iso;
  }
}

function formatNumber(n: number): string {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}w`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

// ── 1. Ping ──
const pinging = ref(false);

async function doPing() {
  pinging.value = true;
  try {
    const { data } = await api.get("/debug/x/ping");
    const d = data as {
      status: string;
      latency_ms: number | null;
      raw_response: unknown;
    };
    addLog(
      "PING",
      d.status === "ok" ? "ok" : "error",
      d.latency_ms,
      d.status === "ok"
        ? "X API 连通正常"
        : d.status === "unconfigured"
          ? "Bearer Token 未配置"
          : "连接失败",
      d.raw_response,
    );
  } catch {
    addLog("PING", "error", null, "请求异常", null);
  } finally {
    pinging.value = false;
  }
}

// ── 2. 用户查询 ──
const userHandle = ref("");
const queryingUser = ref(false);

async function doUserQuery() {
  const handle = userHandle.value.trim().replace(/^@/, "");
  if (!handle) {
    showToast("请输入用户名");
    return;
  }
  queryingUser.value = true;
  try {
    const { data } = await api.get(`/debug/x/user/${handle}`);
    const d = data as {
      user: {
        display_name: string;
        followers_count: number;
        bio: string | null;
        avatar_url: string | null;
      } | null;
      raw_response: unknown;
      latency_ms: number;
    };
    if (d.user) {
      addLog(
        "USER",
        "ok",
        d.latency_ms,
        `${d.user.display_name} · ${d.user.followers_count.toLocaleString()} 粉丝`,
        d.raw_response,
      );
    } else {
      addLog(
        "USER",
        "error",
        d.latency_ms,
        `未找到用户 @${handle}`,
        d.raw_response,
      );
    }
  } catch {
    addLog("USER", "error", null, `查询 @${handle} 失败`, null);
  } finally {
    queryingUser.value = false;
  }
}

// ── 3. 推文抓取 ──
const tweetsHandle = ref("");
const hoursBack = ref(24);
const fetchingTweets = ref(false);
const hoursOptions = [
  { label: "6h", value: 6 },
  { label: "12h", value: 12 },
  { label: "24h", value: 24 },
  { label: "48h", value: 48 },
  { label: "72h", value: 72 },
];

async function doFetchTweets() {
  const handle = tweetsHandle.value.trim().replace(/^@/, "");
  if (!handle) {
    showToast("请输入用户名");
    return;
  }
  fetchingTweets.value = true;
  try {
    const { data } = await api.post("/debug/x/tweets", {
      handle,
      hours_back: hoursBack.value,
    });
    const d = data as {
      tweets: RawTweet[];
      count: number;
      raw_response: unknown;
      latency_ms: number;
    };
    addLog(
      "TWEETS",
      d.count > 0 ? "ok" : "error",
      d.latency_ms,
      `@${handle} 近 ${hoursBack.value}h · ${d.count} 条推文`,
      d.raw_response,
      d.tweets,
    );
  } catch {
    addLog("TWEETS", "error", null, `抓取 @${handle} 推文失败`, null);
  } finally {
    fetchingTweets.value = false;
  }
}

// ── 4. 单条推文 ──
const tweetInput = ref("");
const queryingTweet = ref(false);

function extractTweetId(input: string): string {
  const trimmed = input.trim();
  const match = trimmed.match(/status\/(\d+)/);
  if (match) return match[1];
  if (/^\d+$/.test(trimmed)) return trimmed;
  return trimmed;
}

async function doTweetQuery() {
  const tweetId = extractTweetId(tweetInput.value);
  if (!tweetId) {
    showToast("请输入推文 URL 或 ID");
    return;
  }
  queryingTweet.value = true;
  try {
    const { data } = await api.get(`/debug/x/tweet/${tweetId}`);
    const d = data as {
      tweet: RawTweet | null;
      raw_response: unknown;
      latency_ms: number;
    };
    if (d.tweet) {
      addLog("TWEET", "ok", d.latency_ms, `推文 ${tweetId}`, d.raw_response, [
        d.tweet,
      ]);
    } else {
      addLog(
        "TWEET",
        "error",
        d.latency_ms,
        `推文 ${tweetId} 不存在`,
        d.raw_response,
      );
    }
  } catch {
    addLog("TWEET", "error", null, `查询推文 ${tweetId} 失败`, null);
  } finally {
    queryingTweet.value = false;
  }
}
</script>

<template>
  <div class="zx-page debug-page">
    <van-nav-bar title="X API 调试" left-arrow @click-left="router.back()" />

    <div class="debug-content">
      <!-- ── 操作面板 ── -->
      <div class="ops-panel">
        <!-- Ping -->
        <section class="ops-section">
          <div class="section-label">连通性检测</div>
          <van-button
            size="small"
            :loading="pinging"
            loading-text="检测中..."
            class="ops-btn ops-btn--ping"
            @click="doPing"
          >
            Ping X API
          </van-button>
        </section>

        <!-- 用户查询 -->
        <section class="ops-section">
          <div class="section-label">用户查询</div>
          <div class="ops-row">
            <van-field
              v-model="userHandle"
              placeholder="输入 handle（不含 @）"
              class="ops-input"
              clearable
              @keyup.enter="doUserQuery"
            />
            <van-button
              size="small"
              :loading="queryingUser"
              loading-text="查询..."
              class="ops-btn"
              @click="doUserQuery"
            >
              查询
            </van-button>
          </div>
        </section>

        <!-- 推文抓取 -->
        <section class="ops-section">
          <div class="section-label">推文抓取</div>
          <div class="ops-row">
            <van-field
              v-model="tweetsHandle"
              placeholder="输入 handle"
              class="ops-input"
              clearable
              @keyup.enter="doFetchTweets"
            />
            <div class="hours-selector">
              <button
                v-for="opt in hoursOptions"
                :key="opt.value"
                class="hours-chip"
                :class="{ active: hoursBack === opt.value }"
                @click="hoursBack = opt.value"
              >
                {{ opt.label }}
              </button>
            </div>
          </div>
          <van-button
            size="small"
            :loading="fetchingTweets"
            loading-text="抓取中..."
            class="ops-btn ops-btn--full"
            @click="doFetchTweets"
          >
            抓取推文
          </van-button>
        </section>

        <!-- 单条推文 -->
        <section class="ops-section">
          <div class="section-label">单条推文查询</div>
          <div class="ops-row">
            <van-field
              v-model="tweetInput"
              placeholder="推文 URL 或 ID"
              class="ops-input"
              clearable
              @keyup.enter="doTweetQuery"
            />
            <van-button
              size="small"
              :loading="queryingTweet"
              loading-text="查询..."
              class="ops-btn"
              @click="doTweetQuery"
            >
              查询
            </van-button>
          </div>
        </section>
      </div>

      <!-- ── 实验记录 ── -->
      <div class="log-panel">
        <div class="log-header">
          <span class="log-header-title">实验记录</span>
          <button
            v-if="logs.length > 0"
            class="log-clear-btn"
            @click="clearLogs"
          >
            清空
          </button>
        </div>

        <div v-if="logs.length === 0" class="log-empty">
          <div class="log-empty-icon">&#x2234;</div>
          <div class="log-empty-text">执行操作后，结果将在此处展示</div>
        </div>

        <TransitionGroup name="log-item" tag="div" class="log-list">
          <div
            v-for="log in logs"
            :key="log.id"
            class="log-entry"
            :class="[`log-entry--${log.status}`]"
          >
            <!-- 头部：状态 + 摘要 -->
            <div class="log-entry-header" @click="toggleLog(log)">
              <span class="log-tag" :class="[`log-tag--${log.status}`]">
                {{ log.label }}
              </span>
              <span
                class="log-status-dot"
                :class="[`log-status-dot--${log.status}`]"
              />
              <span class="log-summary">{{ log.summary }}</span>
              <span class="log-meta">
                <span v-if="log.latencyMs !== null" class="log-latency">
                  {{ log.latencyMs }}ms
                </span>
                <span class="log-time">{{ log.timestamp }}</span>
              </span>
              <span class="log-chevron" :class="{ rotated: log.expanded }">
                &#x25BE;
              </span>
            </div>

            <!-- 展开内容 -->
            <Transition name="json-expand">
              <div v-if="log.expanded" class="log-body">
                <!-- 格式化推文列表 -->
                <div v-if="log.tweets && log.tweets.length > 0" class="tweet-list">
                  <div
                    v-for="tweet in log.tweets"
                    :key="tweet.tweet_id"
                    class="tweet-card"
                  >
                    <div class="tweet-text">{{ tweet.text }}</div>
                    <div class="tweet-footer">
                      <span class="tweet-time">
                        {{ formatTime(tweet.created_at) }}
                      </span>
                      <span class="tweet-metrics">
                        <span title="点赞">&#x2661; {{ formatNumber(tweet.public_metrics.like_count ?? 0) }}</span>
                        <span title="转推">&#x21BB; {{ formatNumber(tweet.public_metrics.retweet_count ?? 0) }}</span>
                        <span title="回复">&#x2709; {{ formatNumber(tweet.public_metrics.reply_count ?? 0) }}</span>
                      </span>
                      <a
                        v-if="tweet.tweet_url"
                        :href="tweet.tweet_url"
                        target="_blank"
                        rel="noopener"
                        class="tweet-link"
                      >
                        原文 &#x2197;
                      </a>
                    </div>
                  </div>
                </div>

                <!-- 原始 JSON 开关 -->
                <div v-if="log.rawJson && log.rawJson !== 'null'" class="raw-toggle-bar">
                  <button class="raw-toggle-btn" @click.stop="toggleRaw(log)">
                    {{ log.showRaw ? "收起原始数据" : "查看原始数据" }}
                  </button>
                  <button class="raw-toggle-btn" @click.stop="copyRaw(log)">
                    复制原始数据
                  </button>
                </div>
                <div v-if="log.showRaw && log.rawJson" class="log-json-wrap">
                  <pre class="log-json">{{ log.rawJson }}</pre>
                </div>

                <!-- 无推文时直接显示 JSON -->
                <div
                  v-if="!log.tweets && log.rawJson && log.rawJson !== 'null'"
                  class="log-json-wrap"
                >
                  <pre class="log-json">{{ log.rawJson }}</pre>
                </div>
              </div>
            </Transition>
          </div>
        </TransitionGroup>
      </div>
    </div>
  </div>
</template>

<style scoped>
.debug-content {
  padding: var(--zx-space-base);
  display: flex;
  flex-direction: column;
  gap: var(--zx-space-lg);
}

/* ── 操作面板 ── */
.ops-panel {
  display: flex;
  flex-direction: column;
  gap: var(--zx-space-md);
}

.ops-section {
  background: var(--zx-bg-card);
  border-radius: var(--zx-radius-md);
  padding: var(--zx-space-md) var(--zx-space-base);
  box-shadow: var(--zx-shadow-xs);
}

.section-label {
  font-family: var(--zx-font-display);
  font-size: var(--zx-text-sm);
  color: var(--zx-text-tertiary);
  letter-spacing: 0.08em;
  margin-bottom: var(--zx-space-sm);
}

.ops-row {
  display: flex;
  gap: var(--zx-space-sm);
  align-items: center;
  flex-wrap: wrap;
}

.ops-input {
  flex: 1;
  min-width: 0;
  padding: 0;
  font-size: var(--zx-text-sm);
}

.ops-input :deep(.van-field__control) {
  font-family: var(--zx-font-mono);
  font-size: var(--zx-text-sm);
}

.ops-btn {
  flex-shrink: 0;
  background: var(--zx-primary);
  color: var(--zx-text-inverse);
  border: none;
  border-radius: var(--zx-radius-sm);
  font-size: var(--zx-text-sm);
  min-width: 72px;
}

.ops-btn--ping {
  width: 100%;
}

.ops-btn--full {
  width: 100%;
  margin-top: var(--zx-space-sm);
}

.hours-selector {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.hours-chip {
  border: 1px solid var(--zx-border);
  background: var(--zx-bg-elevated);
  color: var(--zx-text-secondary);
  border-radius: var(--zx-radius-full);
  padding: 2px 10px;
  font-size: var(--zx-text-xs);
  font-family: var(--zx-font-mono);
  cursor: pointer;
  transition: all var(--zx-duration-fast) var(--zx-easing);
}

.hours-chip.active {
  background: var(--zx-primary);
  color: var(--zx-text-inverse);
  border-color: var(--zx-primary);
}

/* ── 实验记录面板 ── */
.log-panel {
  min-height: 200px;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: var(--zx-space-md);
}

.log-header-title {
  font-family: var(--zx-font-display);
  font-size: var(--zx-text-lg);
  color: var(--zx-text-primary);
  letter-spacing: 0.04em;
}

.log-clear-btn {
  background: none;
  border: none;
  color: var(--zx-text-tertiary);
  font-size: var(--zx-text-xs);
  cursor: pointer;
  padding: 2px 8px;
  border-radius: var(--zx-radius-xs);
}

.log-clear-btn:active {
  color: var(--zx-danger);
}

.log-empty {
  text-align: center;
  padding: var(--zx-space-2xl) 0;
  color: var(--zx-text-tertiary);
}

.log-empty-icon {
  font-size: 32px;
  margin-bottom: var(--zx-space-sm);
  opacity: 0.3;
}

.log-empty-text {
  font-size: var(--zx-text-sm);
}

.log-list {
  display: flex;
  flex-direction: column;
  gap: var(--zx-space-sm);
}

.log-entry {
  background: var(--zx-bg-card);
  border-radius: var(--zx-radius-sm);
  border-left: 3px solid var(--zx-border);
  box-shadow: var(--zx-shadow-xs);
  overflow: hidden;
}

.log-entry--ok {
  border-left-color: var(--zx-success);
}

.log-entry--error {
  border-left-color: var(--zx-danger);
}

.log-entry-header {
  display: flex;
  align-items: center;
  gap: var(--zx-space-sm);
  padding: var(--zx-space-sm) var(--zx-space-md);
  cursor: pointer;
  min-height: 40px;
}

.log-tag {
  font-family: var(--zx-font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.05em;
  padding: 1px 6px;
  border-radius: var(--zx-radius-xs);
  flex-shrink: 0;
}

.log-tag--ok {
  background: var(--zx-success-bg);
  color: var(--zx-success);
}

.log-tag--error {
  background: var(--zx-danger-bg);
  color: var(--zx-danger);
}

.log-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.log-status-dot--ok {
  background: var(--zx-success);
}

.log-status-dot--error {
  background: var(--zx-danger);
}

.log-summary {
  flex: 1;
  font-size: var(--zx-text-sm);
  color: var(--zx-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.log-meta {
  display: flex;
  gap: var(--zx-space-sm);
  flex-shrink: 0;
  font-family: var(--zx-font-mono);
  font-size: var(--zx-text-xs);
  color: var(--zx-text-tertiary);
}

.log-latency {
  color: var(--zx-accent-text);
}

.log-chevron {
  font-size: 12px;
  color: var(--zx-text-tertiary);
  transition: transform var(--zx-duration-fast) var(--zx-easing);
  flex-shrink: 0;
}

.log-chevron.rotated {
  transform: rotate(180deg);
}

/* ── 展开内容 ── */
.log-body {
  border-top: 1px solid var(--zx-border-light);
}

/* ── 推文卡片列表 ── */
.tweet-list {
  padding: var(--zx-space-md);
  display: flex;
  flex-direction: column;
  gap: var(--zx-space-sm);
}

.tweet-card {
  padding: var(--zx-space-md);
  background: var(--zx-bg-elevated);
  border-radius: var(--zx-radius-sm);
  border: 1px solid var(--zx-border-light);
}

.tweet-text {
  font-size: var(--zx-text-sm);
  line-height: 1.6;
  color: var(--zx-text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}

.tweet-footer {
  display: flex;
  align-items: center;
  gap: var(--zx-space-md);
  margin-top: var(--zx-space-sm);
  padding-top: var(--zx-space-sm);
  border-top: 1px solid var(--zx-border-light);
  font-size: var(--zx-text-xs);
  color: var(--zx-text-tertiary);
}

.tweet-metrics {
  display: flex;
  gap: var(--zx-space-md);
  font-family: var(--zx-font-mono);
}

.tweet-link {
  margin-left: auto;
  color: var(--zx-info);
  text-decoration: none;
  font-size: var(--zx-text-xs);
}

.tweet-link:active {
  opacity: 0.7;
}

/* ── 原始数据开关 ── */
.raw-toggle-bar {
  padding: var(--zx-space-xs) var(--zx-space-md);
  border-top: 1px solid var(--zx-border-light);
}

.raw-toggle-btn {
  background: none;
  border: none;
  color: var(--zx-text-tertiary);
  font-size: var(--zx-text-xs);
  cursor: pointer;
  padding: 4px 0;
}

.raw-toggle-btn:active {
  color: var(--zx-primary);
}

/* ── JSON 区域 ── */
.log-json-wrap {
  background: var(--zx-bg-elevated);
  max-height: 360px;
  overflow: auto;
  -webkit-overflow-scrolling: touch;
}

.log-json {
  font-family: var(--zx-font-mono);
  font-size: 11px;
  line-height: 1.5;
  color: var(--zx-text-secondary);
  padding: var(--zx-space-md);
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}

/* ── 动画 ── */
.log-item-enter-active {
  transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

.log-item-leave-active {
  transition: all 0.2s ease-in;
}

.log-item-enter-from {
  opacity: 0;
  transform: translateY(-12px);
}

.log-item-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

.json-expand-enter-active {
  transition: all 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}

.json-expand-leave-active {
  transition: all 0.15s ease-in;
}

.json-expand-enter-from,
.json-expand-leave-to {
  opacity: 0;
}
</style>
