import praw
import os
from dotenv import load_dotenv

load_dotenv()


def get_reddit_client() -> praw.Reddit:
    return praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT", "reddit-analytics-bot/1.0"),
    )


def fetch_posts(subreddit_name: str, sample_size: int = 50) -> list[dict]:
    reddit = get_reddit_client()
    subreddit = reddit.subreddit(subreddit_name)

    posts = []
    for submission in subreddit.hot(limit=sample_size):
        comments = []
        submission.comments.replace_more(limit=0)
        for comment in sorted(
            submission.comments.list(), key=lambda c: c.score, reverse=True
        )[:10]:
            comments.append({"body": comment.body, "score": comment.score})

        posts.append(
            {
                "id": submission.id,
                "title": submission.title,
                "selftext": submission.selftext,
                "score": submission.score,
                "url": submission.url,
                "num_comments": submission.num_comments,
                "comments": comments,
            }
        )

    return posts
