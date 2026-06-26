import re


def clean_text(text: str) -> str:
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_posts(posts: list[dict]) -> list[dict]:
    cleaned = []
    for post in posts:
        title = clean_text(post.get("title", ""))
        body = clean_text(post.get("selftext", ""))

        if not title:
            continue

        comments = []
        for c in post.get("comments", []):
            body_text = clean_text(c.get("body", ""))
            if body_text and body_text != "[deleted]" and body_text != "[removed]":
                comments.append({"body": body_text, "score": c.get("score", 0)})

        cleaned.append(
            {
                "id": post["id"],
                "title": title,
                "selftext": body,
                "score": post.get("score", 0),
                "num_comments": post.get("num_comments", 0),
                "comments": sorted(comments, key=lambda c: c["score"], reverse=True),
            }
        )

    return cleaned
