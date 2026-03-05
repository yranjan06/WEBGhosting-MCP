<p align="center">
  <h1 align="center">GhostMCP</h1>
  <p align="center">
    <strong>Agentic Stealth Browser &bull; Recipe Orchestrator &bull; MCP Server &bull; Built for AI Agents</strong>
  </p>
  <p align="center">
    <a href="https://github.com/yranjan06/GhostMCP/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
    <a href="https://go.dev"><img src="https://img.shields.io/badge/Go-1.26+-00ADD8?logo=go" alt="Go Version"></a>
    <a href="https://github.com/yranjan06/GhostMCP/blob/main/CONTRIBUTING.md"><img src="https://img.shields.io/badge/contributions-welcome-brightgreen.svg" alt="Contributions Welcome"></a>
    <a href="https://github.com/yranjan06/GhostMCP/issues"><img src="https://img.shields.io/github/issues/yranjan06/GhostMCP" alt="Issues"></a>
    <a href="https://github.com/yranjan06/GhostMCP/stargazers"><img src="https://img.shields.io/github/stars/yranjan06/GhostMCP?style=social" alt="Stars"></a>
  </p>
  <p align="center">
    <a href="#quick-start">Quick Start</a> &bull;
    <a href="#what-it-can-do">Features</a> &bull;
    <a href="#recipe-orchestrator">Orchestrator</a> &bull;
    <a href="#all-33-tools">Tools</a> &bull;
    <a href="CONTRIBUTING.md">Contributing</a>
  </p>
</p>

---

Most AI agents can think. Very few can actually browse.

**GhostMCP changes that.**

It is the stealthiest and most reliable MCP browser server for AI agents, built for real production use. With **33 powerful tools**, 22 anti-fingerprint scripts, LLM-powered extraction, and a **Recipe Orchestrator** that turns natural language commands into automated browser workflows — it gives AI agents a browser they can truly control.

Navigate pages. Click buttons. Fill forms. Extract structured data. Run multi-step recipes across websites. **All through natural language.**

Built in Go with a Python orchestration layer, fully compliant with the Model Context Protocol. Works seamlessly with Cursor, GitHub Copilot, Cloud Code, and any MCP-compatible client.

Built with ❤️ for the AI community. **[Contributions welcome!](CONTRIBUTING.md)**

---

## What It Can Do

| Capability | What it means for your Agent |
|---|---|
| **Recipe Orchestrator** | Give a natural language command like *"Go to HN and find the top story"* — GhostMCP auto-generates a recipe, executes it, returns data, and cleans up |
| **Pre-cached Selectors** | 55 selectors across 12 major websites (Amazon, Reddit, YouTube, GitHub, etc.) for instant, reliable DOM access |
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

## Quick Start

```bash
git clone https://github.com/yranjan06/GhostMCP.git
cd GhostMCP
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
    "ghostmcp": {
      "type": "stdio",
      "command": "/absolute/path/to/GhostMCP/webmcp",
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
    "ghostmcp": {
      "command": "/absolute/path/to/GhostMCP/webmcp",
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
docker run -p 8080:8080 -e AI_API_KEY="your-key" -e BROWSER_HEADLESS="true" ghostmcp --port=8080
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

The Recipe Orchestrator is GhostMCP's **"brain"** — it turns natural language commands into automated, multi-step browser workflows without writing any Python code.

### How It Works

```
You: "Go to HN and find top story"
  |
  v
LLM auto-generates a 3-step JSON recipe
  |
  v
Orchestrator executes each step via GhostMCP browser engine
  |
  v
Returns structured data, deletes temporary recipe
```

### Usage: Natural Language Mode

Give any browser task in plain English and the Orchestrator handles everything:

```bash
# Set your LLM provider
export AI_API_KEY="your-key"
export AI_BASE_URL="https://api.openai.com/v1"
export AI_MODEL="gpt-4o"

# Run any task in natural language
python3 -m orchestrator.orchestrator --run "Go to Hacker News and find the top story title"
python3 -m orchestrator.orchestrator --run "Search Wikipedia for GrapheneOS and read the intro"
python3 -m orchestrator.orchestrator --run "Go to Amazon and find iPhone 16 price"
```

### Usage: Pre-built Recipe Mode

For repeatable workflows, use JSON recipe files:

```bash
# List available recipes
python3 -m orchestrator.orchestrator --list

# Run a recipe
python3 -m orchestrator.orchestrator hn_reddit_linkedin.json
```

### Usage: MCP Tools (from any IDE)

AI agents in Cursor, Copilot, or Cloud Code can call orchestrator tools directly:

| MCP Tool | Description | Example Input |
|----------|-------------|---------------|
| `run_task` | Execute a task in natural language | `{"command": "Find top HN story"}` |
| `run_recipe` | Run a pre-built recipe by name | `{"name": "hn_reddit_linkedin.json"}` |
| `list_recipes` | Show all available recipes | — |

### Writing a Recipe

Recipes are declarative JSON files with sequential steps:

```json
{
  "name": "My Task",
  "steps": [
    {"id": 1, "action": "browse", "url": "https://example.com", "narrate": "Opening site..."},
    {"id": 2, "action": "wait", "state": "domcontentloaded"},
    {"id": 3, "action": "js", "code": "document.querySelector('h1').innerText", "save_as": "title", "narrate": "Reading title..."},
    {"id": 4, "action": "sleep", "seconds": 2}
  ]
}
```

**Supported actions:** `browse`, `wait`, `wait_selector`, `js`, `search`, `scroll`, `open_tab`, `switch_tab`, `type_to_notepad`, `sleep`

**Variable system:** Use `save_as` to store JS results, reference them later as `{variable.key}`.

---

## Selector Database

GhostMCP ships with **55 pre-cached CSS selectors** across **12 major websites**, stored in `orchestrator/selectors/` as per-website JSON files:

```
orchestrator/selectors/
  hackernews.json     # 5 selectors (posts, comments, scores)
  reddit.json         # 4 selectors (new + old Reddit)
  google.json         # 3 selectors (search, results)
  amazon.json         # 7 selectors (product, price, cart)
  flipkart.json       # 5 selectors (product, search)
  linkedin.json       # 4 selectors (feed, composer)
  twitter.json        # 5 selectors (tweets, compose)
  youtube.json        # 6 selectors (video, channel, comments)
  github.json         # 5 selectors (repo, stars, search)
  wikipedia.json      # 4 selectors (article, infobox)
  stackoverflow.json  # 4 selectors (Q&A, answers)
  others.json         # 3 selectors (naukri, notepad)
```

**Adding a new website:** Just create a new JSON file in `selectors/` — the orchestrator auto-merges all files at startup.

```json
{
  "mysite.search_box": {
    "selector": "#search-input",
    "fallback": "input[type='search']"
  },
  "mysite.first_result": {
    "selector": ".result-item:first-of-type a",
    "extract": ["innerText", "href"]
  }
}
```

---

## Environment Variables

- `AI_API_KEY` (required) — API key for your LLM provider
- `AI_BASE_URL` — custom endpoint URL (default: OpenAI)
- `AI_MODEL` — model name (default: `gpt-4o`)
- `EXTRACTION_MODEL` — separate faster model for data extraction
- `BROWSER_HEADLESS` — set `true` for headless mode
- `BROWSER_USER_DATA_DIR` — persist cookies/sessions across restarts
- `HTTP_PROXY` — proxy server URL

Works with any OpenAI-compatible provider:
```bash
# Groq (free)
export AI_API_KEY="gsk_..." AI_BASE_URL="https://api.groq.com/openai/v1" AI_MODEL="llama-3.1-8b-instant"

# Ollama (local)
export AI_API_KEY="ollama" AI_BASE_URL="http://localhost:11434/v1" AI_MODEL="llama3.1"

# NVIDIA NIM
export AI_API_KEY="nvapi-..." AI_BASE_URL="https://integrate.api.nvidia.com/v1" AI_MODEL="meta/llama3-70b-instruct"
```

## All 33 Tools

**Navigation** — `browse`, `go_back`, `go_forward`

**AI Interaction** — `click`, `type`, `press_key`, `fill_form`, `scroll`, `scroll_to_bottom`

**Data Extraction** — `extract`, `parallel_extract`, `execute_js`, `get_accessibility_tree`, `get_page_context`

**Vision** — `screenshot`, `capture_labeled_snapshot`

**Memory** — `memorize_data`, `recall_data`, `list_memory_keys`

**Multi-Tab** — `open_tab`, `switch_tab`, `close_tab`, `list_tabs`

**Orchestrator** — `run_task`, `run_recipe`, `list_recipes`

**Utilities** — `wait_for_selector`, `wait_for_load_state`, `configure_dialog`, `get_status`, `get_console_logs`, `get_network_requests`, `clear_network_requests`

## Architecture

```
orchestrator/             # Recipe Orchestrator (Python)
  orchestrator.py         # Core engine: recipe execution + LLM recipe generation
  selectors/              # Per-website selector files (55 selectors, 12 sites)
  recipes/                # Pre-built JSON recipe files

cmd/server/               # MCP Server (Go)
  main.go                 # Server entry point, banner, transport setup
  tools.go                # All 33 MCP tool registrations

pkg/                      # Core Go packages
  browser/                # Playwright engine with stealth hardening
  agent/                  # LLM-powered element finding + data extraction

examples/                 # Python demo scripts
  client.py               # GhostMCPClient — Python wrapper for MCP
  e2e_voice_demo.py       # Cinematic demo: HN -> Reddit -> LinkedIn
```

## License

MIT License — see [LICENSE](LICENSE) for details.

## Star History

If you find GhostMCP useful, please give it a star — it helps the project grow!

<a href="https://star-history.com/#yranjan06/GhostMCP&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=yranjan06/GhostMCP&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=yranjan06/GhostMCP&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=yranjan06/GhostMCP&type=Date" />
  </picture>
</a>

---

<p align="center">
  Built with ❤️ for the AI community<br/>
  <a href="https://github.com/yranjan06/GhostMCP">GitHub</a> &bull;
  <a href="https://github.com/yranjan06/GhostMCP/issues">Issues</a> &bull;
  <a href="CONTRIBUTING.md">Contribute</a>
</p>
