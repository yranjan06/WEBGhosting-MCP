<p align="center">
  <h1 align="center">WEBGhosting</h1>
  <p align="center">
    <strong>Agentic Stealth Browser &bull; Recipe Orchestrator &bull; MCP Server &bull; Built for AI Agents</strong>
  </p>
  <p align="center">
    <a href="https://github.com/yranjan06/WEBGhosting-MCP/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
    <a href="https://go.dev"><img src="https://img.shields.io/badge/Go-1.26+-00ADD8?logo=go" alt="Go Version"></a>
    <a href="https://github.com/yranjan06/WEBGhosting-MCP/blob/main/CONTRIBUTING.md"><img src="https://img.shields.io/badge/contributions-welcome-brightgreen.svg" alt="Contributions Welcome"></a>
    <a href="https://github.com/yranjan06/WEBGhosting-MCP/issues"><img src="https://img.shields.io/github/issues/yranjan06/WEBGhosting-MCP" alt="Issues"></a>
    <a href="https://github.com/yranjan06/WEBGhosting-MCP/stargazers"><img src="https://img.shields.io/github/stars/yranjan06/WEBGhosting-MCP?style=social" alt="Stars"></a>
  </p>
  <p align="center">
    <a href="#quick-start">Quick Start</a> &bull;
    <a href="#what-it-can-do">Features</a> &bull;
    <a href="#repo-layout">Repo Layout</a> &bull;
    <a href="#recipe-orchestrator">Orchestrator</a> &bull;
    <a href="#live-site-smoke-tests">Smoke Tests</a> &bull;
    <a href="#all-34-tools">Tools</a> &bull;
    <a href="CONTRIBUTING.md">Contributing</a>
  </p>
</p>

---

Most AI agents can think. Very few can actually browse.

**WEBGhosting changes that.**

It is the stealthiest and most reliable MCP browser server for AI agents, built for real production use. With **34 powerful tools**, 22 anti-fingerprint scripts, LLM-powered extraction, and a **Recipe Orchestrator** that turns natural language commands into automated browser workflows — it gives AI agents a browser they can truly control.

Navigate pages. Click buttons. Fill forms. Extract structured data. Run multi-step recipes across websites. **All through natural language.**

Built in Go with a Python orchestration layer, fully compliant with the Model Context Protocol. Works seamlessly with Cursor, GitHub Copilot, Cloud Code, and any MCP-compatible client.

Built with ❤️ for the AI community. **[Contributions welcome!](CONTRIBUTING.md)**

---

## What It Can Do

| Capability | What it means for your Agent |
|---|---|
| **Recipe Orchestrator** | Give a natural language command like *"Go to HN and find the top story"* — WEBGhosting auto-generates a recipe, executes it, returns data, and cleans up |
| **Pre-cached Selectors** | 134 selectors across 12 major website packs (Amazon, Reddit, YouTube, GitHub, etc.) for instant, reliable DOM access |
| **LLM-Powered Navigation** | Tell it `click("Login button")` or `type("Search box", "AI")` and it figures out the DOM |
| **Stealth Hardening** | 22 fingerprint patches (Bezier mouse, typing cadence, WebGL noise) to bypass bot protection |
| **Map-Reduce Extraction** | Splits massive 300K+ char pages into chunks, runs parallel LLM extraction, stitches JSON |
| **Page Context Analysis** | Zero-LLM instant analyzer that detects page type, features, and interactive elements |
| **Vision System** | Gets labeled screenshots with bounding boxes mapped directly to DOM elements for VLMs |
| **Plugin System** | Drop JSON+JS into `extensions/` and it auto-registers as a new native MCP tool |
| **Memory Store** | Key-value storage between tool calls for complex, multi-step agent workflows |
| **Parallel Extraction** | Extract structured data from multiple URLs simultaneously using isolated browser contexts |
| **Universal LLM Support** | Works seamlessly with OpenAI, Groq, Ollama, Together, NVIDIA NIM, and LM Studio |
| **Docker Ready** | Single-command containerized deployment for headless scraping at scale |

---

## Repo Layout

WEBGhosting is easiest to work with if you treat it as three layers:

- `cmd/server/` and `pkg/`: the Go MCP server, browser runtime, stealth layer, and tool implementations
- `orchestrator/`: the Python recipe generator, selector routing, and workflow executor
- `examples/`: demos, smoke tests, and integration-style validation scripts

---

## Quick Start

```bash
git clone https://github.com/yranjan06/WEBGhosting-MCP.git
cd WEBGhosting-MCP
make install-deps
make build
```

### IDE Integration Setup

**For VS Code (GitHub Copilot Chat):**
1. Create a `.vscode` folder in your project root (if it doesn't exist).
2. Inside it, create a file named `mcp.json`.
3. Paste the following configuration, ensuring you use the **absolute path** to your binary:

```json
{
  "servers": {
    "webghosting": {
      "type": "stdio",
      "command": "/absolute/path/to/WEBGhosting/webmcp",
      "args": [],
      "env": {
        "AI_API_KEY": "your-api-key",
        "AI_MODEL": "gpt-4o"
      }
    }
  }
}
```
4. Restart your VS Code window (`Developer: Reload Window`).
5. Open Copilot Chat, select "Agent" mode, and start giving prompts!

**For Cursor, Roo Code, or Claude Desktop:**
Open your MCP configuration file (e.g., `mcp.json` or `claude_desktop_config.json`) and add the server:

```json
{
  "mcpServers": {
    "webghosting": {
      "command": "/absolute/path/to/WEBGhosting/webmcp",
      "env": {
        "AI_API_KEY": "your-api-key",
        "AI_BASE_URL": "https://api.openai.com/v1", 
        "AI_MODEL": "gpt-4o" 
      }
    }
  }
}
```

Or run with Docker:

```bash
make docker
docker run -p 8080:8080 -e AI_API_KEY="your-key" -e BROWSER_HEADLESS="true" webghosting --port=8080
```

### Try Without an API Key

`get_page_context` runs pure JavaScript — no LLM needed:

```bash
python3 examples/test_page_context.py
```

```json
{
  "page_type": "product_page",
  "has_search": true,
  "has_reviews": true,
  "has_cart": true,
  "link_count": 322,
  "main_headings": ["Apple iPhone 15 (128 GB) - Black"]
}
```

---

## Recipe Orchestrator

Give any browser task in natural language — WEBGhosting auto-generates a recipe, executes it, returns data, and cleans up.

The orchestrator uses Python's standard library HTTP client, so there is no extra `pip install` step required just to run `python3 -m orchestrator.orchestrator`.

```bash
export AI_API_KEY="your-key" AI_BASE_URL="https://api.openai.com/v1" AI_MODEL="gpt-4o"

python3 -m orchestrator.orchestrator --run "Go to Hacker News and find the top story title"
python3 -m orchestrator.orchestrator --run "Go to Amazon and find iPhone 16 price"
python3 -m orchestrator.orchestrator hn_reddit_linkedin.json   # run pre-built recipe
python3 -m orchestrator.orchestrator --resume                  # resume after crash
```

MCP tools for IDE agents: `run_task`, `run_recipe`, `list_recipes`

For recipe writing guide, supported actions, and selector database docs, see [CONTRIBUTING.md](CONTRIBUTING.md#recipe-orchestrator).

---

## Live Site Smoke Tests

Use the built-in smoke runner for quick live-site validation:

```bash
python3 examples/smoke_major_sites.py --list
python3 examples/smoke_major_sites.py --sites hackernews,github,wikipedia
```

Quick examples:

```bash
make smoke-list
make smoke-sites

python3 -m orchestrator.orchestrator --run "Open the Hacker News homepage. Extract the title and author of the 5th article. Then open the comments page for that same 5th article and extract the text of the first 2 comments."

python3 -m orchestrator.orchestrator --run "Open Wikipedia and extract the first paragraph and infobox title for the article on Model Context Protocol."

python3 -m orchestrator.orchestrator --run "Open GitHub and extract the repository name, description, and star count from microsoft/playwright."
```

Prompting tip: when referring to numbered items, keep the ordinal consistent. A prompt like "5th article" and then "same 4th article" is ambiguous, and the LLM may normalize it one way or the other.

---

## Environment Variables

- `AI_API_KEY` (required) — API key for your LLM provider
- `AI_BASE_URL` — custom endpoint URL (default: OpenAI)
- `AI_MODEL` — model name (default: `gpt-4o`)
- `EXTRACTION_MODEL` — separate faster model for data extraction
- `BROWSER_HEADLESS` — set `true` for headless mode
- `BROWSER_USER_DATA_DIR` — persist cookies/sessions across restarts
- `HTTP_PROXY` — proxy server URL
- `HTTPS_PROXY` — proxy server URL for HTTPS traffic
- `PROXY_LIST` — comma-separated proxy pool for per-run rotation in the orchestrator

Works with any OpenAI-compatible provider:
```bash
# Groq (free)
export AI_API_KEY="gsk_..." AI_BASE_URL="https://api.groq.com/openai/v1" AI_MODEL="llama-3.1-8b-instant"

# Ollama (local)
export AI_API_KEY="ollama" AI_BASE_URL="http://localhost:11434/v1" AI_MODEL="llama3.1"

# NVIDIA NIM
export AI_API_KEY="nvapi-..." AI_BASE_URL="https://integrate.api.nvidia.com/v1" AI_MODEL="meta/llama3-70b-instruct"
```

Per-run IP rotation example:

```bash
export PROXY_LIST="http://proxy1.example.com:8080,http://proxy2.example.com:8080"
python3 -m orchestrator.orchestrator --run "Go to Hacker News and find the top story title"
```

## All 34 Tools

**Navigation** — `browse`, `go_back`, `go_forward`

**AI Interaction** — `reframe_user_prompt`, `click`, `type`, `press_key`, `fill_form`, `scroll`, `scroll_to_bottom`

**Data Extraction** — `extract`, `parallel_extract`, `execute_js`, `get_accessibility_tree`, `get_page_context`

**Vision** — `screenshot`, `capture_labeled_snapshot`

**Memory** — `memorize_data`, `recall_data`, `list_memory_keys`

**Multi-Tab** — `open_tab`, `switch_tab`, `close_tab`, `list_tabs`

**Orchestrator** — `run_task`, `run_recipe`, `list_recipes`

**Utilities** — `wait_for_selector`, `wait_for_load_state`, `configure_dialog`, `get_status`, `get_console_logs`, `get_network_requests`, `clear_network_requests`


## License

MIT License — see [LICENSE](LICENSE) for details.

## Star History

If you find WEBGhosting useful, please give it a star — it helps the project grow!

<a href="https://star-history.com/#yranjan06/WEBGhosting-MCP&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=yranjan06/WEBGhosting-MCP&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=yranjan06/WEBGhosting-MCP&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=yranjan06/WEBGhosting-MCP&type=Date" />
  </picture>
</a>

---

<p align="center">
  Built with ❤️ for the AI community<br/>
  <a href="https://github.com/yranjan06/WEBGhosting-MCP">GitHub</a> &bull;
  <a href="https://github.com/yranjan06/WEBGhosting-MCP/issues">Issues</a> &bull;
  <a href="CONTRIBUTING.md">Contribute</a>
</p>
