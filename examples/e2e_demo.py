#!/usr/bin/env python3
"""
Go-WebMCP End-to-End Demo
Demonstrates: Stealth Browse, AI Click, Extraction, Multi-Tab
Target: Hacker News (lightweight, no anti-bot)
"""

import subprocess
import json
import sys
import os
import time

# Colors
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
DIM = "\033[2m"
RESET = "\033[0m"

class GoWebMCPClient:
    def __init__(self):
        env = os.environ.copy()
        env["AI_API_KEY"] = os.getenv("AI_API_KEY", "")
        env["AI_BASE_URL"] = os.getenv("AI_BASE_URL", "https://openrouter.ai/api/v1")
        env["AI_MODEL"] = os.getenv("AI_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

        if not env["AI_API_KEY"]:
            print(f"{RED}ERROR: AI_API_KEY not set!{RESET}")
            print("Run: export AI_API_KEY='sk-or-...'")
            sys.exit(1)

        self.process = subprocess.Popen(
            ['./webmcp'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,  # Let server logs flow to terminal
            text=True,
            env=env
        )
        self.req_id = 1
        self._initialize()

    def _initialize(self):
        msg = self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "e2e-demo", "version": "1.0"}
        })
        self.process.stdin.write(msg + '\n')
        self.process.stdin.flush()

        # Wait for init response
        while True:
            line = self.process.stdout.readline()
            if not line:
                break
            try:
                if "jsonrpc" in json.loads(line):
                    break
            except:
                pass

        # Send initialized notification
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + '\n')
        self.process.stdin.flush()
        print(f"{GREEN}[OK] Go-WebMCP server initialized{RESET}")

    def _rpc(self, method, params=None):
        msg = {"jsonrpc": "2.0", "method": method, "id": self.req_id}
        if params is not None:
            msg["params"] = params
        self.req_id += 1
        return json.dumps(msg)

    def call_tool(self, name, args):
        msg = self._rpc("tools/call", {"name": name, "arguments": args})
        self.process.stdin.write(msg + '\n')
        self.process.stdin.flush()

        while True:
            line = self.process.stdout.readline()
            if not line:
                return None
            try:
                resp = json.loads(line)
                if "error" in resp:
                    return f"ERROR: {resp['error']}"
                if "result" in resp:
                    return resp["result"]["content"][0]["text"]
            except json.JSONDecodeError:
                pass

    def close(self):
        self.process.terminate()
        self.process.wait(timeout=5)


def separator(phase, title):
    print(f"\n{CYAN}{'='*55}")
    print(f"  Phase {phase}: {title}")
    print(f"{'='*55}{RESET}")


def main():
    print(f"\n{CYAN}{'='*55}")
    print(f"  Go-WebMCP -- End-to-End Demo")
    print(f"  Target: Hacker News + Stealth Verification")
    print(f"{'='*55}{RESET}")

    client = GoWebMCPClient()

    try:
        # ─── Phase 1: Stealth Navigation ───
        separator(1, "Stealth Navigation")
        print(">> browse(https://news.ycombinator.com)")
        res = client.call_tool("browse", {"url": "https://news.ycombinator.com"})
        print(f"{GREEN}<< {res}{RESET}")
        time.sleep(2)

        # ─── Phase 2: Stealth Proof ───
        separator(2, "Stealth Verification")
        print(">> Checking navigator.webdriver and fingerprint...")
        res = client.call_tool("execute_js", {
            "script": "JSON.stringify({webdriver: navigator.webdriver, plugins: navigator.plugins.length, languages: navigator.languages}, null, 2)"
        })
        print(f"{GREEN}<< {res}{RESET}")

        # ─── Phase 3: Status Check ───
        separator(3, "Server Status")
        print(">> get_status()")
        res = client.call_tool("get_status", {})
        print(f"{GREEN}<< {res}{RESET}")

        # ─── Phase 4: Accessibility Tree ───
        separator(4, "Accessibility Tree Snapshot")
        print(">> get_accessibility_tree()")
        res = client.call_tool("get_accessibility_tree", {})
        if res:
            lines = res.strip().split("\n")
            print(f"{GREEN}<< {len(lines)} ARIA nodes captured. First 5:{RESET}")
            for l in lines[:5]:
                print(f"   {DIM}{l}{RESET}")

        # ─── Phase 5: AI-Powered Click ───
        separator(5, "AI Click (Natural Language)")
        print(">> click('More link at the bottom')")
        res = client.call_tool("click", {"prompt": "More link at the bottom"})
        print(f"{GREEN}<< {res}{RESET}")
        time.sleep(2)

        # ─── Phase 6: Structured Extraction ───
        separator(6, "Map-Reduce Structured Extraction")
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "points": {"type": "string"},
                    "author": {"type": "string"}
                }
            },
            "description": "Extract the title, points, and author of every story on the page"
        }
        print(f">> extract(schema=stories)")
        res = client.call_tool("extract", {"schema": schema})
        if res:
            try:
                data = json.loads(res)
                print(f"{GREEN}<< Extracted {len(data)} stories! First 3:{RESET}")
                for i, item in enumerate(data[:3]):
                    print(f"   [{i+1}] {item.get('title', '?')[:55]}")
                    print(f"       Points: {item.get('points', '?')} | Author: {item.get('author', '?')}")
            except:
                print(f"{YELLOW}<< Raw: {res[:200]}...{RESET}")

        # ─── Phase 7: Multi-Tab ───
        separator(7, "Multi-Tab Management")
        print(">> open_tab() + browse(example.com)")
        client.call_tool("open_tab", {})
        client.call_tool("browse", {"url": "https://example.com"})
        
        print(">> list_tabs()")
        res = client.call_tool("list_tabs", {})
        print(f"{GREEN}<< {res}{RESET}")

        print(">> Closing tab 1, switching back...")
        client.call_tool("close_tab", {"index": 1})

        # ─── Done ───
        print(f"\n{GREEN}{'='*55}")
        print(f"  ALL 7 PHASES COMPLETE")
        print(f"{'='*55}{RESET}\n")

    except Exception as e:
        print(f"\n{RED}EXCEPTION: {e}{RESET}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    main()
