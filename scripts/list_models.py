"""Print the GitHub Models catalog as a Markdown table (needs GITHUB_TOKEN with models:read)."""
import os
import sys

import httpx

resp = httpx.get(
    "https://models.github.ai/catalog/models",
    headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"},
    follow_redirects=True,
    timeout=30,
)
try:
    resp.raise_for_status()
    models = resp.json()
except ValueError as exc:
    sys.exit(
        f"catalog response is not JSON ({exc}): HTTP {resp.status_code}, "
        f"content-type={resp.headers.get('content-type')!r}, final url={resp.url}, body={resp.content[:300]!r}"
    )

print("\n## GitHub Models catalog\n")
print("| id | rate limit tier |\n| --- | --- |")
for m in sorted(models, key=lambda m: m["id"]):
    print(f"| {m['id']} | {m.get('rate_limit_tier', '')} |")
