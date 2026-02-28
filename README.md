<p align="center">
  <h1 align="center">Go-WebMCP</h1>
  <p align="center">
    <strong>Intelligent Stealth Browser &bull; MCP Server &bull; Built for AI Agents</strong>
  </p>
  <p align="center">
    <a href="#quick-start">Quick Start</a> •
    <a href="#features">Features</a> •
    <a href="#available-tools">Tools</a> •
    <a href="#architecture">Architecture</a> •
    <a href="CONTRIBUTING.md">Contributing</a>
  </p>
</p>

---

Go-WebMCP is a production-ready **Model Context Protocol (MCP)** server built in Go. It acts as an **Intelligent Stealth Browser Proxy** — enabling LLMs, autonomous agents, and AI-powered IDEs to navigate the web, bypass anti-bot systems, and extract structured data at scale.

Built with ❤️ for the AI community.

## Features

| Feature | Description |
|---|---|
| **LLM-Powered Navigation** | Navigate using natural language — `click("Login button")`, `type("Search box", "AI tools")` |
| **Stealth Hardening** | 20+ Playwright-level fingerprint patches: Bézier mouse curves, human typing cadence, WebGL/Canvas noise |
| **Map-Reduce Extraction** | Splits massive SPAs (300K+ chars) into smart chunks, runs parallel LLM extraction, and stitches validated JSON |
| **W3C WebMCP Ready** | Auto-detects native `navigator.modelContext` endpoints to reduce inference costs |
| **Universal LLM Support** | Works with OpenAI, Ollama, Groq, Together, NVIDIA NIM, LM Studio — any OpenAI-compatible API |
| **Docker Ready** | Single-command containerized deployment for headless scraping at scale |

## Quick Start

### Option 1: Local Binary (IDE Integration)

```bash
# Clone and build
git clone https://github.com/AiAutomatrix/GO-WebMcp.git
cd GO-WebMcp
make build
make install-deps
```

**Add to your IDE's MCP config** (`mcp.json` or `settings.json`):

```json
{
  "mcpServers": {
    "go-webmcp": {
      "command": "/absolute/path/to/webmcp",
      "env": {
        "AI_API_KEY": "sk-your-key",
        "AI_MODEL": "gpt-4o"
      }
    }
  }
}
```

### Option 2: Docker (Headless Orchestration)

```bash
# Build and run
make docker
docker run -p 8080:8080 \
  -e AI_API_KEY="sk-..." \
  -e BROWSER_HEADLESS="true" \
  go-webmcp --port=8080
```

### Option 3: Docker Compose

```bash
# Set your key and run
export AI_API_KEY="sk-..."
make docker-compose
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `AI_API_KEY` | Yes | — | API key for your LLM provider |
| `AI_BASE_URL` | — | OpenAI | Custom LLM endpoint URL |
| `AI_MODEL` | — | `gpt-4o` | Model for element finding |
| `EXTRACTION_MODEL` | — | same as `AI_MODEL` | Separate model for data extraction |
| `EXTRACTION_API_KEY` | — | same as `AI_API_KEY` | Separate key for extraction model |
| `EXTRACTION_BASE_URL` | — | same as `AI_BASE_URL` | Separate endpoint for extraction |
| `BROWSER_HEADLESS` | — | `false` | Run Chromium in headless mode |
| `BROWSER_USER_DATA_DIR` | — | — | Persist cookies/sessions across restarts |
| `HTTP_PROXY` | — | — | Proxy server (e.g., `http://proxy:8080`) |
| `PROXY_USERNAME` | — | — | Proxy authentication username |
| `PROXY_PASSWORD` | — | — | Proxy authentication password |

## Available Tools

### Navigation
| Tool | Description |
|---|---|
| `browse` | Navigate to a URL with stealth mode |
| `go_back` | Browser back button |
| `go_forward` | Browser forward button |

### Interaction
| Tool | Description |
|---|---|
| `click` | Natural-language driven smart clicking |
| `type` | Humanized typing on a targeted element |
| `press_key` | Simulate keyboard key press (Enter, Tab, etc.) |
| `fill_form` | Batch fill multiple form fields |
| `scroll` | Scroll up or down with human-like behavior |
| `scroll_to_bottom` | Dynamically scroll infinite feeds to completion |

### Data Extraction
| Tool | Description |
|---|---|
| `extract` | Map-Reduce JSON extraction — feed a JSON Schema, get structured data |
| `execute_js` | Run arbitrary JavaScript in the page context |
| `get_accessibility_tree` | Get semantic ARIA snapshot of the page |
| `get_console_logs` | Retrieve browser console output |

### Multi-Tab
| Tool | Description |
|---|---|
| `open_tab` | Open a new browser tab |
| `switch_tab` | Switch to a tab by index |
| `close_tab` | Close a tab by index |
| `list_tabs` | List all open tabs with URLs and titles |

### Utilities
| Tool | Description |
|---|---|
| `wait_for_selector` | Wait for a CSS selector to appear |
| `wait_for_load_state` | Wait for page load / network idle |
| `configure_dialog` | Auto-handle browser alert/confirm dialogs |
| `get_status` | Server health check and last action report |
| `get_network_requests` | Get captured HTTP request log |
| `clear_network_requests` | Clear the request log |

## Architecture

```mermaid
graph TD
    classDef client fill:#1a1a2e,stroke:#16213e,color:#e94560
    classDef server fill:#0f3460,stroke:#533483,color:#fff
    classDef agent fill:#533483,stroke:#e94560,color:#fff
    classDef stealth fill:#e94560,stroke:#fff,color:#fff
    classDef browser fill:#16213e,stroke:#0f3460,color:#e94560

    A[AI Agent / IDE / Orchestrator] :::client -->|JSON-RPC| B(MCP Server) :::server
    B --> C{Action Router} :::server

    C -->|"click, type, extract"| D[Agentic Perception Layer] :::agent
    C -->|"browse, scroll, press_key"| E[Humanize Engine] :::stealth

    D -->|Accessibility Tree + LLM| F[Playwright / Chromium] :::browser
    E -->|"Bézier Curves + Typing Delays"| F

    F -->|Stealth JS Injection| G[Target Website] :::client

    D -->|Structured JSON| B
    B -->|Response| A
```

## Python Integration

```python
import subprocess, json, os

env = os.environ.copy()
env["AI_API_KEY"] = "sk-..."

process = subprocess.Popen(
    ['./webmcp'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
    env=env
)

# Call any MCP tool via JSON-RPC
msg = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 1,
    "params": {
        "name": "browse",
        "arguments": {"url": "https://news.ycombinator.com"}
    }
}
process.stdin.write(json.dumps(msg) + '\n')
process.stdin.flush()
```

## Extending Go-WebMCP

### Add a Stealth Script
Drop a `.js` file into `pkg/stealth/js/` → Add a toggle in `StealthConfig` → Done. It auto-embeds via `//go:embed`.

### Add an MCP Tool
Define an arg struct + handler in `cmd/server/tools.go` → It auto-registers on startup.

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guides.

## Examples

See the [`examples/`](examples/) directory for real-world automation scripts targeting LinkedIn, Reddit, Twitter, Naukri and more.

## Project Structure

```
go-webmcp/
├── cmd/server/          # MCP server entrypoint
│   ├── main.go          # Bootstrap (flags, banner, transport)
│   ├── config.go        # Version and constants
│   └── tools.go         # All MCP tool handlers
├── pkg/
│   ├── agent/           # LLM-powered perception
│   │   ├── perception.go  # Element finding via accessibility tree
│   │   ├── extract.go     # Map-Reduce structured extraction
│   │   └── cache.go       # Semantic selector cache
│   ├── browser/         # Playwright engine
│   │   ├── engine.go      # Browser lifecycle, tabs, navigation
│   │   ├── humanize.go    # Bézier mouse, typing cadence
│   │   └── retry.go       # Exponential backoff utility
│   ├── stealth/         # Anti-detection layer
│   │   ├── stealth.go     # Config and script injection
│   │   └── js/            # 22 embedded fingerprint patches
│   └── transport/sse/   # HTTP/SSE transport
├── examples/            # E2E automation scripts
├── Dockerfile
├── Makefile
└── go.mod
```

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with heart for the AI community
</p>
