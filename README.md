<p align="center">
  <h1 align="center">Go-WebMCP</h1>
  <p align="center">
    <strong>Intelligent Stealth Browser &bull; MCP Server &bull; Built for AI Agents</strong>
  </p>
  <p align="center">
    <a href="https://github.com/yranjan06/GO-WebMcp/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
    <a href="https://go.dev"><img src="https://img.shields.io/badge/Go-1.26+-00ADD8?logo=go" alt="Go Version"></a>
    <a href="https://github.com/yranjan06/GO-WebMcp/blob/main/CONTRIBUTING.md"><img src="https://img.shields.io/badge/contributions-welcome-brightgreen.svg" alt="Contributions Welcome"></a>
    <a href="https://github.com/yranjan06/GO-WebMcp/issues"><img src="https://img.shields.io/github/issues/yranjan06/GO-WebMcp" alt="Issues"></a>
    <a href="https://github.com/yranjan06/GO-WebMcp/stargazers"><img src="https://img.shields.io/github/stars/yranjan06/GO-WebMcp?style=social" alt="Stars"></a>
  </p>
  <p align="center">
    <a href="#quick-start">Quick Start</a> •
    <a href="#what-it-can-do">Features</a> •
    <a href="#all-30-tools">Tools</a> •
    <a href="CONTRIBUTING.md">Contributing</a>
  </p>
</p>

---

**The stealthiest, most reliable MCP browser server for AI agents.** 30 tools. 22 anti-fingerprint scripts. LLM-powered extraction. Zero IDE setup hassle.

Go-WebMCP is a production-ready **Model Context Protocol (MCP)** server built in Go. It gives LLMs, AI agents, and IDEs like Cursor a **stealth browser** they can control — navigate pages, click buttons, fill forms, extract data, and more — all through natural language.

> **30 MCP tools** · **22 stealth scripts** · **Zero-config IDE integration** · **Plugin system** · **Works with any LLM**

Built with ❤️ for the AI community. **[Contributions welcome!](CONTRIBUTING.md)**

## What It Can Do

- **LLM-Powered Navigation** — tell it `click("Login button")` or `type("Search box", "AI tools")` and it figures out the rest
- **Stealth Hardening** — 22 fingerprint patches: Bézier mouse curves, human typing cadence, WebGL/Canvas noise, font spoofing
- **Map-Reduce Extraction** — splits massive pages (300K+ chars) into chunks, runs parallel LLM extraction, stitches validated JSON
- **Page Context Analysis** — zero-LLM page analyzer that detects page type, features, and interactive elements instantly
- **Vision System** — labeled screenshots with bounding boxes for Vision-Language Models
- **Plugin System** — drop JSON+JS into `extensions/` and it auto-registers as a new MCP tool
- **Memory Store** — key-value storage between tool calls for multi-step agent workflows
- **Parallel Extraction** — extract data from multiple URLs at once using isolated browser contexts
- **Adaptive Rate Limiting** — auto-reduces concurrency on 429 errors, recovers after success streaks
- **Universal LLM Support** — works with OpenAI, Groq, Ollama, Together, NVIDIA NIM, LM Studio — anything OpenAI-compatible
- **Docker Ready** — single command containerized deployment for headless scraping at scale

## Quick Start

```bash
git clone https://github.com/yranjan06/GO-WebMcp.git
cd GO-WebMcp
make install-deps
make build
```

Add to your IDE's MCP config (`mcp.json`):

```json
{
  "mcpServers": {
    "go-webmcp": {
      "command": "/absolute/path/to/webmcp",
      "env": {
        "AI_API_KEY": "your-api-key",
        "AI_MODEL": "gpt-4o"
      }
    }
  }
}
```

Or run with Docker:

```bash
make docker
docker run -p 8080:8080 -e AI_API_KEY="your-key" -e BROWSER_HEADLESS="true" go-webmcp --port=8080
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

## Demo

<!-- TODO: Add demo video/GIF here -->
> Coming soon — a 60-second video showing Go-WebMCP in action with Cursor.

## License

MIT License — see [LICENSE](LICENSE) for details.

## Star History

If you find Go-WebMCP useful, please give it a star — it helps the project grow!

<a href="https://star-history.com/#yranjan06/GO-WebMcp&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=yranjan06/GO-WebMcp&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=yranjan06/GO-WebMcp&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=yranjan06/GO-WebMcp&type=Date" />
  </picture>
</a>

---

<p align="center">
  Built with ❤️ for the AI community<br/>
  <a href="https://github.com/yranjan06/GO-WebMcp">GitHub</a> •
  <a href="https://github.com/yranjan06/GO-WebMcp/issues">Issues</a> •
  <a href="CONTRIBUTING.md">Contribute</a>
</p>
