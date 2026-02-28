# Examples

Real-world end-to-end automation scripts demonstrating Go-WebMCP capabilities.

## Scripts

| Script | Target | What it does |
|---|---|---|
| `e2e_linkedin.py` | LinkedIn | Login, navigate profile, extract connections |
| `e2e_naukri.py` | Naukri.com | Browse job listings, extract structured job data |
| `e2e_reddit.py` | Reddit | Navigate subreddits, extract posts and comments |
| `e2e_twitter.py` | Twitter/X | Login, scroll feed, extract tweets |
| `test_demo.py` | Local demo page | Verify all MCP tools work end-to-end |
| `test_tools.py` | Various | Tool-by-tool verification suite |

## Running an Example

1. Build the Go-WebMCP binary:
   ```bash
   make build
   ```

2. Set your API key:
   ```bash
   export AI_API_KEY="sk-..."
   ```

3. Run any script:
   ```bash
   python examples/e2e_reddit.py
   ```

## Demo Page

The `demo/index.html` file is a local HTML page for verifying stealth, typing, clicking, dialogs, and accessibility tree features. Open it in a browser or use `browse` to navigate to it.

## Adding Your Own

Create a new Python script that spawns the `./webmcp` binary via `subprocess` and communicates over JSON-RPC stdin/stdout. See any existing script for the pattern.
