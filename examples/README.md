# GhostMCP Examples

Ready-to-run scripts demonstrating GhostMCP's capabilities. All scripts use the shared [`client.py`](client.py) MCP client.

## Prerequisites

```bash
# Build the server
cd GhostMCP
make build

# Set your API key (required for AI-powered tools)
export AI_API_KEY="your-key"
export AI_BASE_URL="https://api.groq.com/openai/v1"  # or OpenAI, Ollama, etc
export AI_MODEL="llama-3.1-8b-instant"
```

## Scripts

| Script | AI Key Required? | Description |
|---|---|---|
| **[test_page_context.py](test_page_context.py)** | ❌ No | Tests page detection on 10 major websites — great first script to run |
| **[e2e_amazon_flipkart.py](e2e_amazon_flipkart.py)** | ✅ Yes | Smart multi-step demo: Amazon vs Flipkart iPhone 15 comparison |
| **[e2e_demo.py](e2e_demo.py)** | ✅ Yes | Basic navigation + extraction demo |
| **[e2e_linkedin.py](e2e_linkedin.py)** | ✅ Yes | LinkedIn profile/job extraction |
| **[e2e_reddit.py](e2e_reddit.py)** | ✅ Yes | Reddit subreddit scraping |
| **[e2e_twitter.py](e2e_twitter.py)** | ✅ Yes | Twitter/X feed extraction |
| **[e2e_naukri.py](e2e_naukri.py)** | ✅ Yes | Job portal extraction |
| **[test_tools.py](test_tools.py)** | ✅ Yes | Tool integration tests |
| **[test_demo.py](test_demo.py)** | ✅ Yes | Quick demo test |

## Quick Start

```bash
# Run without API key (page context test)
python3 examples/test_page_context.py

# Run with API key
export AI_API_KEY="gsk_..."
export AI_BASE_URL="https://api.groq.com/openai/v1"
export AI_MODEL="llama-3.1-8b-instant"
python3 examples/e2e_amazon_flipkart.py
```

## Shared Client (`client.py`)

All scripts use the `GhostMCPClient` class:

```python
from examples.client import GhostMCPClient

client = GhostMCPClient()
client.call("browse", {"url": "https://example.com"})
data = client.call("extract", {"schema": {...}})
client.close()
```

## Writing Your Own Script

1. Copy the template from [CONTRIBUTING.md](../CONTRIBUTING.md#-adding-example-scripts)
2. Use `sys.path.insert(0, '.')` and `from examples.client import *`
3. Run from the project root: `python3 examples/your_script.py`
4. Submit a PR!

## Page Types Detected

The `get_page_context` tool can identify these page types (zero LLM cost):

| Page Type | Examples |
|---|---|
| `search_results` | Google, Bing, DuckDuckGo |
| `product_page` | Amazon, Flipkart product pages |
| `social_feed` | Reddit, Twitter, Facebook |
| `video_platform` | YouTube |
| `code_repository` | GitHub |
| `article` | Wikipedia, blogs, news sites |
| `login_page` | Any login/signup page |
| `listing_page` | Hacker News, StackOverflow |
| `qa_page` | StackOverflow questions |
| `form_page` | Contact forms, surveys |
