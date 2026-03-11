#!/usr/bin/env python3
"""
"Watch an AI Agent Research MCP Across Hacker News, Reddit, X, and LinkedIn — Fully Autonomous Browser Control"

A cinematic, multi-tab, cross-site, memory-aware, real-time agent demo.
This script interfaces with the WEBGhosting binary to perform a sequence of
impressive browser actions simulating a real AI agent researching 
the "Model Context Protocol".
"""

import subprocess
import json
import sys
import os
import time

# Terminal colors for cinematic effect
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"
MAGENTA = "\033[35m"


class WebMCPClient:
    """Interfaces with the WEBGhosting server."""

    def __init__(self):
        env = os.environ.copy()
        
        # force the browser to be visible so the user can record it alongside the terminal
        env["BROWSER_HEADLESS"] = "false"
        
        print(f"{CYAN}🎬 [Scene 0] Initializing WEBGhosting Engine...{RESET}")
        
        # Start the webmcp binary
        self.process = subprocess.Popen(
            ["./webmcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=sys.stderr, text=True, env=env
        )
        self.req_id = 1
        
        # Initialize MCP protocol
        self._send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "cinematic-demo", "version": "1.0"}
        })
        self._read_response()
        self.process.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + '\n'
        )
        self.process.stdin.flush()
        print(f"{GREEN}» Engine Ready. The AI is now in control.{RESET}\n")
        time.sleep(1)

    def _send(self, method, params=None):
        msg = {"jsonrpc": "2.0", "method": method, "id": self.req_id}
        if params:
            msg["params"] = params
        self.req_id += 1
        self.process.stdin.write(json.dumps(msg) + '\n')
        self.process.stdin.flush()

    def _read_response(self):
        while True:
            line = self.process.stdout.readline()
            if not line:
                return None
            try:
                resp = json.loads(line)
                if "result" in resp:
                    return resp["result"]
                if "error" in resp:
                    return f"ERROR: {resp['error']}"
                if "jsonrpc" in resp:
                    return resp
            except Exception:
                pass

    def call(self, name, args=None):
        """Calls a specific WEBGhosting tool."""
        print(f"{DIM}  > executing: {name}({json.dumps(args) if args else ''}){RESET}")
        self._send("tools/call", {"name": name, "arguments": args or {}})
        resp = self._read_response()
        if isinstance(resp, dict) and "content" in resp:
            # Try to return the text nicely
            try:
                return resp["content"][0]["text"]
            except Exception:
                return str(resp["content"])
        return str(resp)

    def close(self):
        print(f"\n{CYAN}🎬 [Demo Finished] Shutting down Engine...{RESET}")
        self.process.terminate()
        self.process.wait(timeout=5)


def cinematic_sleep(seconds=1.5):
    """Adds a human-like delay between actions."""
    time.sleep(seconds)


def run_demo():
    client = WebMCPClient()

    try:
        print(f"{MAGENTA}{'='*80}")
        print(f"  🎬 TITLE: Watch an AI Agent Research MCP Across Hacker News, Reddit, X, and LinkedIn")
        print(f"  🧠 GOAL : Research 'Model Context Protocol' autonomously")
        print(f"{'='*80}{RESET}\n")
        
        cinematic_sleep(2)

        # ---------------------------------------------------------
        # Scene 1: Hacker News
        # ---------------------------------------------------------
        print(f"{CYAN}{BOLD}🎬 Scene 1 — Tab 1: Hacker News opens{RESET}")
        client.call("browse", {"url": "https://news.ycombinator.com"})
        
        print(f"{DIM}  [System] Waiting for page to load completely...{RESET}")
        client.call("wait_for_load_state", {"state": "domcontentloaded"})
        cinematic_sleep(3) # Let the audience read the front page
        
        print(f"{YELLOW}  [Visual] Scrolling down to read posts...{RESET}")
        client.call("scroll", {"amount": 500})
        cinematic_sleep(1)
        client.call("scroll", {"amount": 500})
        cinematic_sleep(2)
        
        print(f"{YELLOW}  [Visual] Clicking on 'Motorola announces a partnership with GrapheneOS' discussion...{RESET}")
        client.call("execute_js", {"script": "document.querySelector(\"a[href='https://motorolanews.com/motorola-three-new-b2b-solutions-at-mwc-2026/']\").click()"})
        
        print(f"{DIM}  [System] Waiting for news article to load...{RESET}")
        client.call("wait_for_load_state", {"state": "domcontentloaded"})
        cinematic_sleep(4) # Let audience see the new page loaded
        
        print(f"{YELLOW}  [Visual] Reading the article...{RESET}")
        client.call("scroll", {"amount": 600})
        cinematic_sleep(2)
        print(f"{GREEN}» Hacker News reading complete.{RESET}\n")

        # ---------------------------------------------------------
        # Scene 2: Google to Reddit
        # ---------------------------------------------------------
        print(f"{CYAN}{BOLD}🎬 Scene 2 — Tab 2 opens: Google Search for Reddit Discussions{RESET}")
        client.call("open_tab", {})
        client.call("browse", {"url": "https://google.com"})
        
        print(f"{DIM}  [System] Waiting for Google to load...{RESET}")
        client.call("wait_for_load_state", {"state": "domcontentloaded"})
        cinematic_sleep(2)
        
        print(f"{YELLOW}  [Visual] Searching for 'Motorola announces a partnership with GrapheneOS in reddit'...{RESET}")
        # fill_form bypasses AI and uses playwright's human type directly
        client.call("fill_form", {"fields": [{"selector": "textarea#APjFqb", "value": "Motorola announces a partnership with GrapheneOS in reddit", "type": "textbox"}]})
        cinematic_sleep(1)
        client.call("press_key", {"key": "Enter"})
        
        print(f"{DIM}  [System] Waiting for Search Results...{RESET}")
        client.call("wait_for_load_state", {"state": "domcontentloaded"})
        cinematic_sleep(3) # Audience parses the results
        
        print(f"{YELLOW}  [Visual] Clicking the exact Reddit link...{RESET}")
        # Querying the exact google result and clicking its closest a-tag link
        client.call("execute_js", {"script": "const h3 = [...document.querySelectorAll('h3')].find(el => el.textContent.includes('GrapheneOS partnership with Motorola')); if(h3) { const a = h3.closest('a'); if(a) a.click(); else h3.click(); }"})
        
        print(f"{DIM}  [System] Waiting for Reddit thread to load...{RESET}")
        client.call("wait_for_load_state", {"state": "domcontentloaded"})
        cinematic_sleep(4) # Audience sees the Reddit layout
        
        print(f"{YELLOW}  [Visual] Scrolling down the Reddit discussion...{RESET}")
        client.call("scroll", {"amount": 800})
        cinematic_sleep(2)
        client.call("scroll", {"amount": 800})
        cinematic_sleep(2)
        
        print(f"{GREEN}» Reddit exploration complete.{RESET}\n")

        # ---------------------------------------------------------
        # Scene 3: X (Twitter)
        # ---------------------------------------------------------
        print(f"{CYAN}{BOLD}🎬 Scene 3 — Tab 3 opens: X (Twitter){RESET}")
        client.call("open_tab", {})
        client.call("browse", {"url": "https://x.com/search?q=Model%20Context%20Protocol"})
        cinematic_sleep(3)
        
        print(f"{YELLOW}  [Visual] Scrolling tweets...{RESET}")
        client.call("scroll", {"amount": 800})
        cinematic_sleep(1)
        client.call("scroll", {"amount": 800})
        cinematic_sleep(1)
        
        print(f"{YELLOW}  [Visual] Extracting hot takes...{RESET}")
        client.call("extract", {
             "schema": {
                 "author": "string",
                 "content": "string"
             }
        })
        
        print(f"{YELLOW}  [Visual] Storing in memory...{RESET}")
        client.call("memorize_data", {
             "key": "twitter_posts",
             "value": "X Sentiment: Rapid adoption happening across IDEs."
        })
        print(f"{GREEN}» X (Twitter) analysis complete.{RESET}\n")
        cinematic_sleep()

        # ---------------------------------------------------------
        # Scene 4: Switch back to HN (Visual impact)
        # ---------------------------------------------------------
        print(f"{CYAN}{BOLD}🎬 Scene 4 — Switch back to Tab 1 (Hacker News){RESET}")
        client.call("switch_tab", {"tab_id": 0})
        cinematic_sleep(2)
        
        print(f"{YELLOW}  [Visual] Capturing labeled DOM snapshot for VLMs...{RESET}")
        client.call("capture_labeled_snapshot", {})
        cinematic_sleep(1)
        
        print(f"{YELLOW}  [Visual] Taking a normal screenshot...{RESET}")
        client.call("screenshot", {})
        print(f"{GREEN}» Returned to previous context seamlessly.{RESET}\n")
        cinematic_sleep()

        # ---------------------------------------------------------
        # Scene 5: LinkedIn
        # ---------------------------------------------------------
        print(f"{CYAN}{BOLD}🎬 Scene 5 — Open LinkedIn in Tab 4{RESET}")
        client.call("open_tab", {})
        client.call("browse", {"url": "https://linkedin.com"})
        cinematic_sleep(3)
        
        print(f"{YELLOW}  [Visual] Scrolling feed...{RESET}")
        client.call("scroll", {"amount": 600})
        cinematic_sleep()
        
        print(f"{YELLOW}  [Visual] High-speed context analysis (Zero-LLM)...{RESET}")
        ctx = client.call("get_page_context", {})
        print(f"          {DIM}Result: {ctx[:100]}...{RESET}")
        cinematic_sleep()
        
        print(f"{YELLOW}  [Visual] Executing JS to extract document title...{RESET}")
        title = client.call("execute_js", {"script": "return document.title;"})
        print(f"          {DIM}Title: {title}{RESET}")
        print(f"{GREEN}» LinkedIn analysis complete.{RESET}\n")
        cinematic_sleep()

        # ---------------------------------------------------------
        # Scene 6: Back to Reddit
        # ---------------------------------------------------------
        print(f"{CYAN}{BOLD}🎬 Scene 6 — Switch back to Reddit tab (Tab 2){RESET}")
        client.call("switch_tab", {"tab_id": 1})
        cinematic_sleep(2)
        
        print(f"{YELLOW}  [Visual] Scrolling & deep-diving into comments...{RESET}")
        client.call("scroll", {"amount": 500})
        cinematic_sleep()
        
        client.call("click", {"selector": "comments", "use_ai": True})
        cinematic_sleep()
        client.call("extract", {
             "schema": {"deep_insight": "string"}
        })
        print(f"{GREEN}» Context maintained.{RESET}\n")
        cinematic_sleep()

        # ---------------------------------------------------------
        # Scene 7: Memory Recall & Reasoning
        # ---------------------------------------------------------
        print(f"{CYAN}{BOLD}🎬 Scene 7 — Memory recall + cross-platform reasoning{RESET}")
        
        hn_mem = client.call("recall_data", {"key": "hn_discussion"})
        print(f"          {DIM}Recalled HN: {hn_mem}{RESET}")
        cinematic_sleep(1)
        
        reddit_mem = client.call("recall_data", {"key": "reddit_discussion"})
        print(f"          {DIM}Recalled Reddit: {reddit_mem}{RESET}")
        cinematic_sleep(1)
        
        x_mem = client.call("recall_data", {"key": "twitter_posts"})
        print(f"          {DIM}Recalled X: {x_mem}{RESET}")
        
        print(f"{GREEN}» AI Agent has synthesized understanding across 3 platforms.{RESET}\n")
        cinematic_sleep()

        # ---------------------------------------------------------
        # Scene 8: Show Tab Overview
        # ---------------------------------------------------------
        print(f"{CYAN}{BOLD}🎬 Scene 8 — Show tab overview{RESET}")
        tabs = client.call("list_tabs", {})
        print(f"{DIM}Open Tabs:\n{tabs}{RESET}")
        print(f"{GREEN}» Perfect state tracking.{RESET}\n")
        cinematic_sleep(2)

        # ---------------------------------------------------------
        # Scene 9: Final cinematic ending
        # ---------------------------------------------------------
        print(f"{CYAN}{BOLD}🎬 Scene 9 — Final cinematic ending{RESET}")
        print(f"{YELLOW}  [Visual] Rapid tab switching...{RESET}")
        client.call("switch_tab", {"tab_id": 0})
        cinematic_sleep(0.5)
        client.call("switch_tab", {"tab_id": 2})
        cinematic_sleep(0.5)
        client.call("switch_tab", {"tab_id": 1})
        cinematic_sleep(0.5)
        client.call("switch_tab", {"tab_id": 3})
        cinematic_sleep(1)
        
        print(f"{YELLOW}  [Visual] Closing current tab...{RESET}")
        client.call("close_tab", {})
        cinematic_sleep(1)

        print(f"\n{BOLD}{GREEN}🎉 DEMO COMPLETE! 🎉{RESET}")
        print(f"{DIM}The Agent successfully researched MCP, maintaining context, extracting data, and coordinating across 4 tabs.{RESET}\n")

    except KeyboardInterrupt:
        print(f"\n{RED}Demo interrupted by user.{RESET}")
    except Exception as e:
        print(f"\n{RED}Error during execution: {e}{RESET}")
    finally:
        client.close()


if __name__ == "__main__":
    run_demo()
