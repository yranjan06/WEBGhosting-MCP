# WEBGhosting Examples

Ready-to-run scripts demonstrating WEBGhosting's capabilities. All scripts use the shared [`client.py`](client.py) MCP client.

## Prerequisites

```bash
# Build the server
cd WEBGhosting-MCP
make build

# Set your API key (required for AI-powered tools)
export AI_API_KEY="your-key"
export AI_BASE_URL="https://api.groq.com/openai/v1"  # or OpenAI, Ollama, etc
export AI_MODEL="llama-3.1-8b-instant"
```

## Layout

Examples stay in one folder for easy discovery, but they follow a simple structure:

- `client.py`: shared MCP stdio client
- `test_*.py`: validation and tool checks
- `smoke_major_sites.py`: reusable prompt-driven smoke suite
- `e2e_*.py`: live end-to-end demos
- `*_voice_*.py`, `ui_voice_agent.py`, `wavy_voice_app.py`: experimental voice interfaces

## Scripts

| Script | AI Key Required? | Description |
|---|---|---|
| **[test_page_context.py](test_page_context.py)** | ❌ No | Tests page detection on 10 major websites — great first script to run |
| **[test_tools.py](test_tools.py)** | ✅ Yes | Tool integration tests against the local demo page |
| **[test_demo.py](test_demo.py)** | ✅ Yes | Quick MCP integration sanity check |
| **[smoke_major_sites.py](smoke_major_sites.py)** | ✅ Yes | Runs a reusable prompt-driven smoke suite across major public websites |
| **[e2e_amazon_flipkart.py](e2e_amazon_flipkart.py)** | ✅ Yes | Smart multi-step demo: Amazon vs Flipkart iPhone 15 comparison |
| **[e2e_demo.py](e2e_demo.py)** | ✅ Yes | Basic navigation + extraction demo |
| **[e2e_linkedin.py](e2e_linkedin.py)** | ✅ Yes | LinkedIn profile/job extraction |
| **[e2e_reddit.py](e2e_reddit.py)** | ✅ Yes | Reddit subreddit scraping |
| **[e2e_twitter.py](e2e_twitter.py)** | ✅ Yes | Twitter/X feed extraction |
| **[e2e_naukri.py](e2e_naukri.py)** | ✅ Yes | Job portal extraction |
| **[e2e_voice_demo.py](e2e_voice_demo.py)** | ✅ Yes | Voice-command style cinematic cross-site demo |
| **[sarvam_voice_agent.py](sarvam_voice_agent.py)** | ✅ Extra deps | CLI voice demo using SarvamAI + PyAudio |
| **[ui_voice_agent.py](ui_voice_agent.py)** | ✅ Extra deps | Gradio-based voice UI demo |
| **[wavy_voice_app.py](wavy_voice_app.py)** | ✅ Extra deps | FastAPI voice app experiment |

## Quick Start

```bash
# Run without API key (page context test)
python3 examples/test_page_context.py

# Run with API key
export AI_API_KEY="gsk_..."
export AI_BASE_URL="https://api.groq.com/openai/v1"
export AI_MODEL="llama-3.1-8b-instant"
python3 examples/e2e_amazon_flipkart.py

# Run the reusable major-site smoke suite
python3 examples/smoke_major_sites.py --sites hackernews,github,wikipedia
```

For prompt-driven live-site validation across major websites, see [../MAJOR_SITE_SMOKE_TESTS.md](../MAJOR_SITE_SMOKE_TESTS.md).

## Shared Client (`client.py`)

All scripts use the `WEBGhostingClient` class:

```python
from examples.client import WEBGhostingClient

client = WEBGhostingClient()
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
