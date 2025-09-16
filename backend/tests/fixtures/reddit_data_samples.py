"""
Reddit真实数据样本 - PRD03-08
为测试提供真实的Reddit数据模拟

严格类型安全：
- 禁止Any类型
- 100% mypy --strict兼容
- 禁止type: ignore
"""

from typing import Dict, List, Optional, Union, cast
from datetime import datetime, timedelta
import random


class RedditDataSamples:
    """Reddit数据样本生成器"""

    @staticmethod
    def get_real_subreddits() -> List[Dict[str, Union[str, int, float]]]:
        """获取真实的subreddit数据"""
        return [
            {
                "name": "r/startups",
                "display_name": "Startups",
                "subscribers": 1543287,
                "active_users": 2341,
                "description": "Welcome to r/startups, the place to discuss startup problems and solutions.",
                "created_utc": 1234567890,
                "over18": False,
                "lang": "en",
                "submission_type": "any",
                "avg_posts_per_day": 45.3,
                "avg_comments_per_post": 12.7,
            },
            {
                "name": "r/SaaS",
                "display_name": "SaaS",
                "subscribers": 324891,
                "active_users": 512,
                "description": "All things related to Software as a Service (SaaS).",
                "created_utc": 1345678901,
                "over18": False,
                "lang": "en",
                "submission_type": "any",
                "avg_posts_per_day": 18.5,
                "avg_comments_per_post": 8.3,
            },
            {
                "name": "r/ProductManagement",
                "display_name": "Product Management",
                "subscribers": 189234,
                "active_users": 287,
                "description": "For product managers, by product managers.",
                "created_utc": 1456789012,
                "over18": False,
                "lang": "en",
                "submission_type": "any",
                "avg_posts_per_day": 12.1,
                "avg_comments_per_post": 15.4,
            },
            {
                "name": "r/entrepreneur",
                "display_name": "Entrepreneur",
                "subscribers": 2145678,
                "active_users": 3456,
                "description": "A community of individuals who seek to solve problems, network professionally.",
                "created_utc": 1234567890,
                "over18": False,
                "lang": "en",
                "submission_type": "any",
                "avg_posts_per_day": 67.8,
                "avg_comments_per_post": 9.2,
            },
            {
                "name": "r/remotework",
                "display_name": "Remote Work",
                "subscribers": 456789,
                "active_users": 678,
                "description": "A place to discuss remote work, share tips, and find remote jobs.",
                "created_utc": 1567890123,
                "over18": False,
                "lang": "en",
                "submission_type": "any",
                "avg_posts_per_day": 23.4,
                "avg_comments_per_post": 11.6,
            },
        ]

    @staticmethod
    def get_sample_posts(
        subreddit: str, count: int = 10
    ) -> List[Dict[str, Union[str, int, float, bool]]]:
        """生成特定subreddit的帖子样本"""

        # 不同subreddit的典型帖子模板
        post_templates = {
            "r/startups": [
                {
                    "title": "Just launched our MVP - looking for feedback",
                    "selftext": "We've been working on this for 6 months...",
                    "score": 234,
                    "num_comments": 45,
                    "upvote_ratio": 0.92,
                },
                {
                    "title": "Failed after 2 years - lessons learned",
                    "selftext": "Here's what I wish I knew when starting...",
                    "score": 892,
                    "num_comments": 123,
                    "upvote_ratio": 0.96,
                },
                {
                    "title": "How do you handle customer churn?",
                    "selftext": "Our churn rate is killing us...",
                    "score": 156,
                    "num_comments": 67,
                    "upvote_ratio": 0.88,
                },
            ],
            "r/SaaS": [
                {
                    "title": "What's your tech stack for a B2B SaaS?",
                    "selftext": "Planning to build a new SaaS product...",
                    "score": 167,
                    "num_comments": 89,
                    "upvote_ratio": 0.91,
                },
                {
                    "title": "Pricing strategies that actually work",
                    "selftext": "We tried 5 different pricing models...",
                    "score": 445,
                    "num_comments": 78,
                    "upvote_ratio": 0.94,
                },
                {
                    "title": "MRR milestone: $10k! Here's how",
                    "selftext": "It took us 18 months to reach this...",
                    "score": 678,
                    "num_comments": 92,
                    "upvote_ratio": 0.97,
                },
            ],
            "r/ProductManagement": [
                {
                    "title": "How to prioritize features with limited resources?",
                    "selftext": "Our backlog is growing faster than we can build...",
                    "score": 234,
                    "num_comments": 56,
                    "upvote_ratio": 0.89,
                },
                {
                    "title": "Tools for async collaboration with remote teams",
                    "selftext": "Looking for recommendations on tools...",
                    "score": 189,
                    "num_comments": 43,
                    "upvote_ratio": 0.87,
                },
                {
                    "title": "From engineer to PM - one year later",
                    "selftext": "Sharing my transition experience...",
                    "score": 567,
                    "num_comments": 98,
                    "upvote_ratio": 0.95,
                },
            ],
        }

        # 默认模板
        default_templates = [
            {
                "title": "Looking for advice on scaling",
                "selftext": "We're growing fast and need help...",
                "score": 145,
                "num_comments": 34,
                "upvote_ratio": 0.85,
            },
            {
                "title": "What tools do you use for project management?",
                "selftext": "Currently evaluating different options...",
                "score": 89,
                "num_comments": 67,
                "upvote_ratio": 0.82,
            },
        ]

        templates = post_templates.get(subreddit, default_templates)
        posts = []

        for i in range(min(count, len(templates) * 3)):
            template = templates[i % len(templates)]

            # 添加变化以创建唯一的帖子
            post: Dict[str, Union[str, int, float, bool]] = {
                "id": f"post_{subreddit}_{i}",
                "title": f"{template['title']} #{i+1}" if i > 0 else cast(str, template["title"]),
                "selftext": cast(str, template["selftext"]),
                "score": cast(int, template["score"]) + random.randint(-50, 50),
                "num_comments": cast(int, template["num_comments"]) + random.randint(-10, 10),
                "upvote_ratio": max(
                    0.5, min(1.0, cast(float, template["upvote_ratio"]) + random.uniform(-0.1, 0.1))
                ),
                "subreddit": subreddit,
                "created_utc": int(
                    (datetime.now() - timedelta(days=random.randint(0, 30))).timestamp()
                ),
                "author": f"user_{random.randint(1000, 9999)}",
                "is_self": True,
                "over_18": False,
                "spoiler": False,
                "stickied": False,
                "locked": False,
                "permalink": f"/r/{subreddit[2:]}/comments/{i}/",
                "url": f"https://reddit.com/r/{subreddit[2:]}/comments/{i}/",
            }

            posts.append(post)

        return posts

    @staticmethod
    def get_sample_comments(
        post_id: str, count: int = 5
    ) -> List[Dict[str, Union[str, int, bool]]]:
        """生成帖子的评论样本"""
        comment_templates = [
            "This is exactly what I was looking for!",
            "Have you considered trying [alternative solution]?",
            "We had the same problem and solved it by...",
            "Great post! Can you share more details about...",
            "I disagree with this approach because...",
            "Thanks for sharing! This helped me realize...",
            "+1 to this. We've been using it for months.",
            "Be careful with this, we ran into issues with...",
            "Does anyone have experience with [related tool]?",
            "This won't scale. You need to think about...",
        ]

        comments = []
        for i in range(count):
            comment: Dict[str, Union[str, int, bool]] = {
                "id": f"comment_{post_id}_{i}",
                "parent_id": post_id,
                "body": comment_templates[i % len(comment_templates)],
                "score": random.randint(1, 100),
                "created_utc": int(
                    (
                        datetime.now() - timedelta(hours=random.randint(1, 48))
                    ).timestamp()
                ),
                "author": f"commenter_{random.randint(1000, 9999)}",
                "is_submitter": False,
                "stickied": False,
                "collapsed": False,
                "controversiality": 0 if random.random() > 0.2 else 1,
                "depth": 0,
            }
            comments.append(comment)

        return comments

    @staticmethod
    def generate_pain_point_posts() -> List[Dict[str, Union[str, int, float, bool]]]:
        """生成包含痛点的帖子"""
        return [
            {
                "id": "pain_1",
                "title": "Struggling with team communication across timezones",
                "selftext": "We have team members in 5 different timezones. Standup meetings are impossible, async communication is slow, and important decisions get delayed. What tools or processes have worked for you?",
                "score": 456,
                "num_comments": 89,
                "upvote_ratio": 0.94,
                "subreddit": "r/remotework",
                "created_utc": int(datetime.now().timestamp()),
                "sentiment": "negative",
                "pain_intensity": "high",
            },
            {
                "id": "pain_2",
                "title": "Project tracking is a nightmare with current tools",
                "selftext": "Using 5 different tools (Jira, Slack, Notion, Google Docs, Figma) and spending more time updating status than actually working. There has to be a better way!",
                "score": 678,
                "num_comments": 123,
                "upvote_ratio": 0.96,
                "subreddit": "r/ProductManagement",
                "created_utc": int(datetime.now().timestamp()),
                "sentiment": "negative",
                "pain_intensity": "very_high",
            },
            {
                "id": "pain_3",
                "title": "Customer feedback gets lost between teams",
                "selftext": "Sales has their CRM, support uses Zendesk, product uses Linear, and engineering uses GitHub. Customer feedback never makes it to the product roadmap properly.",
                "score": 345,
                "num_comments": 67,
                "upvote_ratio": 0.91,
                "subreddit": "r/SaaS",
                "created_utc": int(datetime.now().timestamp()),
                "sentiment": "negative",
                "pain_intensity": "high",
            },
        ]

    @staticmethod
    def generate_feature_request_posts() -> (
        List[Dict[str, Union[str, int, float, bool]]]
    ):
        """生成包含功能需求的帖子"""
        return [
            {
                "id": "feature_1",
                "title": "Looking for PM tool with AI-powered insights",
                "selftext": "Does anyone know a project management tool that can analyze team patterns and predict bottlenecks? Would love AI suggestions for resource allocation.",
                "score": 234,
                "num_comments": 45,
                "upvote_ratio": 0.88,
                "subreddit": "r/ProductManagement",
                "created_utc": int(datetime.now().timestamp()),
                "sentiment": "neutral",
                "request_type": "ai_automation",
            },
            {
                "id": "feature_2",
                "title": "Need: Git integration directly in project management tool",
                "selftext": "Want to see code commits, PRs, and deploy status right next to our tasks. Switching between GitHub and our PM tool is inefficient.",
                "score": 189,
                "num_comments": 34,
                "upvote_ratio": 0.85,
                "subreddit": "r/startups",
                "created_utc": int(datetime.now().timestamp()),
                "sentiment": "neutral",
                "request_type": "integration",
            },
            {
                "id": "feature_3",
                "title": "Wishlist: Automatic standup reports from activity",
                "selftext": "Imagine if the tool could generate standup updates based on what you actually did (commits, ticket updates, meetings) instead of manual writing.",
                "score": 567,
                "num_comments": 98,
                "upvote_ratio": 0.93,
                "subreddit": "r/remotework",
                "created_utc": int(datetime.now().timestamp()),
                "sentiment": "positive",
                "request_type": "automation",
            },
        ]

    @staticmethod
    def generate_opportunity_posts() -> List[Dict[str, Union[str, int, float, bool]]]:
        """生成包含市场机会的帖子"""
        return [
            {
                "id": "opp_1",
                "title": "SMBs are completely underserved in the project management space",
                "selftext": "Enterprise tools are too complex and expensive. Free tools lack essential features. There's a huge gap for tools targeting 10-50 person companies.",
                "score": 892,
                "num_comments": 156,
                "upvote_ratio": 0.97,
                "subreddit": "r/entrepreneur",
                "created_utc": int(datetime.now().timestamp()),
                "sentiment": "positive",
                "opportunity_type": "market_gap",
            },
            {
                "id": "opp_2",
                "title": "Nobody is solving PM for creative agencies properly",
                "selftext": "Agencies have unique needs: client approvals, revision tracking, time billing. Generic PM tools don't cut it. Specific agency tools are outdated.",
                "score": 445,
                "num_comments": 78,
                "upvote_ratio": 0.92,
                "subreddit": "r/SaaS",
                "created_utc": int(datetime.now().timestamp()),
                "sentiment": "neutral",
                "opportunity_type": "vertical_market",
            },
            {
                "id": "opp_3",
                "title": "The integration problem is getting worse, not better",
                "selftext": "Every new tool creates another silo. We need something that truly unifies work, not just adds another integration.",
                "score": 678,
                "num_comments": 134,
                "upvote_ratio": 0.94,
                "subreddit": "r/startups",
                "created_utc": int(datetime.now().timestamp()),
                "sentiment": "negative",
                "opportunity_type": "integration_platform",
            },
        ]

    @staticmethod
    def generate_edge_case_posts() -> List[Dict[str, Union[str, int, float, bool]]]:
        """生成边界情况的帖子"""
        return [
            {
                "id": "edge_1",
                "title": "",  # 空标题
                "selftext": "Content without title",
                "score": 0,
                "num_comments": 0,
                "upvote_ratio": 0.5,
                "subreddit": "r/test",
                "created_utc": int(datetime.now().timestamp()),
            },
            {
                "id": "edge_2",
                "title": "A" * 300,  # 超长标题
                "selftext": "Normal content",
                "score": 10,
                "num_comments": 2,
                "upvote_ratio": 0.6,
                "subreddit": "r/test",
                "created_utc": int(datetime.now().timestamp()),
            },
            {
                "id": "edge_3",
                "title": "Post with special chars 中文 émoji 🚀 symbols @#$%",
                "selftext": "Testing unicode handling",
                "score": 50,
                "num_comments": 10,
                "upvote_ratio": 0.75,
                "subreddit": "r/test",
                "created_utc": int(datetime.now().timestamp()),
            },
            {
                "id": "edge_4",
                "title": "[deleted]",
                "selftext": "[removed]",
                "score": 0,
                "num_comments": 0,
                "upvote_ratio": 0,
                "subreddit": "r/test",
                "created_utc": 0,
                "deleted": True,
            },
        ]
