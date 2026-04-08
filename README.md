<div align="center">
  <img src="logo.svg" alt="WEBGhosting" width="650">
</div>

---
## Demo

[![WEBGhosting Demo](https://img.youtube.com/vi/sBX8FHHPyKY/maxresdefault.jpg)](https://www.youtube.com/watch?v=sBX8FHHPyKY)

> Click the thumbnail above to watch the full demo on YouTube.

## What is WEBGhosting

The concept behind WEBGhosting is to tackle the one thing that keeps AI agents trapped in their digital boxes which is the lack of a genuine window to the world. I started with a simple question about whether an agent could navigate a complete browser just like we do, and I wanted to turn that into a reality. It is one thing to have a script that scrapes data, but it is an entirely different beast to build a system that can handle DOM perception and bypass bot detection measures while maintaining the persona of a real human. By focusing on the Model Context Protocol, I created a bridge that lets tools like Claude Code or Cursor step out of the development environment and into the live web, which is a massive leap for autonomous agents.

The way I layered the architecture was very intentional, especially with the Go-based MCP server wrapping Playwright. Building a stealth engine with twenty-two different anti-fingerprint scripts is a level of detail that most people overlook, but it is exactly what makes the difference between a bot that gets blocked immediately and an agent that actually functions. The progression from rigid cinematic demos to a fluid voice-controlled interface highlights how much I learned about where the LLM is most effective. It was fascinating landing on that three-tier execution model because it solves the latency issues that usually kill the vibe of a voice assistant. By using regex for basic tasks and only calling the LLM for the complex stuff, I managed to make the interaction feel instantaneous.

What I built with the Sarvam Voice Agent feels like that Jarvis moment I had been waiting for in tech. It is not just about the code or the thirty-four tools I integrated, but about the user experience of having a persistent browser session that just listens and acts. The move from pixel art microphones and FastAPI web interfaces to a refined orchestrator that can handle ordinal commands like clicking the third article shows a deep understanding of how humans actually want to interact with machines. This project started as a learning exercise, but it has clearly evolved into a blueprint for the future of how we will collaborate with AI in our daily browsing lives.

## Voice Assistant Wrapper

I also built a voice wrapper for this project. Start the Sarvam voice agent and speak commands like "open google", "type hacker news and search", "click the first comment", "extract the top news titles into JSON":

```bash
export SARVAM_API_KEY="your-key"
export AI_API_KEY="your-key"
export AI_BASE_URL="https://integrate.api.nvidia.com/v1"
export AI_MODEL="meta/llama3-70b-instruct"

python3 examples/sarvam_voice_agent.py
```

## The 34 Tools

Every capability is exposed as a standard MCP tool. Any compatible AI agent can call these directly.

- **Navigation:** `browse`, `go_back`, `go_forward`
- **Interaction:** `reframe_user_prompt`, `click`, `type`, `press_key`, `fill_form`, `scroll`, `scroll_to_bottom`
- **Data Extraction:** `extract`, `parallel_extract`, `execute_js`, `get_accessibility_tree`, `get_page_context`
- **Vision:** `screenshot`, `capture_labeled_snapshot`
- **Memory:** `memorize_data`, `recall_data`, `list_memory_keys`
- **Multi-Tab:** `open_tab`, `switch_tab`, `close_tab`, `list_tabs`
- **Orchestrator:** `run_task`, `run_recipe`, `list_recipes`
- **Utilities:** `wait_for_selector`, `wait_for_load_state`, `configure_dialog`, `get_status`, `get_console_logs`, `get_network_requests`, `clear_network_requests`

## How to Use It

**As an MCP server for AI agents:** add it to your IDE's MCP config and any agent (Cursor, Copilot, Claude Code) can start browsing:

```json
{
  "servers": {
    "webghosting": {
      "type": "stdio",
      "command": "/path/to/webmcp",
      "env": {
        "AI_API_KEY": "your-api-key",
        "AI_BASE_URL": "https://api.openai.com/v1",
        "AI_MODEL": "gpt-4o"
      }
    }
  }
}
```

## Environment Variables

- `AI_API_KEY` (Required): Your LLM provider API key
- `AI_BASE_URL`: Custom endpoint URL (defaults to OpenAI)
- `AI_MODEL`: Model name (defaults to gpt-4o)
- `SARVAM_API_KEY` (Voice only): Required for the speech-to-text wrapper
- `BROWSER_HEADLESS`: Set to true for headless operation
- `BROWSER_USER_DATA_DIR`: Persist cookies and sessions across restarts

*Works with any OpenAI-compatible provider including Groq, Ollama, NVIDIA NIM, Together, and LM Studio.*
## License

MIT — see [LICENSE](LICENSE).
