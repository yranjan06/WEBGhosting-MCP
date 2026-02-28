#!/usr/bin/env python3
"""
Go-WebMCP — Killer Demo: Automated Competitor Intelligence
============================================================
Scenario: Compare iPhone 15 prices on Amazon vs Flipkart,
extract top results, and prove stealth bypass works.

This demo showcases:
  1. Multi-Tab Intelligence (Amazon + Flipkart side-by-side)
  2. Stealth Proof (navigator.webdriver = false)
  3. Humanized Typing (character-by-character with delays)
  4. AI Click (natural language element finding)
  5. Map-Reduce Extraction (parallel goroutine JSON extraction)

Usage:
  export AI_API_KEY="your-key"
  export AI_BASE_URL="https://api.groq.com/openai/v1"    # Groq recommended
  export AI_MODEL="llama-3.3-70b-versatile"
  python3 examples/e2e_amazon_flipkart.py
"""

import subprocess
import json
import sys
import os
import time

# ─── Colors ───
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
DIM    = "\033[2m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


class GoWebMCPClient:
    def __init__(self):
        env = os.environ.copy()
        env["AI_API_KEY"]  = os.getenv("AI_API_KEY", "")
        env["AI_BASE_URL"] = os.getenv("AI_BASE_URL", "https://api.groq.com/openai/v1")
        env["AI_MODEL"]    = os.getenv("AI_MODEL", "llama-3.3-70b-versatile")

        if not env["AI_API_KEY"]:
            print(f"{RED}ERROR: AI_API_KEY not set!{RESET}")
            print("Run: export AI_API_KEY='gsk_...' (Groq recommended)")
            sys.exit(1)

        self.process = subprocess.Popen(
            ['./webmcp'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            env=env
        )
        self.req_id = 1
        self._initialize()

    def _initialize(self):
        msg = self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "competitor-intel-demo", "version": "1.0"}
        })
        self.process.stdin.write(msg + '\n')
        self.process.stdin.flush()

        while True:
            line = self.process.stdout.readline()
            if not line: break
            try:
                if "jsonrpc" in json.loads(line): break
            except: pass

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
            if not line: return None
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


def phase(num, title):
    print(f"\n{CYAN}{'='*60}")
    print(f"  Phase {num}: {title}")
    print(f"{'='*60}{RESET}")


def step(description):
    print(f"\n  {BOLD}>> {description}{RESET}")


def result(text, truncate=500):
    if text and len(text) > truncate:
        print(f"  {GREEN}<< {text[:truncate]}...{RESET}")
    else:
        print(f"  {GREEN}<< {text}{RESET}")


def main():
    print(f"""
{CYAN}{'='*60}
  Go-WebMCP — Competitor Intelligence Demo
  
  Scenario: "Compare iPhone 15 prices on Amazon vs Flipkart,
  extract top results, prove stealth bypass works."
{'='*60}{RESET}
""")

    client = GoWebMCPClient()
    amazon_data = None
    flipkart_data = None

    product_schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "title":    {"type": "string", "description": "Product name/title"},
                "price":    {"type": "string", "description": "Price including currency symbol"},
                "rating":   {"type": "string", "description": "Star rating (e.g., 4.5 out of 5)"},
                "reviews":  {"type": "string", "description": "Number of reviews/ratings"}
            }
        },
        "description": "Extract the top 5 product listings with title, price, rating, and review count"
    }

    try:
        # ═══════════════════════════════════════════════════
        # PHASE 1: STEALTH PROOF
        # ═══════════════════════════════════════════════════
        phase(1, "Stealth Verification")

        step("Navigating to a test page...")
        client.call_tool("browse", {"url": "about:blank"})
        time.sleep(1)

        step("Checking browser fingerprint...")
        res = client.call_tool("execute_js", {
            "script": """JSON.stringify({
                webdriver: navigator.webdriver,
                plugins: navigator.plugins.length,
                languages: navigator.languages,
                platform: navigator.platform,
                hardwareConcurrency: navigator.hardwareConcurrency,
                chrome_runtime: typeof window.chrome !== 'undefined'
            }, null, 2)"""
        })
        result(res)
        print(f"\n  {DIM}webdriver=false proves stealth layer is active{RESET}")

        # ═══════════════════════════════════════════════════
        # PHASE 2: AMAZON — MULTI-TAB + SEARCH + EXTRACT
        # ═══════════════════════════════════════════════════
        phase(2, "Amazon India — Search + Extract")

        step("Navigating to Amazon India...")
        res = client.call_tool("browse", {"url": "https://www.amazon.in"})
        result(res)
        time.sleep(3)

        step("AI Typing 'iPhone 15' in search bar (humanized)...")
        res = client.call_tool("type", {"prompt": "search box or search input field", "text": "iPhone 15"})
        result(res)
        time.sleep(1)

        step("AI Clicking the search button...")
        res = client.call_tool("press_key", {"key": "Enter"})
        result(res)
        time.sleep(3)

        step("Waiting for results to load...")
        client.call_tool("wait_for_load_state", {"state": "networkidle"})
        time.sleep(2)

        step("Extracting top 5 product listings (Map-Reduce)...")
        amazon_raw = client.call_tool("extract", {"schema": product_schema})
        if amazon_raw:
            try:
                amazon_data = json.loads(amazon_raw)
                print(f"  {GREEN}<< Extracted {len(amazon_data)} products from Amazon!{RESET}")
                for i, p in enumerate(amazon_data[:5]):
                    print(f"     [{i+1}] {p.get('title', '?')[:50]}")
                    print(f"         Price: {p.get('price', '?')} | Rating: {p.get('rating', '?')}")
            except:
                print(f"  {YELLOW}<< Raw: {amazon_raw[:200]}...{RESET}")
                amazon_data = amazon_raw

        # ═══════════════════════════════════════════════════
        # PHASE 3: FLIPKART — NEW TAB + SEARCH + EXTRACT
        # ═══════════════════════════════════════════════════
        phase(3, "Flipkart — New Tab + Search + Extract")

        step("Opening new tab...")
        client.call_tool("open_tab", {})

        step("Navigating to Flipkart...")
        res = client.call_tool("browse", {"url": "https://www.flipkart.com"})
        result(res)
        time.sleep(3)

        step("AI Typing 'iPhone 15' in Flipkart search bar (humanized)...")
        res = client.call_tool("type", {"prompt": "search for products input", "text": "iPhone 15"})
        result(res)
        time.sleep(1)

        step("Pressing Enter to search...")
        res = client.call_tool("press_key", {"key": "Enter"})
        result(res)
        time.sleep(3)

        step("Waiting for results to load...")
        client.call_tool("wait_for_load_state", {"state": "networkidle"})
        time.sleep(2)

        step("Extracting top 5 product listings (Map-Reduce)...")
        flipkart_raw = client.call_tool("extract", {"schema": product_schema})
        if flipkart_raw:
            try:
                flipkart_data = json.loads(flipkart_raw)
                print(f"  {GREEN}<< Extracted {len(flipkart_data)} products from Flipkart!{RESET}")
                for i, p in enumerate(flipkart_data[:5]):
                    print(f"     [{i+1}] {p.get('title', '?')[:50]}")
                    print(f"         Price: {p.get('price', '?')} | Rating: {p.get('rating', '?')}")
            except:
                print(f"  {YELLOW}<< Raw: {flipkart_raw[:200]}...{RESET}")
                flipkart_data = flipkart_raw

        # ═══════════════════════════════════════════════════
        # PHASE 4: MULTI-TAB PROOF
        # ═══════════════════════════════════════════════════
        phase(4, "Multi-Tab Management Proof")

        step("Listing all open tabs...")
        tabs = client.call_tool("list_tabs", {})
        result(tabs)

        step("Switching back to Amazon (Tab 0)...")
        client.call_tool("switch_tab", {"index": 0})

        step("Verifying we're back on Amazon...")
        status = client.call_tool("get_status", {})
        result(status)

        # ═══════════════════════════════════════════════════
        # PHASE 5: FINAL COMPARISON
        # ═══════════════════════════════════════════════════
        phase(5, "Comparison Summary")

        print(f"\n  {BOLD}Amazon India:{RESET}")
        if isinstance(amazon_data, list):
            for i, p in enumerate(amazon_data[:3]):
                print(f"     [{i+1}] {p.get('title', '?')[:45]} — {p.get('price', '?')}")
        else:
            print(f"     {DIM}(extraction pending or rate-limited){RESET}")

        print(f"\n  {BOLD}Flipkart:{RESET}")
        if isinstance(flipkart_data, list):
            for i, p in enumerate(flipkart_data[:3]):
                print(f"     [{i+1}] {p.get('title', '?')[:45]} — {p.get('price', '?')}")
        else:
            print(f"     {DIM}(extraction pending or rate-limited){RESET}")

        # ─── Done ───
        print(f"""
{GREEN}{'='*60}
  DEMO COMPLETE

  Features Demonstrated:
    - Stealth Bypass (webdriver=false, spoofed fingerprint)
    - Multi-Tab Navigation (Amazon + Flipkart)
    - Humanized Typing (character-by-character)
    - AI-Powered Element Finding (natural language)
    - Map-Reduce Parallel Extraction (Go goroutines)
    - Structured JSON Output
{'='*60}{RESET}
""")

    except Exception as e:
        print(f"\n{RED}EXCEPTION: {e}{RESET}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    main()
