import json
import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def analyze_posts(posts: list[dict]) -> dict:
    sample_size = len(posts)
    posts_text = json.dumps(
        [
            {
                "id": p["id"],
                "title": p["title"],
                "body": p["selftext"],
                "top_comments": [c["body"] for c in p["comments"][:5]],
            }
            for p in posts
        ],
        ensure_ascii=False,
    )

    prompt = f"""You are a market research analyst. Analyze the following {sample_size} Reddit posts and return a JSON object with this exact structure:

{{
  "summary": "2-3 sentence overall summary of what this community discusses",
  "sentiment_breakdown": {{
    "complaint_frustration": <integer percentage 0-100>,
    "neutral_discussion": <integer percentage 0-100>,
    "positive_satisfaction": <integer percentage 0-100>
  }},
  "pain_points": [
    {{
      "description": "short sentence describing the pain point",
      "frequency_pct": <integer percentage of posts mentioning this>,
      "urgency": "high|medium|low"
    }}
  ],
  "demands": [
    {{
      "description": "short sentence describing what users want or need",
      "frequency_pct": <integer percentage>
    }}
  ],
  "classified_posts": [
    {{
      "id": "<post id>",
      "classification": "complaint|neutral|positive",
      "key_insight": "one short sentence"
    }}
  ]
}}

The three sentiment_breakdown values must sum to 100.
Return only the JSON object, no markdown fences.

Posts data:
{posts_text}"""

    client = _get_client()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    return json.loads(raw)
