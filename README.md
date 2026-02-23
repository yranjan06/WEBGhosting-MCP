# GO-WebMcp

A high-performance, stealthy, and AI-powered Model Context Protocol (MCP) server for web automation. Built in Go, this server acts as a bridge between LLM agents (like Claude in VS Code/Cursor) and a Playwright-driven browser.

## Key Features

1. **Human-like Behavior Simulation**: Replaces instantaneous, robotic inputs with algorithms that mimic human interaction. Features include Bézier curve mouse movements, randomized typing delays, and natural scrolling.
2. **Stealth Mode (Evasion Tech)**: Uses embedded JavaScript evasion techniques to bypass bot detection. Spoofs Canvas fingerprinting, WebGL hashes, enumerated fonts, and Permissions API states.
3. **Advanced AI Perception**: Replaces brittle XPath lookups with local Accessibility Tree (AX Tree) snapshots sent to OpenAI. Features smart DOM cleaning, confidence scoring, and fallback mechanisms for natural language element finding.
4. **Robust Error Recovery**: Built-in exponential backoff for transient web issues. Automatically re-snapshots the DOM if elements aren't found on the first try and handles LLM timeouts gracefully.
5. **Multi-Tab Architecture**: Thread-safe management of multiple browser tabs at once. Seamlessly open, switch, and close tabs while retaining context.

## Prerequisites

1.  **Go 1.21+**
2.  **Playwright Browsers**:
    ```bash
    go run github.com/playwright-community/playwright-go/cmd/playwright@latest install --with-deps
    ```
3.  **OpenAI API Key**: Required for the AI Perception module (`click`, `type` and semantic querying).
    ```bash
    export AI_API_KEY=sk-...  # or OPENAI_API_KEY
    ```
4.  **Proxy Server (Optional)**: Required if you get IP-banned from sites (e.g., Reddit block). Use a residential proxy.
    ```bash
    export HTTP_PROXY=http://your-proxy-host.com:8080
    export PROXY_USERNAME=usr
    export PROXY_PASSWORD=pwd
    ```

## Installation

```bash
git clone https://github.com/ranjanyadav/web-mcp.git
cd web-mcp
go mod tidy
go build -o webmcp ./cmd/server
```

## Configuring IDEs (Antigravity, Cursor, Claude Desktop, VS Code)

Add the following to your MCP configuration (`mcp_config.json`, `settings.json`, or `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "go-webmcp": {
      "command": "/absolute/path/to/web-mcp/webmcp",
      "env": {
        "AI_API_KEY": "sk-your-openai-or-custom-key",
        "AI_BASE_URL": "https://api.openai.com/v1",
        "AI_MODEL": "gpt-4o",
        "HTTP_PROXY": "http://your-residential-proxy.zone:1234",
        "PROXY_USERNAME": "user",
        "PROXY_PASSWORD": "password",
        "BROWSER_HEADLESS": "true",
        "BROWSER_USER_DATA_DIR": "/absolute/path/to/save/cookies"
      }
    }
  }
}
```

*Note: All environment variables are optional. `AI_API_KEY` is only needed if you use AI-driven tools like `click` and `type`. `BROWSER_HEADLESS` runs the browser invisibly. `BROWSER_USER_DATA_DIR` keeps you logged into websites across server restarts.*

## Tools Available (16 Total)

The server exposes 16 tightly integrated tools to the LLM:

**Navigation & State**
- `browse(url)`: Navigates the active tab to a website.
- `get_url()`: Returns the current page URL.
- `wait_for_load_state(state)`: Waits for network idle or DOM load.
- `wait_for_selector(selector)`: Waits for a specific element to appear.

**Interaction (Humanized & AI-driven)**
- `click(prompt)`: AI-driven, hesitates, moves mouse via Bézier curve, and clicks based on semantic description.
- `type(prompt, text)`: AI-driven, finds input field, and types with randomized human speed (50-150ms/char).
- `scroll(direction, amount)`: Smoothly scrolls the page mimicking trackpad/mouse wheel.
- `mouse_click(selector)`: Direct CSS-based click.
- `fill_element(selector, text)`: Direct CSS-based instant fill.
- `hover(selector)`: Hovers over an element.

**Multi-Tab Management**
- `open_tab()`: Opens a new blank tab and automatically focuses it.
- `switch_tab(index)`: Switches the active context to the tab at the given 0-based index.
- `close_tab(index)`: Closes a specified tab.
- `list_tabs()`: Returns an array of all open tabs, tracking their URLs and Titles.

**Execution & Extraction**
- `execute_js(script)`: Evaluates arbitrary JavaScript in the page context.
- `execute_js_on_element(selector, script)`: Evaluates JavaScript scoped to a specific element.
- `screenshot()`: Captures a full-page or viewport screenshot encoded as base64.

## Data Flow Example

1.  **User Request**: "Go to google.com and search for kittens"
2.  **MCP Server**: LLM Calls `browse("google.com")`.
3.  **Browser Engine**: Launches Chromium, creates a tab, and injects 4 stealth JS scripts.
4.  **MCP Server**: LLM Calls `type("Search box", "kittens")`.
5.  **AI Perception**:
    -   Takes accessibility snapshot of `google.com`.
    -   Sends cleaned snapshot + "Search box" prompt to OpenAI.
    -   OpenAI returns `{"selector": "textarea[name='q']", "confidence": 0.98}`.
6.  **Browser Engine**: Moves mouse along a curved path to the input, hesitates, and types "kittens" with realistic delays.
