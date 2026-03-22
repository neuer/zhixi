<script setup lang="ts">
import type { PerspectiveItem } from "@/utils/digest";
import { filterVisibleItems, parsePerspectives } from "@/utils/digest";
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

/** 解析 source_tweets JSON（带元素类型守卫）。字段名与后端 _build_source_tweets_json 一致：handle, tweet_url。 */
function parseSourceTweets(
  raw: string | null,
): { handle: string; tweet_url: string }[] {
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed))
      return parsed.filter(
        (item): item is { handle: string; tweet_url: string } =>
          typeof item === "object" &&
          item !== null &&
          typeof (item as Record<string, unknown>).handle === "string" &&
          typeof (item as Record<string, unknown>).tweet_url === "string",
      );
  } catch (e: unknown) {
    console.warn("[ArticlePreview] JSON 解析失败:", raw, e);
  }
  return [];
}

/** 预解析条目，避免模板中重复调用 JSON.parse。 */
interface ParsedItem {
  item: DigestItemResponse;
  perspectives: PerspectiveItem[];
  sourceTweets: { handle: string; tweet_url: string }[];
}

const parsedItems = computed<ParsedItem[]>(() =>
  visibleItems.value.map((item) => ({
    item,
    perspectives: parsePerspectives(item.snapshot_perspectives),
    sourceTweets: parseSourceTweets(item.snapshot_source_tweets),
  })),
);
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
        v-for="(parsed, idx) in parsedItems"
        :key="parsed.item.id"
        class="preview-card"
      >
        <!-- 序号 + 热度 -->
        <div class="card-header">
          <span class="card-index">{{ idx + 1 }}</span>
          <span class="card-heat">{{ Math.round(parsed.item.snapshot_heat_score) }}</span>
          <span
            v-if="parsed.item.is_pinned"
            class="card-pinned"
          >置顶</span>
        </div>

        <!-- 标题 -->
        <h3 class="card-title">{{ parsed.item.snapshot_title }}</h3>

        <!-- 聚合话题：摘要 + 观点 + 来源 -->
        <template v-if="parsed.item.item_type === 'topic' && parsed.item.snapshot_topic_type === 'aggregated'">
          <p v-if="parsed.item.snapshot_summary" class="card-summary">
            {{ parsed.item.snapshot_summary }}
          </p>
          <div v-if="parsed.perspectives.length" class="card-perspectives">
            <div class="perspectives-label">各方观点</div>
            <ul>
              <li v-for="(p, pi) in parsed.perspectives" :key="pi">
                <template v-if="p.author || p.handle">
                  <strong>{{ p.author }}</strong><span v-if="p.handle">（@{{ p.handle }}）</span>：
                </template>
                {{ p.viewpoint }}
              </li>
            </ul>
          </div>
          <div v-if="parsed.sourceTweets.length" class="card-sources">
            <span class="sources-label">来源：</span>
            <a
              v-for="(src, si) in parsed.sourceTweets"
              :key="si"
              :href="safeHref(src.tweet_url)"
              target="_blank"
              rel="noopener noreferrer"
              class="source-link"
            >@{{ src.handle }}</a>
          </div>
        </template>

        <!-- Thread / 单条推文：翻译 + 点评 -->
        <template v-else>
          <p v-if="parsed.item.snapshot_translation" class="card-translation">
            {{ parsed.item.snapshot_translation }}
          </p>
          <div v-if="parsed.item.snapshot_author_handle" class="card-author">
            <a
              v-if="parsed.item.snapshot_tweet_url"
              :href="safeHref(parsed.item.snapshot_tweet_url)"
              target="_blank"
              rel="noopener noreferrer"
              class="author-link"
            >@{{ parsed.item.snapshot_author_handle }}</a>
            <span v-else>@{{ parsed.item.snapshot_author_handle }}</span>
          </div>
        </template>

        <!-- 点评 -->
        <div v-if="parsed.item.snapshot_comment" class="card-comment">
          <span class="comment-label">智曦点评：</span>{{ parsed.item.snapshot_comment }}
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
  padding: 0 var(--zx-space-base) var(--zx-space-2xl);
  background: var(--zx-bg-card);
  min-height: 100vh;
  font-family: var(--zx-font-body);
  color: var(--zx-text-primary);
}

.preview-header {
  text-align: center;
  padding: var(--zx-space-2xl) 0 var(--zx-space-base);
  border-bottom: 1px solid var(--zx-border-light);
}

.preview-title {
  font-family: var(--zx-font-display);
  font-size: var(--zx-text-2xl);
  font-weight: 700;
  margin: 0 0 var(--zx-space-xs);
  color: var(--zx-primary);
}

.preview-date {
  font-size: var(--zx-text-sm);
  color: var(--zx-text-tertiary);
  margin: 0;
}

.preview-summary {
  margin: var(--zx-space-lg) 0;
  padding: var(--zx-space-base);
  background: var(--zx-primary-bg);
  border-radius: var(--zx-radius-md);
  border-left: 3px solid var(--zx-primary);
}

.summary-label {
  font-size: var(--zx-text-xs);
  color: var(--zx-primary);
  font-weight: 600;
  margin-bottom: var(--zx-space-sm);
  letter-spacing: 0.05em;
}

.summary-text {
  font-size: var(--zx-text-base);
  line-height: 1.7;
  color: var(--zx-text-secondary);
  margin: 0;
}

.preview-items {
  margin-top: var(--zx-space-base);
}

.preview-card {
  background: var(--zx-bg-card);
  border-radius: var(--zx-radius-md);
  padding: var(--zx-space-base);
  margin-bottom: var(--zx-space-md);
  border: 1px solid var(--zx-border-light);
  box-shadow: var(--zx-shadow-xs);
}

.card-header {
  display: flex;
  align-items: center;
  gap: var(--zx-space-sm);
  margin-bottom: var(--zx-space-sm);
}

.card-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: var(--zx-accent);
  color: var(--zx-text-inverse);
  border-radius: var(--zx-radius-sm);
  font-size: var(--zx-text-xs);
  font-weight: 700;
}

.card-heat {
  font-size: var(--zx-text-xs);
  color: var(--zx-text-tertiary);
}

.card-heat::before {
  content: "热度 ";
}

.card-pinned {
  font-size: var(--zx-text-xs);
  color: var(--zx-accent);
  background: var(--zx-accent-bg);
  padding: 2px 6px;
  border-radius: var(--zx-radius-xs);
  font-weight: 500;
}

.card-title {
  font-family: var(--zx-font-display);
  font-size: var(--zx-text-lg);
  font-weight: 600;
  line-height: 1.4;
  margin: 0 0 var(--zx-space-sm);
  color: var(--zx-text-primary);
}

.card-summary,
.card-translation {
  font-size: var(--zx-text-base);
  line-height: 1.7;
  color: var(--zx-text-secondary);
  margin: 0 0 var(--zx-space-sm);
}

.card-author {
  font-size: var(--zx-text-sm);
  color: var(--zx-text-tertiary);
  margin-bottom: var(--zx-space-sm);
}

.author-link {
  color: var(--zx-primary-lighter);
  text-decoration: none;
}

.card-comment {
  font-size: var(--zx-text-sm);
  line-height: 1.6;
  color: var(--zx-text-secondary);
  background: var(--zx-bg-elevated);
  padding: var(--zx-space-md);
  border-radius: var(--zx-radius-sm);
  margin-top: var(--zx-space-sm);
}

.comment-label {
  color: var(--zx-accent);
  font-weight: 600;
}

.card-perspectives {
  margin: var(--zx-space-sm) 0;
  padding: var(--zx-space-md);
  background: var(--zx-bg-elevated);
  border-radius: var(--zx-radius-sm);
  border-left: 2px solid var(--zx-primary-lighter);
}

.perspectives-label {
  font-size: var(--zx-text-sm);
  color: var(--zx-primary);
  font-weight: 600;
  margin-bottom: var(--zx-space-xs);
}

.card-perspectives ul {
  margin: 0;
  padding-left: var(--zx-space-lg);
}

.card-perspectives li {
  font-size: var(--zx-text-sm);
  line-height: 1.7;
  color: var(--zx-text-secondary);
  margin-bottom: var(--zx-space-xs);
}

.card-sources {
  font-size: var(--zx-text-sm);
  color: var(--zx-text-tertiary);
  margin-top: var(--zx-space-sm);
}

.source-link {
  color: var(--zx-primary-lighter);
  text-decoration: none;
  margin-right: var(--zx-space-sm);
}

.preview-footer {
  text-align: center;
  padding: var(--zx-space-xl) 0;
  margin-top: var(--zx-space-base);
  border-top: 1px solid var(--zx-border-light);
  color: var(--zx-text-disabled);
  font-size: var(--zx-text-sm);
  font-family: var(--zx-font-display);
  letter-spacing: 0.1em;
}
</style>
