# Go-WebMCP: Intelligent Stealth Browser MCP

Go-WebMCP is a highly scalable, production-ready **Model Context Protocol (MCP)** server built in Go. It operates as an **Intelligent Stealth Browser Automation Proxy**, allowing internal LLMs and Autonomous Agents to navigate the web, bypass anti-bot detections, and extract highly structured schema data at scale.

## Core Features
* **LLM-Powered Navigation:** Navigate the web using natural language (e.g., `click({"prompt": "Login button"})`).
* **Stealth Hardening (Humanize Mode):** Evades strict anti-bot systems (DataDome, Cloudflare) via Playwright-level Bézier curve mouse paths, random jitter, and human typing delays.
* **Map-Reduce JSON Extraction:** Solves the context-limit problem of massive Single Page Applications (SPAs). It splits 300k+ character React payloads into smart boundary chunks, processes them via heavily parallelized LLM extraction limits, and stitches them seamlessly back into validated JSON.
* **W3C WebMCP Readiness:** Automatically detects and prefers native `navigator.modelContext` endpoints if exposed by the target website to reduce inference costs.

## Quick Start

### 1. Local Binary Setup (IDE usage)
You can plug Go-WebMCP directly into AI-powered IDEs (like Cursor, Windsurf, or Claude Desktop) as a local extension.

```bash
# Clone the repository
git clone https://github.com/your-username/go-webmcp.git
cd go-webmcp

# Build the binary
go build -o webmcp cmd/server/main.go

# Install Playwright system dependencies
go run github.com/playwright-community/playwright-go/cmd/playwright@latest install --with-deps
```

**Add to IDE MCP Configuration (`mcp.json` / `settings.json`):**
```json
{
  "mcpServers": {
    "go-webmcp": {
      "command": "/absolute/path/to/webmcp",
      "env": {
        "AI_API_KEY": "sk-your-openai-or-custom-key",
        "AI_BASE_URL": "https://api.openai.com/v1",
        "AI_MODEL": "gpt-4o",
        "EXTRACTION_BASE_URL": "https://integrate.api.nvidia.com/v1",
        "EXTRACTION_MODEL": "meta/llama-3.1-8b-instruct",
        "EXTRACTION_API_KEY": "nvapi-..."
      }
    }
  }
}
```

### 2. Docker Deployment (Containerized Orchestration)
For headless parallel scraping, run Go-WebMCP within an isolated container.

```bash
# Build the Docker image
docker build -t go-webmcp .

# Run the container in HTTP/SSE mode (Exposing port 8080)
docker run -p 8080:8080 \
  -e AI_API_KEY="sk-..." \
  -e BROWSER_HEADLESS="true" \
  go-webmcp --port=8080
```

## Available Tooling (MCP Capabilities)

- **`browse`**: Navigate to a URL stealthily.
- **`click`**: Natural-language driven smart clicking.
- **`type`**: Humanized typing action on a targeted element.
- **`fill_form`**: Batch fill inputs seamlessly.
- **`scroll`** / **`scroll_to_bottom`**: Mechanically hydrate infinite feeds gracefully.
- **`execute_js`**: Run native Javascript inside the V8 engine.
- **`configure_dialog`**: Auto-manage or bypass blocking JS `alert()` overrides.
- **`extract`**: The crown jewel—feed it a `JSON Schema` and it will automatically chunk, map-reduce, and parse unstructured dirty HTML into strict JSON structures.

## Python Integration Example

When writing standalone Python agents, use stdio mode to boot up the target MCP sub-process:

```python
import subprocess
import json
import os

env = os.environ.copy()
env["AI_API_KEY"] = "sk-..."

process = subprocess.Popen(
    ['./webmcp'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
    env=env
)

# Call an MCP Server Tool easily via JSON-RPC
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
