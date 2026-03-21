"""
种子数据脚本 — 生成测试数据用于前端页面效果检查。
用法: python scripts/seed_test_data.py
"""

import json
import sqlite3
from datetime import UTC, datetime, timedelta

DB_PATH = "data/zhixi.db"
NOW = datetime.now(UTC)
TODAY = NOW.strftime("%Y-%m-%d")
YESTERDAY = (NOW - timedelta(days=1)).strftime("%Y-%m-%d")


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # ── 清理旧的测试数据 ──
    for table in [
        "digest_items",
        "daily_digest",
        "tweets",
        "topics",
        "twitter_accounts",
        "api_cost_log",
        "job_runs",
        "fetch_log",
    ]:
        cur.execute(f"DELETE FROM {table}")  # noqa: S608
    print("已清理旧数据")

    # ══════════════════════════════════════════════
    # 1. 大V 账号（8 个）
    # ══════════════════════════════════════════════
    accounts = [
        ("sama", "Sam Altman", "OpenAI CEO. Building AGI.", 3200000, 2.0),
        ("kaborstnikov", "Andrej Karpathy", "AI researcher, ex-Tesla/OpenAI.", 1100000, 1.8),
        ("ylecun", "Yann LeCun", "Chief AI Scientist at Meta. Turing Award.", 850000, 1.5),
        ("demaborstnikov2", "Demis Hassabis", "CEO DeepMind. Nobel Prize.", 620000, 1.5),
        ("JeffDean", "Jeff Dean", "Chief Scientist at Google DeepMind.", 480000, 1.3),
        ("ClementDelangue", "Clement Delangue", "CEO Hugging Face.", 350000, 1.2),
        ("hardmaru", "David Ha", "AI researcher. Sakana AI.", 280000, 1.0),
        ("emaborstnikov1", "Elon Musk", "xAI, Tesla, SpaceX.", 180000000, 0.8),
    ]

    account_ids: dict[str, int] = {}
    for handle, name, bio, followers, weight in accounts:
        cur.execute(
            """INSERT INTO twitter_accounts
               (twitter_handle, display_name, bio, followers_count, weight, is_active,
                last_fetch_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)""",
            (
                handle,
                name,
                bio,
                followers,
                weight,
                (NOW - timedelta(hours=2)).isoformat(),
                (NOW - timedelta(days=7)).isoformat(),
                NOW.isoformat(),
            ),
        )
        account_ids[handle] = cur.lastrowid  # type: ignore[assignment]
    print(f"已创建 {len(accounts)} 个账号")

    # ══════════════════════════════════════════════
    # 2. 推文（12 条）
    # ══════════════════════════════════════════════
    tweets_data = [
        {
            "tweet_id": "1900001",
            "account": "sama",
            "text": "GPT-5 is here. Our most capable model yet. Reasoning, multimodal, agentic.",
            "title": "GPT-5 正式发布：OpenAI 迄今最强模型",
            "translation": "GPT-5 来了。这是我们迄今为止最强大的模型。具备推理、多模态和智能体能力。这标志着通用人工智能研究的一个重要里程碑。",
            "comment": "GPT-5 的发布再次证明 OpenAI 在大模型竞赛中的领先地位。值得关注的是其在推理和智能体方面的突破，这可能改变 AI 应用的格局。",
            "heat": 95,
            "ai_score": 92,
            "likes": 45000,
            "retweets": 12000,
            "replies": 8500,
        },
        {
            "tweet_id": "1900002",
            "account": "kaborstnikov",
            "text": "A deep dive into why transformers struggle with compositional reasoning. Thread 🧵",
            "title": "Karpathy 深度解析 Transformer 组合推理瓶颈",
            "translation": "深入探讨为什么 Transformer 在组合推理方面表现不佳。我认为核心问题在于注意力机制的固有局限性，它更擅长模式匹配而非逻辑推演。",
            "comment": "Karpathy 的技术分析一如既往地深入浅出。组合推理确实是当前 LLM 的阿喀琉斯之踵，未来的架构突破可能就在此处。",
            "heat": 88,
            "ai_score": 90,
            "likes": 23000,
            "retweets": 6500,
            "replies": 3200,
        },
        {
            "tweet_id": "1900003",
            "account": "ylecun",
            "text": "Autoregressive LLMs are a dead end for AGI. We need world models with planning capabilities.",
            "title": "LeCun 再批自回归 LLM：通往 AGI 的死胡同",
            "translation": "自回归大语言模型是通往 AGI 的死胡同。我们需要具备规划能力的世界模型。联合嵌入预测架构（JEPA）才是正确方向。",
            "comment": "LeCun 一贯的犀利观点。虽然业界对此存在分歧，但他提出的世界模型概念确实值得深思——语言可能不是理解世界的唯一途径。",
            "heat": 82,
            "ai_score": 85,
            "likes": 18000,
            "retweets": 5200,
            "replies": 4100,
        },
        {
            "tweet_id": "1900004",
            "account": "demaborstnikov2",
            "text": "Excited to announce AlphaFold 4. Now predicts protein-drug interactions with 95% accuracy.",
            "title": "AlphaFold 4 发布：蛋白质-药物交互预测准确率达 95%",
            "translation": "很高兴宣布 AlphaFold 4。现在能以 95% 的准确率预测蛋白质-药物交互作用。这将大大加速药物研发进程。",
            "comment": "AlphaFold 系列持续突破生物学边界。95% 的药物交互预测准确率意味着新药研发周期有望大幅缩短，这是 AI for Science 的标杆成果。",
            "heat": 78,
            "ai_score": 88,
            "likes": 15000,
            "retweets": 4800,
            "replies": 2100,
        },
        {
            "tweet_id": "1900005",
            "account": "JeffDean",
            "text": "Our new Gemini Ultra 2 achieves SOTA on 47 benchmarks. Efficiency improved 3x.",
            "title": "Jeff Dean 宣布 Gemini Ultra 2：47 项基准测试 SOTA",
            "translation": "我们的新 Gemini Ultra 2 在 47 项基准测试中达到最优水平。效率提升了 3 倍。这是 Google 在 AI 效率优化方面的重大进展。",
            "comment": "Gemini Ultra 2 的效率提升令人印象深刻。3 倍的效率改善意味着更低的推理成本，这对 AI 的普及至关重要。",
            "heat": 75,
            "ai_score": 82,
            "likes": 12000,
            "retweets": 3500,
            "replies": 1800,
        },
        {
            "tweet_id": "1900006",
            "account": "ClementDelangue",
            "text": "Open source AI is winning. HF just hit 2M models. The ecosystem is unstoppable.",
            "title": "Hugging Face 模型数突破 200 万：开源 AI 势不可挡",
            "translation": "开源 AI 正在胜出。Hugging Face 刚刚突破 200 万个模型。这个生态系统势不可挡。开放与协作是 AI 发展的最佳路径。",
            "comment": "200 万模型是一个里程碑数字。Hugging Face 证明了开源社区在 AI 领域的巨大力量，也让更多中小团队能够站在巨人的肩膀上。",
            "heat": 70,
            "ai_score": 75,
            "likes": 9500,
            "retweets": 2800,
            "replies": 1200,
        },
        {
            "tweet_id": "1900007",
            "account": "hardmaru",
            "text": "Small language models are the future for edge AI. Our new 3B model beats GPT-4 on domain tasks.",
            "title": "小模型逆袭：Sakana AI 30 亿参数模型在领域任务上超越 GPT-4",
            "translation": "小型语言模型是边缘 AI 的未来。我们新的 30 亿参数模型在领域任务上击败了 GPT-4。专精化是关键。",
            "comment": "小模型在特定领域超越大模型的趋势越来越明显。这对端侧 AI 部署意义重大，也暗示了 AI 应用的未来可能是'专而精'。",
            "heat": 65,
            "ai_score": 70,
            "likes": 7200,
            "retweets": 2100,
            "replies": 950,
        },
        {
            "tweet_id": "1900008",
            "account": "sama",
            "text": "We're making o3 free for all ChatGPT users starting next week.",
            "title": "OpenAI 宣布 o3 下周起对所有用户免费开放",
            "translation": "我们将从下周开始让所有 ChatGPT 用户免费使用 o3 模型。AI 应该惠及每一个人。",
            "comment": "o3 免费化是 OpenAI 在市场策略上的重要一步。这将直接冲击竞争对手的付费模型，同时也展示了 OpenAI 在成本控制上的信心。",
            "heat": 85,
            "ai_score": 80,
            "likes": 35000,
            "retweets": 9800,
            "replies": 6200,
        },
        {
            "tweet_id": "1900009",
            "account": "emaborstnikov1",
            "text": "Grok 4 coming soon. It will be the most truthful AI ever built.",
            "title": "Musk 预告 Grok 4：号称将成为史上最真实的 AI",
            "translation": "Grok 4 即将推出。它将是有史以来最真实的 AI。我们正在重新定义 AI 的诚实与透明度。",
            "comment": "Musk 对 Grok 4 的预告一如既往地充满豪言。不过'最真实的 AI'这个说法需要看具体的评测数据来验证。",
            "heat": 60,
            "ai_score": 55,
            "likes": 42000,
            "retweets": 8500,
            "replies": 12000,
        },
        {
            "tweet_id": "1900010",
            "account": "kaborstnikov",
            "text": "Just released a new YouTube video: 'Building GPT from scratch in 2 hours'. Link in bio.",
            "title": "Karpathy 发布新教程：2 小时从零构建 GPT",
            "translation": "刚发布了新的 YouTube 视频：《2 小时从零构建 GPT》。链接在简介中。这是我系列教程的最新一期。",
            "comment": "Karpathy 的教程系列一直是 AI 教育的黄金标准。从零构建 GPT 的实操内容对于理解 Transformer 架构具有极高的学习价值。",
            "heat": 72,
            "ai_score": 68,
            "likes": 28000,
            "retweets": 7500,
            "replies": 2800,
        },
    ]

    tweet_ids: dict[str, int] = {}
    for t in tweets_data:
        tweet_time = (NOW - timedelta(hours=8)).isoformat()
        cur.execute(
            """INSERT INTO tweets
               (tweet_id, account_id, digest_date, original_text, translated_text, title,
                ai_comment, base_heat_score, ai_importance_score, heat_score,
                likes, retweets, replies, tweet_url, tweet_time,
                is_ai_relevant, is_processed, is_quote_tweet, is_self_thread_reply,
                source, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 0, 0, 'auto', ?)""",
            (
                t["tweet_id"],
                account_ids[t["account"]],
                TODAY,
                t["text"],
                t["translation"],
                t["title"],
                t["comment"],
                t["heat"],
                t["ai_score"],
                t["heat"],
                t["likes"],
                t["retweets"],
                t["replies"],
                f"https://x.com/{t['account']}/status/{t['tweet_id']}",
                tweet_time,
                NOW.isoformat(),
            ),
        )
        tweet_ids[t["tweet_id"]] = cur.lastrowid  # type: ignore[assignment]
    print(f"已创建 {len(tweets_data)} 条推文")

    # ══════════════════════════════════════════════
    # 3. 聚合话题（2 个）
    # ══════════════════════════════════════════════
    topics_data = [
        {
            "title": "GPT-5 vs Gemini Ultra 2：新一轮大模型军备竞赛",
            "type": "aggregated",
            "summary": "OpenAI 发布 GPT-5 与 Google 推出 Gemini Ultra 2，标志着新一轮大模型竞赛正式开启。两者分别在推理能力和效率优化上取得突破，行业格局正在重塑。",
            "perspectives": json.dumps(
                [
                    {
                        "author": "Sam Altman",
                        "handle": "sama",
                        "viewpoint": "GPT-5 代表了通用智能的一大步，推理和智能体能力的结合将改变 AI 的使用方式。",
                    },
                    {
                        "author": "Jeff Dean",
                        "handle": "JeffDean",
                        "viewpoint": "效率才是关键。Gemini Ultra 2 用更少资源做到更多，这对实际部署至关重要。",
                    },
                    {
                        "author": "Yann LeCun",
                        "handle": "ylecun",
                        "viewpoint": "不管是 GPT-5 还是 Gemini，自回归架构的天花板终将到来。真正的突破需要范式转变。",
                    },
                ],
                ensure_ascii=False,
            ),
            "comment": "大模型竞赛进入白热化阶段。GPT-5 和 Gemini Ultra 2 各有侧重——前者追求能力上限，后者注重效率平衡。对开发者而言，选择正在变得更加丰富。",
            "heat": 90,
            "ai_score": 95,
            "tweet_count": 3,
            "source_tweets": [
                {"handle": "sama", "tweet_url": "https://x.com/sama/status/1900001"},
                {"handle": "JeffDean", "tweet_url": "https://x.com/JeffDean/status/1900005"},
                {"handle": "ylecun", "tweet_url": "https://x.com/ylecun/status/1900003"},
            ],
        },
        {
            "title": "开源 AI 生态爆发：从模型数量到边缘部署",
            "type": "aggregated",
            "summary": "Hugging Face 模型数突破 200 万，Sakana AI 的小模型在领域任务上超越 GPT-4。开源 AI 正在从数量增长转向质量飞跃，边缘部署成为新趋势。",
            "perspectives": json.dumps(
                [
                    {
                        "author": "Clement Delangue",
                        "handle": "ClementDelangue",
                        "viewpoint": "200 万模型证明了社区的力量。开源不仅是理念，更是最高效的创新方式。",
                    },
                    {
                        "author": "David Ha",
                        "handle": "hardmaru",
                        "viewpoint": "小而精的模型在实际应用中更有价值。边缘 AI 需要的不是参数量，而是领域适配能力。",
                    },
                ],
                ensure_ascii=False,
            ),
            "comment": "开源 AI 生态的繁荣不仅体现在数量上，更在于质量的提升和应用场景的拓展。小模型在边缘设备上的潜力正在被充分释放。",
            "heat": 72,
            "ai_score": 78,
            "tweet_count": 2,
            "source_tweets": [
                {
                    "handle": "ClementDelangue",
                    "tweet_url": "https://x.com/ClementDelangue/status/1900006",
                },
                {"handle": "hardmaru", "tweet_url": "https://x.com/hardmaru/status/1900007"},
            ],
        },
    ]

    topic_ids: list[int] = []
    for tp in topics_data:
        cur.execute(
            """INSERT INTO topics
               (digest_date, type, title, summary, perspectives, ai_comment,
                heat_score, ai_importance_score, tweet_count, version, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (
                TODAY,
                tp["type"],
                tp["title"],
                tp["summary"],
                tp["perspectives"],
                tp["comment"],
                tp["heat"],
                tp["ai_score"],
                tp["tweet_count"],
                NOW.isoformat(),
            ),
        )
        topic_ids.append(cur.lastrowid)  # type: ignore[arg-type]
    print(f"已创建 {len(topics_data)} 个话题")

    # ══════════════════════════════════════════════
    # 4. 今日日报（草稿）
    # ══════════════════════════════════════════════
    summary_text = (
        "今日 AI 圈重磅不断：GPT-5 与 Gemini Ultra 2 同台竞技，标志着新一轮大模型军备竞赛白热化；"
        "LeCun 再次炮轰自回归架构；AlphaFold 4 在药物研发领域取得突破性进展；"
        "开源 AI 生态持续爆发，小模型在边缘部署场景展现惊人潜力。"
    )
    cur.execute(
        """INSERT INTO daily_digest
           (digest_date, version, is_current, title, summary, item_count,
            status, publish_mode, created_at, updated_at)
           VALUES (?, 1, 1, ?, ?, ?, 'draft', 'manual', ?, ?)""",
        (TODAY, "智曦 AI 日报", summary_text, 10, NOW.isoformat(), NOW.isoformat()),
    )
    digest_id = cur.lastrowid
    print(f"已创建今日日报（草稿），ID={digest_id}")

    # ══════════════════════════════════════════════
    # 5. 日报条目（10 条 = 2 话题 + 8 推文）
    # ══════════════════════════════════════════════
    order = 0

    # 话题条目
    for i, tp in enumerate(topics_data):
        order += 1
        cur.execute(
            """INSERT INTO digest_items
               (digest_id, item_type, item_ref_id, display_order, is_pinned, is_excluded,
                snapshot_title, snapshot_summary, snapshot_comment, snapshot_perspectives,
                snapshot_heat_score, snapshot_source_tweets, snapshot_topic_type, created_at)
               VALUES (?, 'topic', ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, 'aggregated', ?)""",
            (
                digest_id,
                topic_ids[i],
                order,
                1 if i == 0 else 0,  # 第一个话题置顶
                tp["title"],
                tp["summary"],
                tp["comment"],
                tp["perspectives"],
                tp["heat"],
                json.dumps(tp["source_tweets"], ensure_ascii=False),
                NOW.isoformat(),
            ),
        )

    # 推文条目（取前 8 条）
    for t in tweets_data[:8]:
        order += 1
        cur.execute(
            """INSERT INTO digest_items
               (digest_id, item_type, item_ref_id, display_order, is_pinned, is_excluded,
                snapshot_title, snapshot_translation, snapshot_comment,
                snapshot_heat_score, snapshot_author_name, snapshot_author_handle,
                snapshot_tweet_url, snapshot_tweet_time, created_at)
               VALUES (?, 'tweet', ?, ?, 0, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                digest_id,
                tweet_ids[t["tweet_id"]],
                order,
                t["title"],
                t["translation"],
                t["comment"],
                t["heat"],
                _get_display_name(t["account"], accounts),
                t["account"],
                f"https://x.com/{t['account']}/status/{t['tweet_id']}",
                (NOW - timedelta(hours=8)).isoformat(),
                NOW.isoformat(),
            ),
        )
    print(f"已创建 {order} 条日报条目")

    # ══════════════════════════════════════════════
    # 6. 历史日报（过去 5 天）
    # ══════════════════════════════════════════════
    for days_ago in range(1, 6):
        d = (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        item_count = 10 - days_ago  # 5~9 条
        cur.execute(
            """INSERT INTO daily_digest
               (digest_date, version, is_current, title, summary, item_count,
                status, publish_mode, published_at, created_at, updated_at)
               VALUES (?, 1, 1, ?, ?, ?, 'published', 'manual', ?, ?, ?)""",
            (
                d,
                "智曦 AI 日报",
                f"第 {days_ago} 天前的 AI 动态回顾。",
                item_count,
                (NOW - timedelta(days=days_ago, hours=-1)).isoformat(),
                (NOW - timedelta(days=days_ago)).isoformat(),
                (NOW - timedelta(days=days_ago)).isoformat(),
            ),
        )
    print("已创建 5 条历史日报")

    # ══════════════════════════════════════════════
    # 7. API 成本记录
    # ══════════════════════════════════════════════
    cost_entries = [
        # 今日
        (
            TODAY,
            "claude",
            "chat",
            "/v1/messages",
            "claude-sonnet-4-20250514",
            15000,
            3500,
            0.0975,
            1,
            2800,
        ),
        (
            TODAY,
            "claude",
            "chat",
            "/v1/messages",
            "claude-sonnet-4-20250514",
            12000,
            2800,
            0.0780,
            1,
            3200,
        ),
        (
            TODAY,
            "claude",
            "chat",
            "/v1/messages",
            "claude-sonnet-4-20250514",
            8000,
            1500,
            0.0465,
            1,
            1900,
        ),
        (TODAY, "x", "search", "/2/tweets/search/recent", None, 0, 0, 0.0150, 1, 450),
        (TODAY, "x", "search", "/2/tweets/search/recent", None, 0, 0, 0.0150, 1, 380),
        (TODAY, "x", "user", "/2/users/by/username", None, 0, 0, 0.0050, 1, 200),
        (
            TODAY,
            "gemini",
            "generate",
            "/v1/models/gemini",
            "gemini-2.0-flash",
            5000,
            1200,
            0.0120,
            1,
            1500,
        ),
    ]

    # 过去 7 天的成本
    for days_ago in range(1, 8):
        d = (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        base_cost = 0.25 - days_ago * 0.02
        cost_entries.extend(
            [
                (
                    d,
                    "claude",
                    "chat",
                    "/v1/messages",
                    "claude-sonnet-4-20250514",
                    20000,
                    5000,
                    base_cost,
                    1,
                    3000,
                ),
                (d, "x", "search", "/2/tweets/search/recent", None, 0, 0, 0.03, 1, 400),
                (
                    d,
                    "gemini",
                    "generate",
                    "/v1/models/gemini",
                    "gemini-2.0-flash",
                    4000,
                    1000,
                    0.01,
                    1,
                    1200,
                ),
            ]
        )

    for entry in cost_entries:
        d, svc, call_type, endpoint, model, inp, out, cost, success, dur = entry
        cur.execute(
            """INSERT INTO api_cost_log
               (call_date, service, call_type, endpoint, model,
                input_tokens, output_tokens, estimated_cost,
                success, duration_ms, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (d, svc, call_type, endpoint, model, inp, out, cost, success, dur, NOW.isoformat()),
        )
    print(f"已创建 {len(cost_entries)} 条 API 成本记录")

    # ══════════════════════════════════════════════
    # 8. 任务运行记录
    # ══════════════════════════════════════════════
    job_runs = [
        ("pipeline", TODAY, "cron", "completed", None),
        ("fetch", TODAY, "cron", "completed", None),
        ("process", TODAY, "cron", "completed", None),
        ("digest", TODAY, "cron", "completed", None),
        ("pipeline", YESTERDAY, "cron", "completed", None),
        ("fetch", YESTERDAY, "cron", "completed", None),
        ("backup", YESTERDAY, "manual", "completed", None),
    ]
    for jt, d, trigger, status, err in job_runs:
        started = (NOW - timedelta(hours=3)).isoformat()
        finished = (NOW - timedelta(hours=2, minutes=50)).isoformat()
        cur.execute(
            """INSERT INTO job_runs
               (job_type, digest_date, trigger_source, status, error_message,
                started_at, finished_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (jt, d, trigger, status, err, started, finished, NOW.isoformat()),
        )
    print(f"已创建 {len(job_runs)} 条任务运行记录")

    # ══════════════════════════════════════════════
    # 9. 抓取日志
    # ══════════════════════════════════════════════
    cur.execute(
        """INSERT INTO fetch_log
           (fetch_date, total_accounts, success_count, fail_count, new_tweets,
            started_at, finished_at)
           VALUES (?, 8, 7, 1, 12, ?, ?)""",
        (
            TODAY,
            (NOW - timedelta(hours=3)).isoformat(),
            (NOW - timedelta(hours=2, minutes=55)).isoformat(),
        ),
    )
    print("已创建抓取日志")

    conn.commit()
    conn.close()
    print("\n✅ 测试数据生成完毕！启动后端 `uvicorn app.main:app --reload` 后即可查看效果。")


# 修复 display_name 查找逻辑
def _get_display_name(handle: str, accounts_list: list[tuple[str, str, str, int, float]]) -> str:
    for h, name, *_ in accounts_list:
        if h == handle:
            return name
    return handle


if __name__ == "__main__":
    main()
