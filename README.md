<p align="center">
  <h1 align="center">GhostMCP</h1>
  <p align="center">
    <strong>Intelligent Stealth Browser &bull; MCP Server &bull; Built for AI Agents</strong>
  </p>
  <p align="center">
    <a href="https://github.com/yranjan06/GhostMCP/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
    <a href="https://go.dev"><img src="https://img.shields.io/badge/Go-1.26+-00ADD8?logo=go" alt="Go Version"></a>
    <a href="https://github.com/yranjan06/GhostMCP/blob/main/CONTRIBUTING.md"><img src="https://img.shields.io/badge/contributions-welcome-brightgreen.svg" alt="Contributions Welcome"></a>
    <a href="https://github.com/yranjan06/GhostMCP/issues"><img src="https://img.shields.io/github/issues/yranjan06/GhostMCP" alt="Issues"></a>
    <a href="https://github.com/yranjan06/GhostMCP/stargazers"><img src="https://img.shields.io/github/stars/yranjan06/GhostMCP?style=social" alt="Stars"></a>
  </p>
  <p align="center">
    <a href="#quick-start">Quick Start</a> •
    <a href="#what-it-can-do">Features</a> •
    <a href="#all-30-tools">Tools</a> •
    <a href="CONTRIBUTING.md">Contributing</a>
  </p>
</p>

---

## Demo

<!-- TODO: Add demo video/GIF here -->
> Coming soon — a 60-second video showing GhostMCP in action with Cursor.

---

Most AI agents can think. Very few can actually browse.

**GhostMCP changes that.**

It is the stealthiest and most reliable MCP browser server for AI agents, built for real production use. With 30 powerful tools, 22 anti-fingerprint scripts, and LLM-powered extraction, it gives AI agents a browser they can truly control.

Navigate pages. Click buttons. Fill forms. Extract structured data. All through natural language.

Built in Go and fully compliant with the Model Context Protocol, GhostMCP works seamlessly with LLMs, AI agents, and IDEs like Cursor, with zero setup friction.



Built with ❤️ for the AI community. **[Contributions welcome!](CONTRIBUTING.md)**

## What It Can Do

| Capability | What it means for your Agent |
|---|---|
| **LLM-Powered Navigation** | Tell it `click("Login button")` or `type("Search box", "AI")` and it figures out the DOM |
| **Stealth Hardening** | 22 fingerprint patches (Bézier mouse, typing cadence, WebGL noise) to bypass bot protection |
| **Map-Reduce Extraction** | Splits massive 300K+ char pages into chunks, runs parallel LLM extraction, stitches JSON |
| **Page Context Analysis** | Zero-LLM instant analyzer that detects page type, features, and interactive elements |
| **Vision System** | Gets labeled screenshots with bounding boxes mapped directly to DOM elements for VLMs |
| **Plugin System** | Drop JSON+JS into `extensions/` and it auto-registers as a new native MCP tool |
| **Memory Store** | Key-value storage between tool calls for complex, multi-step agent workflows |
| **Parallel Extraction** | Extract structured data from multiple URLs simultaneously using isolated browser contexts |
| **Adaptive Rate Limiting** | Auto-reduces concurrency on HTTP 429 errors, recovers automatically after success streaks |
| **Universal LLM Support** | Works seamlessly with OpenAI, Groq, Ollama, Together, NVIDIA NIM, and LM Studio |
| **Docker Ready** | Single-command containerized deployment for headless scraping at scale |

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
```

## All 30 Tools

**Navigation** — `browse`, `go_back`, `go_forward`

**AI Interaction** — `click`, `type`, `press_key`, `fill_form`, `scroll`, `scroll_to_bottom`

**Data Extraction** — `extract`, `parallel_extract`, `execute_js`, `get_accessibility_tree`, `get_page_context`

**Vision** — `screenshot`, `capture_labeled_snapshot`

**Memory** — `memorize_data`, `recall_data`, `list_memory_keys`

**Multi-Tab** — `open_tab`, `switch_tab`, `close_tab`, `list_tabs`

**Utilities** — `wait_for_selector`, `wait_for_load_state`, `configure_dialog`, `get_status`, `get_console_logs`, `get_network_requests`, `clear_network_requests`



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
  <a href="https://github.com/yranjan06/GhostMCP">GitHub</a> •
  <a href="https://github.com/yranjan06/GhostMCP/issues">Issues</a> •
  <a href="CONTRIBUTING.md">Contribute</a>
</p>
