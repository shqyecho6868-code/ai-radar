import httpx

USER_AGENT = "ai-radar/0.1 (+https://github.com/shqyecho6868-code/ai-radar)"


def client(**kwargs) -> httpx.Client:
    headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
    return httpx.Client(headers=headers, timeout=30, follow_redirects=True, **kwargs)
