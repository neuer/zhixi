<script setup lang="ts">
import { filterVisibleItems } from "@/utils/digest";
import { formatDate, safeHref } from "@/utils/format";
import type {
  DigestBriefResponse,
  DigestItemResponse,
} from "@zhixi/openapi-client";
import { computed } from "vue";

const props = defineProps<{
  digest: DigestBriefResponse;
  items: DigestItemResponse[];
}>();

const visibleItems = computed(() => filterVisibleItems(props.items));

/** 解析 perspectives JSON（带元素类型守卫）。 */
function parsePerspectives(raw: string | null): string[] {
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed))
      return parsed.filter((x): x is string => typeof x === "string");
  } catch {
    /* 忽略解析失败 */
  }
  return [];
}

/** 解析 source_tweets JSON（带元素类型守卫）。 */
function parseSourceTweets(
  raw: string | null,
): { author: string; url: string }[] {
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed))
      return parsed.filter(
        (item): item is { author: string; url: string } =>
          typeof item === "object" &&
          item !== null &&
          typeof (item as Record<string, unknown>).author === "string" &&
          typeof (item as Record<string, unknown>).url === "string",
      );
  } catch {
    /* 忽略解析失败 */
  }
  return [];
}
</script>

<template>
  <div class="article-preview">
    <!-- 头部 -->
    <div class="preview-header">
      <h1 class="preview-title">智曦 AI 日报</h1>
      <p class="preview-date">{{ formatDate(digest.digest_date) }}</p>
    </div>

    <!-- 导读摘要 -->
    <div v-if="digest.summary" class="preview-summary">
      <div class="summary-label">今日导读</div>
      <p class="summary-text">{{ digest.summary }}</p>
    </div>

    <!-- 条目列表 -->
    <div class="preview-items">
      <div
        v-for="(item, idx) in visibleItems"
        :key="item.id"
        class="preview-card"
      >
        <!-- 序号 + 热度 -->
        <div class="card-header">
          <span class="card-index">{{ idx + 1 }}</span>
          <span class="card-heat">🔥 {{ Math.round(item.snapshot_heat_score) }}</span>
          <span
            v-if="item.is_pinned"
            class="card-pinned"
          >置顶</span>
        </div>

        <!-- 标题 -->
        <h3 class="card-title">{{ item.snapshot_title }}</h3>

        <!-- 聚合话题：摘要 + 观点 + 来源 -->
        <template v-if="item.item_type === 'topic' && item.snapshot_topic_type === 'aggregated'">
          <p v-if="item.snapshot_summary" class="card-summary">
            {{ item.snapshot_summary }}
          </p>
          <div v-if="parsePerspectives(item.snapshot_perspectives).length" class="card-perspectives">
            <div class="perspectives-label">各方观点</div>
            <ul>
              <li v-for="(p, pi) in parsePerspectives(item.snapshot_perspectives)" :key="pi">
                {{ p }}
              </li>
            </ul>
          </div>
          <div v-if="parseSourceTweets(item.snapshot_source_tweets).length" class="card-sources">
            <span class="sources-label">来源：</span>
            <a
              v-for="(src, si) in parseSourceTweets(item.snapshot_source_tweets)"
              :key="si"
              :href="safeHref(src.url)"
              target="_blank"
              rel="noopener noreferrer"
              class="source-link"
            >@{{ src.author }}</a>
          </div>
        </template>

        <!-- Thread / 单条推文：翻译 + 点评 -->
        <template v-else>
          <p v-if="item.snapshot_translation" class="card-translation">
            {{ item.snapshot_translation }}
          </p>
          <div v-if="item.snapshot_author_handle" class="card-author">
            <a
              v-if="item.snapshot_tweet_url"
              :href="safeHref(item.snapshot_tweet_url)"
              target="_blank"
              rel="noopener noreferrer"
              class="author-link"
            >@{{ item.snapshot_author_handle }}</a>
            <span v-else>@{{ item.snapshot_author_handle }}</span>
          </div>
        </template>

        <!-- 点评 -->
        <div v-if="item.snapshot_comment" class="card-comment">
          <span class="comment-label">智曦点评：</span>{{ item.snapshot_comment }}
        </div>
      </div>
    </div>

    <!-- 底部 -->
    <div class="preview-footer">
      <p>智曦 — 每天一束 AI 之光</p>
    </div>
  </div>
</template>

<style scoped>
.article-preview {
  max-width: 680px;
  margin: 0 auto;
  padding: 0 16px 32px;
  background: #fff;
  min-height: 100vh;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  color: #333;
}

.preview-header {
  text-align: center;
  padding: 32px 0 16px;
  border-bottom: 1px solid #eee;
}

.preview-title {
  font-size: 24px;
  font-weight: 600;
  margin: 0 0 4px;
  color: #1a1a1a;
}

.preview-date {
  font-size: 14px;
  color: #999;
  margin: 0;
}

.preview-summary {
  margin: 20px 0;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 12px;
  border-left: 3px solid #4a90d9;
}

.summary-label {
  font-size: 12px;
  color: #4a90d9;
  font-weight: 600;
  margin-bottom: 6px;
}

.summary-text {
  font-size: 15px;
  line-height: 1.6;
  color: #555;
  margin: 0;
}

.preview-items {
  margin-top: 16px;
}

.preview-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  border: 1px solid #f0f0f0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.card-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: #4a90d9;
  color: #fff;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.card-heat {
  font-size: 12px;
  color: #999;
}

.card-pinned {
  font-size: 11px;
  color: #ff976a;
  background: #fff7f0;
  padding: 2px 6px;
  border-radius: 4px;
}

.card-title {
  font-size: 17px;
  font-weight: 600;
  line-height: 1.4;
  margin: 0 0 8px;
  color: #1a1a1a;
}

.card-summary,
.card-translation {
  font-size: 15px;
  line-height: 1.6;
  color: #555;
  margin: 0 0 8px;
}

.card-author {
  font-size: 13px;
  color: #999;
  margin-bottom: 8px;
}

.author-link {
  color: #4a90d9;
  text-decoration: none;
}

.card-comment {
  font-size: 14px;
  line-height: 1.5;
  color: #666;
  background: #f8f9fa;
  padding: 10px 12px;
  border-radius: 8px;
  margin-top: 8px;
}

.comment-label {
  color: #4a90d9;
  font-weight: 500;
}

.card-perspectives {
  margin: 8px 0;
}

.perspectives-label {
  font-size: 13px;
  color: #4a90d9;
  font-weight: 500;
  margin-bottom: 4px;
}

.card-perspectives ul {
  margin: 0;
  padding-left: 20px;
}

.card-perspectives li {
  font-size: 14px;
  line-height: 1.6;
  color: #555;
  margin-bottom: 4px;
}

.card-sources {
  font-size: 13px;
  color: #999;
  margin-top: 8px;
}

.sources-label {
  color: #999;
}

.source-link {
  color: #4a90d9;
  text-decoration: none;
  margin-right: 8px;
}

.preview-footer {
  text-align: center;
  padding: 24px 0;
  margin-top: 16px;
  border-top: 1px solid #eee;
  color: #bbb;
  font-size: 13px;
}
</style>
