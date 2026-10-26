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
if resp.status_code != 200 or not resp.text.strip():
    sys.exit(f"catalog request failed: HTTP {resp.status_code}: {resp.text[:300]!r}")

print("\n## GitHub Models catalog\n")
print("| id | rate limit tier |\n| --- | --- |")
for m in sorted(resp.json(), key=lambda m: m["id"]):
    print(f"| {m['id']} | {m.get('rate_limit_tier', '')} |")
