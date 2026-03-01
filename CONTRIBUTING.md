# Contributing to Go-WebMCP

First off — **thank you** for considering contributing! Go-WebMCP is built for the AI community, and every contribution makes it better for everyone.

## Table of Contents

- [Ways to Contribute](#ways-to-contribute)
- [Getting Started](#getting-started)
- [Adding Stealth Scripts](#-adding-stealth-scripts)
- [Adding MCP Tools](#-adding-mcp-tools)
- [Creating Plugins](#-creating-plugins)
- [Improving Page Detection](#-improving-page-detection)
- [Adding Examples](#-adding-example-scripts)
- [Code Style](#code-style)
- [Pull Request Process](#pull-request-process)

## Ways to Contribute

| Level | What | Difficulty |
|---|---|---|
| **Easy** | Fix typos, improve docs, add examples | Beginner friendly |
| **Medium** | Add stealth scripts, create plugins, improve page detection | Some Go/JS knowledge |
| **Advanced** | Add MCP tools, improve extraction pipeline, new browser features | Go + Playwright experience |

## Getting Started

```bash
# 1. Fork the repo on GitHub

# 2. Clone your fork
git clone https://github.com/YOUR-USERNAME/GO-WebMcp.git
cd GO-WebMcp

# 3. Install dependencies
make install-deps

# 4. Build
make build

# 5. Run tests
python3 examples/test_page_context.py  # No API key needed!

# 6. Create your branch
git checkout -b feature/my-feature
```

## Adding Stealth Scripts

**One of the easiest ways to contribute!** Each script patches a browser fingerprint signal.

### Steps

1. **Create your JS file** in `pkg/stealth/js/your_script.js`:
   ```javascript
   // Example: Spoof battery API
   if (navigator.getBattery) {
     const originalGetBattery = navigator.getBattery;
     navigator.getBattery = () => originalGetBattery.call(navigator).then(battery => {
       Object.defineProperty(battery, 'level', { get: () => 0.75 + Math.random() * 0.2 });
       return battery;
     });
   }
   ```

2. **Add a toggle** in `pkg/stealth/stealth.go`:
   ```go
   // In StealthConfig struct:
   AddBatterySpoof bool

   // In DefaultConfig():
   AddBatterySpoof: true,

   // In generateScripts() scriptMap:
   c.AddBatterySpoof: "js/battery.spoof.js",
   ```

3. **Build and test**: `make build` — the file is auto-embedded via `//go:embed js/*.js`

### Existing Scripts (22)

Before adding, check if it already exists: `navigator.webdriver`, `chrome.app`, `chrome.csi`, `chrome.runtime`, `iframe.contentWindow`, `media.codecs`, `navigator.hardwareConcurrency`, `navigator.languages`, `navigator.permissions`, `navigator.plugins`, `navigator.userAgent`, `navigator.vendor`, `canvas.noise`, `webgl.vendor`, `webgl.noise`, `fonts.spoof`, `permissions.spoof`, `window.outerdimensions`, `chrome.loadTimes`.

### Ideas for New Scripts

- Battery API spoofing
- Bluetooth API detection bypass
- Screen orientation emulation
- AudioContext fingerprint noise
- Performance API timing noise

## Adding MCP Tools

### Steps

1. **Define your args struct** in `cmd/server/tools.go`:
   ```go
   type MyToolArgs struct {
       Param string `json:"param" jsonschema:"required,description=What this param does"`
       Optional string `json:"optional,omitempty" jsonschema:"description=Optional param"`
   }
   ```

2. **Register the handler** inside `RegisterAllTools()`:
   ```go
   must(server.RegisterTool("my_tool", "What this tool does — keep it clear for the LLM", func(args MyToolArgs) (*mcp_golang.ToolResponse, error) {
       log.Printf("%s[MY_TOOL]%s Processing: %s", ColorBlue, ColorReset, args.Param)

       // Your logic here — use engine, aiAgent, or stateStore
       result := "done"

       engine.SetLastAction("my_tool: " + args.Param)
       return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(result)), nil
   }))
   ```

3. **Tool Description Tips:**
   - Be specific — LLM agents read this to decide when to use the tool
   - Include parameter hints — "Pass a CSS selector or natural language description"
   - Mention when **not** to use it — "Use `extract` instead for structured data"

### Available Dependencies

| Object | What You Can Use |
|---|---|
| `engine` | `.Navigate()`, `.ClickElement()`, `.TypeText()`, `.ExecuteScript()`, `.activePage()` |
| `aiAgent` | `.PerceiveElement()`, `.ExtractData()`, `.ParallelExtract()` |
| `stateStore` | `.Store()`, `.Retrieve()`, `.Delete()`, `.ListKeys()` |

## Creating Plugins

Plugins are the **easiest way to add tools** without touching Go code.

### Steps

1. **Create `extensions/my_tool.json`:**
   ```json
   {
     "name": "count_links",
     "description": "Count all links on the current page",
     "script_file": "count_links.js"
   }
   ```

2. **Create `extensions/count_links.js`:**
   ```javascript
   (args) => {
       const links = document.querySelectorAll('a[href]');
       return JSON.stringify({
           count: links.length,
           external: Array.from(links).filter(a => !a.href.includes(location.hostname)).length,
           internal: Array.from(links).filter(a => a.href.includes(location.hostname)).length
       });
   }
   ```

3. **Restart the server** — the tool is auto-registered!

### Plugin Limitations

- Plugins run JavaScript in the page context only
- No direct access to Go APIs (use MCP tools for that)
- Arguments are passed as a JSON object to the function

## Improving Page Detection

The `get_page_context` tool uses pure JavaScript to detect page types. Help us improve accuracy!

### How to Help

1. **Run the detection test:**
   ```bash
   python3 examples/test_page_context.py
   ```

2. **Test your site:**
   Add your site to the `SITES` list in `test_page_context.py` and run again

3. **Fix misdetections:**
   Edit the JS analysis in `pkg/browser/engine.go` → `GetPageContext()` method

### Current Page Types

`search_results`, `product_page`, `login_page`, `article`, `social_feed`, `video_platform`, `code_repository`, `qa_page`, `listing_page`, `review_page`, `form_page`, `general`, `blank`

## Adding Example Scripts

All examples live in `examples/` and use the shared `client.py`.

### Template

```python
#!/usr/bin/env python3
"""
Go-WebMCP — My Example
========================
Description of what this script demonstrates.
"""

import sys, time, json
sys.path.insert(0, '.')
from examples.client import *

client = GoWebMCPClient()

try:
    # Navigate
    client.call("browse", {"url": "https://example.com"})

    # Analyze
    context = client.call("get_page_context", {})
    print(json.loads(context))

    # Extract
    data = client.call("extract", {"schema": {
        "type": "array",
        "items": {"type": "object", "properties": {
            "title": {"type": "string"},
        }},
        "description": "Extract items"
    }})
    print(data)
finally:
    client.close()
```

## Code Style

- Follow standard Go conventions (`gofmt`, `go vet`)
- Add comments for all exported functions
- Keep functions focused — one responsibility per function
- Use meaningful variable names
- **Tool descriptions must be LLM-friendly** — agents read them to decide what to call

## Pull Request Process

1. **Fork → Branch → Code → Test → PR**
2. Ensure `make build` passes with zero errors
3. Update docs if you changed behavior
4. Add your example to `examples/README.md` if applicable
5. Keep PRs focused — one feature/fix per PR
6. Describe what changed and why in the PR description

### Commit Message Format

```
type: short description

Longer explanation if needed.
What changed and why.
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

## Report Bugs

[Open an issue](https://github.com/yranjan06/GO-WebMcp/issues) with:
- Go version (`go version`)
- OS and architecture
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs (stderr output)

## Suggest Features

[Open an issue](https://github.com/yranjan06/GO-WebMcp/issues) with the `enhancement` label:
- The use case you're solving
- Proposed behavior
- Alternatives you've considered

## License

By contributing, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).

---

**Thank you for making Go-WebMCP better!** 
