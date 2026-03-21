"""process_service — AI 加工编排层（US-019 + US-020 + US-021）。

编排全局分析（含分批+去重）、逐条/逐话题加工、热度计算。
"""

import asyncio
import json
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.claude_client import ClaudeAPIError, ClaudeClient
from app.config import ensure_utc
from app.models.account import TwitterAccount
from app.models.api_cost_log import ApiCostLog
from app.models.topic import Topic
from app.models.tweet import Tweet
from app.processor.analyzer import run_global_analysis
from app.processor.analyzer_prompts import serialize_tweets_for_analysis
from app.processor.batch_merger import merge_analysis_results, run_dedup_analysis
from app.processor.batch_strategy import split_into_batches
from app.processor.heat_calculator import (
    calculate_base_score,
    calculate_heat_score,
    calculate_hours_since_post,
    get_reference_time,
    normalize_scores,
)
from app.processor.json_validator import JsonValidationError
from app.processor.translator import (
    process_aggregated_topic,
    process_single_tweet,
    process_thread,
)
from app.schemas.client_types import ClaudeResponse
from app.schemas.processor_types import AnalysisResult, ProcessResult

logger = logging.getLogger(__name__)

# 逐条加工最大重试次数
_ITEM_MAX_RETRIES = 2
# 全局分析最大重试次数
_ANALYSIS_MAX_RETRIES = 1


class ProcessService:
    """AI 加工编排服务。"""

    def __init__(self, db: AsyncSession, claude_client: ClaudeClient) -> None:
        self._db = db
        self._claude = claude_client

    async def run_daily_process(self, digest_date: date) -> ProcessResult:
        """执行当日全量 AI 加工。

        流程：全局分析 → 应用结果 → 逐条加工 → 热度计算。
        """
        # 1. 查询当日未处理推文
        tweets = await self._get_unprocessed_tweets(digest_date)
        if not tweets:
            logger.info("当日无待处理推文 (%s)", digest_date)
            return ProcessResult(
                processed_count=0,
                filtered_count=0,
                topic_count=0,
                failed_count=0,
            )

        # 2. 构建账号映射
        accounts_map = await self._get_accounts_map(tweets)

        # ── US-019 全局分析 ──
        analysis = await self._run_analysis_with_retry(tweets, accounts_map, digest_date)

        # 3. 应用分析结果
        tweet_map = {t.tweet_id: t for t in tweets}
        filtered_count = self._apply_filtering(analysis, tweet_map)
        topics_created, merged_texts = await self._create_topics(
            analysis,
            tweet_map,
            digest_date,
        )
        self._apply_importance_scores(analysis, tweet_map)

        await self._db.flush()

        # ── US-021 逐条/逐话题加工 ──
        processed_count, failed_count = await self._process_all_items(
            analysis,
            tweet_map,
            topics_created,
            merged_texts,
            accounts_map,
            digest_date,
        )

        await self._db.flush()

        # ── 热度计算 ──
        self._calculate_all_heat_scores(tweets, topics_created, accounts_map, digest_date)

        await self._db.flush()

        return ProcessResult(
            processed_count=processed_count,
            filtered_count=filtered_count,
            topic_count=len(topics_created),
            failed_count=failed_count,
        )

    async def process_single_tweet_by_id(self, tweet_id: int) -> None:
        """单条推文加工（供手动补录 US-016 调用）。"""
        stmt = select(Tweet).where(Tweet.id == tweet_id)
        tweet = (await self._db.execute(stmt)).scalar_one_or_none()
        if tweet is None:
            msg = f"推文不存在: id={tweet_id}"
            raise ValueError(msg)

        accounts_map = await self._get_accounts_map([tweet])
        account = accounts_map.get(tweet.account_id)

        tweet_data = _build_single_tweet_data(tweet, account)
        result, response = await process_single_tweet(self._claude, tweet_data)

        tweet.title = str(result["title"])
        tweet.translated_text = str(result["translation"])
        tweet.ai_comment = str(result["comment"])
        tweet.is_processed = True

        self._record_cost(response, "single_process", tweet.digest_date)
        await self._db.flush()

    # ──────────────────────────────────────────────────
    # 内部方法
    # ──────────────────────────────────────────────────

    async def _get_unprocessed_tweets(self, digest_date: date) -> list[Tweet]:
        """查询当日未处理推文。"""
        stmt = (
            select(Tweet)
            .where(Tweet.digest_date == digest_date, Tweet.is_processed.is_(False))
            .order_by(Tweet.tweet_time.desc())
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def _get_accounts_map(self, tweets: list[Tweet]) -> dict[int, TwitterAccount]:
        """构建 account_id → TwitterAccount 映射。"""
        account_ids = {t.account_id for t in tweets}
        if not account_ids:
            return {}
        stmt = select(TwitterAccount).where(TwitterAccount.id.in_(account_ids))
        accounts = (await self._db.execute(stmt)).scalars().all()
        return {a.id: a for a in accounts}

    async def _run_analysis_with_retry(
        self,
        tweets: list[Tweet],
        accounts_map: dict[int, TwitterAccount],
        digest_date: date,
    ) -> AnalysisResult:
        """执行全局分析（含分批 + 去重，US-020）。

        流程：
        1. split_into_batches 检查是否需要分批
        2. 单批：走原有逻辑
        3. 多批：逐批分析 → 合并 → AI 去重
        """
        batches = split_into_batches(tweets, accounts_map)

        if len(batches) <= 1:
            # 单批：原有逻辑
            serialized = serialize_tweets_for_analysis(tweets, accounts_map)
            tweets_json = json.dumps(serialized, ensure_ascii=False)
            return await self._run_single_analysis(tweets_json, digest_date)

        # 多批处理
        logger.info("推文 token 超限，分 %d 批处理", len(batches))
        batch_results: list[AnalysisResult] = []

        for i, batch in enumerate(batches):
            logger.info(
                "执行第 %d/%d 批全局分析（%d 条推文）",
                i + 1,
                len(batches),
                len(batch),
            )
            serialized = serialize_tweets_for_analysis(batch, accounts_map)
            tweets_json = json.dumps(serialized, ensure_ascii=False)
            result = await self._run_single_analysis(tweets_json, digest_date)
            batch_results.append(result)

        # 合并 + 去重
        merged_data = merge_analysis_results(batch_results)
        deduped = await self._run_dedup_with_retry(merged_data, digest_date)
        logger.info(
            "去重完成: filtered=%d, topics=%d",
            len(deduped.filtered_ids),
            len(deduped.topics),
        )
        return deduped

    async def _run_single_analysis(
        self,
        tweets_json: str,
        digest_date: date,
    ) -> AnalysisResult:
        """单批全局分析（含重试），从原 _run_analysis_with_retry 提取。"""
        last_error: Exception | None = None
        for attempt in range(_ANALYSIS_MAX_RETRIES + 1):
            try:
                analysis, response = await run_global_analysis(self._claude, tweets_json)
                self._record_cost(response, "global_analysis", digest_date)
                logger.info(
                    "全局分析完成: filtered=%d, topics=%d",
                    len(analysis.filtered_ids),
                    len(analysis.topics),
                )
                return analysis
            except (ClaudeAPIError, JsonValidationError) as e:
                last_error = e
                logger.warning("全局分析第 %d 次尝试失败: %s", attempt + 1, e)

        logger.error("全局分析连续失败，中止 pipeline")
        raise last_error  # type: ignore[misc]

    async def _run_dedup_with_retry(
        self,
        merged_data: dict[str, object],
        digest_date: date,
    ) -> AnalysisResult:
        """去重 AI 调用（含重试）。"""
        last_error: Exception | None = None
        for attempt in range(_ANALYSIS_MAX_RETRIES + 1):
            try:
                deduped, response = await run_dedup_analysis(self._claude, merged_data)
                self._record_cost(response, "dedup_analysis", digest_date)
                return deduped
            except (ClaudeAPIError, JsonValidationError) as e:
                last_error = e
                logger.warning("去重分析第 %d 次尝试失败: %s", attempt + 1, e)

        logger.error("去重分析连续失败，中止 pipeline")
        raise last_error  # type: ignore[misc]

    def _apply_filtering(
        self,
        analysis: AnalysisResult,
        tweet_map: dict[str, Tweet],
    ) -> int:
        """标记被过滤推文 is_ai_relevant=false。"""
        count = 0
        for fid in analysis.filtered_ids:
            tweet = tweet_map.get(fid)
            if tweet:
                tweet.is_ai_relevant = False
                count += 1
            else:
                logger.warning("过滤 ID %s 在推文中未找到，跳过", fid)
        return count

    async def _create_topics(
        self,
        analysis: AnalysisResult,
        tweet_map: dict[str, Tweet],
        digest_date: date,
    ) -> tuple[list[Topic], dict[int, str]]:
        """根据分析结果创建 topics，返回 (topics, merged_texts)。"""
        topics: list[Topic] = []
        merged_texts: dict[int, str] = {}

        for topic_result in analysis.topics:
            if topic_result.type == "single":
                continue

            topic = Topic(
                digest_date=digest_date,
                type=topic_result.type,
                topic_label=topic_result.topic_label,
                ai_importance_score=topic_result.ai_importance_score,
                tweet_count=len(topic_result.tweet_ids),
            )
            self._db.add(topic)
            await self._db.flush()  # 获取 topic.id

            # 关联推文
            for tid in topic_result.tweet_ids:
                tweet = tweet_map.get(tid)
                if tweet:
                    tweet.topic_id = topic.id

            # Thread: 缓存 merged_text
            if topic_result.type == "thread" and topic_result.merged_text:
                merged_texts[topic.id] = topic_result.merged_text

            topics.append(topic)

        return topics, merged_texts

    def _apply_importance_scores(
        self,
        analysis: AnalysisResult,
        tweet_map: dict[str, Tweet],
    ) -> None:
        """将 ai_importance_score 写入所有非 filtered 推文。"""
        for topic_result in analysis.topics:
            score = topic_result.ai_importance_score
            for tid in topic_result.tweet_ids:
                tweet = tweet_map.get(tid)
                if tweet and tweet.is_ai_relevant:
                    tweet.ai_importance_score = score

    async def _process_all_items(
        self,
        analysis: AnalysisResult,
        tweet_map: dict[str, Tweet],
        topics: list[Topic],
        merged_texts: dict[int, str],
        accounts_map: dict[int, TwitterAccount],
        digest_date: date,
    ) -> tuple[int, int]:
        """逐条/逐话题加工，返回 (processed_count, failed_count)。"""
        processed = 0
        failed = 0

        # 收集 single 推文
        single_tweet_ids = self._get_single_tweet_ids(analysis, tweet_map)

        # 按 topic 结果顺序 + single 推文顺序加工
        item_index = 0

        # 加工 single 推文
        for tid in single_tweet_ids:
            tweet = tweet_map.get(tid)
            if not tweet:
                continue

            if item_index > 0:
                await asyncio.sleep(1.0)
            item_index += 1

            account = accounts_map.get(tweet.account_id)
            success = await self._process_single_with_retry(
                tweet,
                account,
                digest_date,
            )
            if success:
                processed += 1
            else:
                failed += 1

        # 加工 topics（aggregated + thread）
        for topic in topics:
            if item_index > 0:
                await asyncio.sleep(1.0)
            item_index += 1

            member_tweets = [t for t in tweet_map.values() if t.topic_id == topic.id]

            if topic.type == "aggregated":
                success = await self._process_aggregated_with_retry(
                    topic,
                    member_tweets,
                    accounts_map,
                    digest_date,
                )
            else:  # thread
                merged_text = merged_texts.get(topic.id, "")
                success = await self._process_thread_with_retry(
                    topic,
                    member_tweets,
                    accounts_map,
                    merged_text,
                    digest_date,
                )

            if success:
                processed += 1
                # 标记成员推文为已处理
                for t in member_tweets:
                    t.is_processed = True
            else:
                failed += 1

        return processed, failed

    def _get_single_tweet_ids(
        self,
        analysis: AnalysisResult,
        tweet_map: dict[str, Tweet],
    ) -> list[str]:
        """从分析结果中提取 single 推文 ID 列表。

        如果 AI 返回空 topics，所有非 filtered 推文 fallback 为 single。
        """
        # 收集已被 topic 覆盖的 tweet_ids
        covered_ids: set[str] = set()
        single_from_analysis: list[str] = []

        for topic_result in analysis.topics:
            if topic_result.type == "single":
                single_from_analysis.extend(topic_result.tweet_ids)
            covered_ids.update(topic_result.tweet_ids)

        # filtered 的也排除
        covered_ids.update(analysis.filtered_ids)

        # fallback: 未被覆盖的推文也作为 single
        for tid, tweet in tweet_map.items():
            if tid not in covered_ids and tweet.is_ai_relevant:
                single_from_analysis.append(tid)

        return single_from_analysis

    async def _process_single_with_retry(
        self,
        tweet: Tweet,
        account: TwitterAccount | None,
        digest_date: date,
    ) -> bool:
        """单条推文加工（含重试）。"""
        tweet_data = _build_single_tweet_data(tweet, account)

        for attempt in range(_ITEM_MAX_RETRIES + 1):
            try:
                result, response = await process_single_tweet(self._claude, tweet_data)
                tweet.title = str(result["title"])
                tweet.translated_text = str(result["translation"])
                tweet.ai_comment = str(result["comment"])
                tweet.is_processed = True
                self._record_cost(response, "single_process", digest_date)
                return True
            except (ClaudeAPIError, JsonValidationError) as e:
                logger.warning(
                    "单条加工 %s 第 %d 次失败: %s",
                    tweet.tweet_id,
                    attempt + 1,
                    e,
                )

        logger.error("单条加工 %s 连续失败，跳过", tweet.tweet_id)
        self._record_cost_failure("single_process", digest_date)
        return False

    async def _process_aggregated_with_retry(
        self,
        topic: Topic,
        member_tweets: list[Tweet],
        accounts_map: dict[int, TwitterAccount],
        digest_date: date,
    ) -> bool:
        """聚合话题加工（含重试）。"""
        tweets_data = _build_aggregated_tweets_data(member_tweets, accounts_map)
        tweets_json = json.dumps(tweets_data, ensure_ascii=False)

        for attempt in range(_ITEM_MAX_RETRIES + 1):
            try:
                result, response = await process_aggregated_topic(
                    self._claude,
                    tweets_json,
                )
                topic.title = str(result["title"])
                topic.summary = str(result["summary"])
                topic.perspectives = json.dumps(
                    result["perspectives"],
                    ensure_ascii=False,
                )
                topic.ai_comment = str(result["comment"])
                self._record_cost(response, "topic_process", digest_date)
                return True
            except (ClaudeAPIError, JsonValidationError) as e:
                logger.warning(
                    "聚合加工 topic %d 第 %d 次失败: %s",
                    topic.id,
                    attempt + 1,
                    e,
                )

        logger.error("聚合加工 topic %d 连续失败，跳过", topic.id)
        self._record_cost_failure("topic_process", digest_date)
        return False

    async def _process_thread_with_retry(
        self,
        topic: Topic,
        member_tweets: list[Tweet],
        accounts_map: dict[int, TwitterAccount],
        merged_text: str,
        digest_date: date,
    ) -> bool:
        """Thread 加工（含重试）。"""
        thread_data = _build_thread_data(topic, member_tweets, accounts_map, merged_text)

        for attempt in range(_ITEM_MAX_RETRIES + 1):
            try:
                result, response = await process_thread(self._claude, thread_data)
                topic.title = str(result["title"])
                topic.summary = str(result["translation"])  # translation → summary
                topic.ai_comment = str(result["comment"])
                self._record_cost(response, "thread_process", digest_date)
                return True
            except (ClaudeAPIError, JsonValidationError) as e:
                logger.warning(
                    "Thread 加工 topic %d 第 %d 次失败: %s",
                    topic.id,
                    attempt + 1,
                    e,
                )

        logger.error("Thread 加工 topic %d 连续失败，跳过", topic.id)
        self._record_cost_failure("thread_process", digest_date)
        return False

    def _calculate_all_heat_scores(
        self,
        tweets: list[Tweet],
        topics: list[Topic],
        accounts_map: dict[int, TwitterAccount],
        digest_date: date,
    ) -> None:
        """计算所有推文和话题的热度分。"""
        ref_time = get_reference_time(digest_date)

        # 计算推文 base_score
        relevant_tweets = [t for t in tweets if t.is_ai_relevant]
        for tweet in relevant_tweets:
            account = accounts_map.get(tweet.account_id)
            weight = account.weight if account else 1.0
            tweet_time = ensure_utc(tweet.tweet_time)
            hours = calculate_hours_since_post(tweet_time, ref_time)
            tweet.base_heat_score = calculate_base_score(
                tweet.likes,
                tweet.retweets,
                tweet.replies,
                weight,
                hours,
            )

        # 计算 topic raw_base_score = AVG(成员 base_score)
        topic_raw_scores: dict[int, float] = {}
        for topic in topics:
            member_scores = [t.base_heat_score for t in relevant_tweets if t.topic_id == topic.id]
            if member_scores:
                topic_raw_scores[topic.id] = sum(member_scores) / len(member_scores)
            else:
                topic_raw_scores[topic.id] = 0.0

        # 收集所有需要归一化的分数：单条 base_score + topic raw_base_score
        all_raw_scores: list[float] = []
        single_tweets = [t for t in relevant_tweets if t.topic_id is None]

        for t in single_tweets:
            all_raw_scores.append(t.base_heat_score)
        for topic in topics:
            all_raw_scores.append(topic_raw_scores.get(topic.id, 0.0))

        # 归一化
        normalized = normalize_scores(all_raw_scores)

        # 分配归一化后的分数
        idx = 0
        for t in single_tweets:
            norm_score = normalized[idx] if idx < len(normalized) else 50.0
            t.heat_score = calculate_heat_score(norm_score, t.ai_importance_score)
            idx += 1

        for topic in topics:
            norm_score = normalized[idx] if idx < len(normalized) else 50.0
            topic.heat_score = calculate_heat_score(norm_score, topic.ai_importance_score)
            idx += 1

    def _record_cost(
        self,
        response: ClaudeResponse,
        call_type: str,
        digest_date: date | None,
    ) -> None:
        """记录 API 调用成本。"""
        cost = ApiCostLog(
            call_date=digest_date or date.today(),
            service="claude",
            call_type=call_type,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            estimated_cost=response.estimated_cost,
            success=True,
            duration_ms=response.duration_ms,
        )
        self._db.add(cost)

    def _record_cost_failure(self, call_type: str, digest_date: date | None) -> None:
        """记录失败的 API 调用。"""
        cost = ApiCostLog(
            call_date=digest_date or date.today(),
            service="claude",
            call_type=call_type,
            success=False,
        )
        self._db.add(cost)


# ──────────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────────


def _build_single_tweet_data(
    tweet: Tweet,
    account: TwitterAccount | None,
) -> dict[str, object]:
    """构建单条推文加工输入。"""
    return {
        "author_name": account.display_name if account else "",
        "author_handle": account.twitter_handle if account else "",
        "author_bio": (account.bio or "") if account else "",
        "tweet_time": tweet.tweet_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "likes": tweet.likes,
        "retweets": tweet.retweets,
        "replies": tweet.replies,
        "original_text": tweet.original_text,
    }


def _build_aggregated_tweets_data(
    tweets: list[Tweet],
    accounts_map: dict[int, TwitterAccount],
) -> list[dict[str, object]]:
    """构建聚合话题加工输入（R.1.4 格式）。"""
    result: list[dict[str, object]] = []
    for tweet in tweets:
        account = accounts_map.get(tweet.account_id)
        result.append(
            {
                "author": account.display_name if account else "",
                "handle": account.twitter_handle if account else "",
                "bio": (account.bio or "") if account else "",
                "text": tweet.original_text,
                "likes": tweet.likes,
                "retweets": tweet.retweets,
                "replies": tweet.replies,
                "time": tweet.tweet_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "url": tweet.tweet_url or "",
            }
        )
    return result


def _build_thread_data(
    _topic: Topic,
    member_tweets: list[Tweet],
    accounts_map: dict[int, TwitterAccount],
    merged_text: str,
) -> dict[str, object]:
    """构建 Thread 加工输入（R.1.5 格式）。"""
    sorted_tweets = sorted(member_tweets, key=lambda t: t.tweet_time)
    first_tweet = sorted_tweets[0] if sorted_tweets else member_tweets[0]
    last_tweet = sorted_tweets[-1] if sorted_tweets else member_tweets[-1]
    account = accounts_map.get(first_tweet.account_id)

    return {
        "author_name": account.display_name if account else "",
        "author_handle": account.twitter_handle if account else "",
        "author_bio": (account.bio or "") if account else "",
        "thread_start_time": first_tweet.tweet_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "thread_end_time": last_tweet.tweet_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tweet_count": len(member_tweets),
        "total_likes": sum(t.likes for t in member_tweets),
        "total_retweets": sum(t.retweets for t in member_tweets),
        "total_replies": sum(t.replies for t in member_tweets),
        "merged_text": merged_text,
    }
