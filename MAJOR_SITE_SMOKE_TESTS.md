# Major Site Smoke Tests

This guide gives you high-signal prompts for validating WEBGhosting on real websites.

If you want to run a reusable suite instead of copying prompts one by one, use:

```bash
python3 examples/smoke_major_sites.py --sites hackernews,github,wikipedia
```

## Prerequisites

```bash
make build

export AI_API_KEY="your-key"
export AI_BASE_URL="https://api.openai.com/v1"
export AI_MODEL="gpt-4o"
```

Optional but useful for debugging:

```bash
export BROWSER_HEADLESS="false"
```

## Verified Smoke Test

This Hacker News flow was verified from a real terminal run on 2026-03-22:

```bash
python3 -m orchestrator.orchestrator --run "Open the Hacker News homepage. Extract the title and author of the 5th article. Then open the comments page for that same 5th article and extract the text of the first 2 comments."
```

Expected behavior:

- the orchestrator generates a recipe,
- opens Hacker News,
- extracts the article metadata,
- navigates to the matching comments thread,
- extracts the first two comments as structured results.

## Major Website Prompts

### Hacker News

```bash
python3 -m orchestrator.orchestrator --run "Open the Hacker News homepage. Extract the title and author of the 5th article. Then open the comments page for that same 5th article and extract the text of the first 2 comments."
```

### Reddit

```bash
python3 -m orchestrator.orchestrator --run "Open Reddit r/LocalLLaMA top posts for today. Extract the title of the top post, open it, and extract the first comment."
```

### GitHub

```bash
python3 -m orchestrator.orchestrator --run "Open the GitHub repository microsoft/playwright and extract the repository name, description, and star count."
```

### Wikipedia

```bash
python3 -m orchestrator.orchestrator --run "Open the Wikipedia article for Model Context Protocol and extract the article title and the first paragraph."
```

### YouTube

```bash
python3 -m orchestrator.orchestrator --run "Open YouTube search results for Model Context Protocol and extract the title and channel name of the first result."
```

### Amazon

```bash
python3 -m orchestrator.orchestrator --run "Open Amazon and find iPhone 16. Extract the title, price, and rating of the first relevant result."
```

## Prompt Design Tips

- Keep numbered references consistent. "5th article" followed by "same 4th article" is ambiguous.
- Prefer explicit destinations like "open the comments page for the same 5th article" instead of "open that one."
- If the site requires auth, give WEBGhosting a persistent profile:

```bash
export BROWSER_USER_DATA_DIR="$HOME/.webghosting-profile"
```

- If you hit login or anti-bot walls, run headed mode with `BROWSER_HEADLESS=false`.

## Troubleshooting

### Orchestrator starts but recipe generation fails

Check:

- `AI_API_KEY`
- `AI_BASE_URL`
- `AI_MODEL`

Example for NVIDIA NIM:

```bash
export AI_API_KEY="nvapi-..."
export AI_BASE_URL="https://integrate.api.nvidia.com/v1"
export AI_MODEL="meta/llama3-70b-instruct"
```

### Browser fails to launch

Install Playwright dependencies:

```bash
make install-deps
```

### Reddit thread navigation aborts with a block/interstitial error

That is expected behavior when Reddit serves a blocked page instead of the real thread. WEBGhosting now stops the recipe instead of extracting garbage from the block page.

Try:

- `BROWSER_USER_DATA_DIR` for a persistent browser profile
- `BROWSER_HEADLESS=false`
- a clean proxy via `HTTP_PROXY` or `PROXY_LIST`

### Need a fast non-LLM smoke test first

Run:

```bash
python3 examples/test_page_context.py
```

That validates browser startup and page analysis without consuming LLM tokens.
