# Examples

All example scripts use the shared `client.py` module. Set your API credentials as
environment variables before running any demo:

```bash
export AI_API_KEY="your-key"
export AI_BASE_URL="https://api.groq.com/openai/v1"   # or NVIDIA, OpenRouter, etc.
export AI_MODEL="llama-3.1-8b-instant"
```

## Quick Start

```bash
make build
python3 examples/e2e_demo.py          # Hacker News (no auth needed)
```

## Scripts

| Script | Target | Auth | What it tests |
|--------|--------|------|---------------|
| `test_tools.py` | `demo/index.html` | No | Core tool suite: browse, stealth, type, console, a11y, dialogs, multi-tab |
| `test_demo.py` | `demo/index.html` | No | Quick stealth + fingerprint validation |
| `e2e_demo.py` | Hacker News | No | Full 7-phase demo: stealth, a11y, AI click, extraction, multi-tab |
| `e2e_amazon_flipkart.py` | Amazon + Flipkart | No | Price comparison, Map-Reduce extraction, multi-tab |
| `e2e_naukri.py` | Naukri | No | Job search extraction |
| `e2e_reddit.py` | Reddit | No | AI click on post title + comment extraction |
| `e2e_linkedin.py` | LinkedIn | Yes (Google SSO) | Job extraction behind auth wall |
| `e2e_twitter.py` | X.com | Yes (Twitter login) | Infinite scroll + tweet extraction |

## Shared Client

`client.py` provides `GoWebMCPClient` — a reusable MCP stdio client:

```python
from examples.client import *

client = GoWebMCPClient()
client.call("browse", {"url": "https://example.com"})
result = client.call("extract", {"schema": {...}})
client.close()
```
