import api from "@/api";
import type { AddLogFn } from "@/composables/useExperimentLog";
import type { RawTweet } from "@zhixi/openapi-client";
import { showToast } from "vant";
import { ref } from "vue";

export const hoursOptions = [
  { label: "6h", value: 6 },
  { label: "12h", value: 12 },
  { label: "24h", value: 24 },
  { label: "48h", value: 48 },
  { label: "72h", value: 72 },
] as const;

function extractTweetId(input: string): string {
  const trimmed = input.trim();
  const match = trimmed.match(/status\/(\d+)/);
  if (match) return match[1];
  if (/^\d+$/.test(trimmed)) return trimmed;
  return trimmed;
}

export function useXApiDebug(addLog: AddLogFn) {
  const userHandle = ref("");
  const tweetsHandle = ref("");
  const hoursBack = ref(24);
  const tweetInput = ref("");

  const pinging = ref(false);
  const queryingUser = ref(false);
  const fetchingTweets = ref(false);
  const queryingTweet = ref(false);

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

  return {
    userHandle,
    tweetsHandle,
    hoursBack,
    tweetInput,
    pinging,
    queryingUser,
    fetchingTweets,
    queryingTweet,
    doPing,
    doUserQuery,
    doFetchTweets,
    doTweetQuery,
  };
}
