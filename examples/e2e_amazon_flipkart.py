#!/usr/bin/env python3
"""
Go-WebMCP — Smart Demo: iPhone 15 Price Comparison
====================================================
Strategy: Navigate directly via search URLs (no LLM wasted on finding buttons).
          Use LLM ONLY for structured data extraction.
"""

import subprocess
import json
import sys
import os
import time

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
        env["AI_MODEL"]    = os.getenv("AI_MODEL", "llama-3.1-8b-instant")

        if not env["AI_API_KEY"]:
            print(f"{RED}ERROR: AI_API_KEY not set!{RESET}")
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
            "clientInfo": {"name": "smart-demo", "version": "1.0"}
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
        print(f"{GREEN}[OK] Server ready{RESET}")

    def _rpc(self, method, params=None):
        msg = {"jsonrpc": "2.0", "method": method, "id": self.req_id}
        if params: msg["params"] = params
        self.req_id += 1
        return json.dumps(msg)

    def call(self, name, args):
        self.process.stdin.write(self._rpc("tools/call", {"name": name, "arguments": args}) + '\n')
        self.process.stdin.flush()
        while True:
            line = self.process.stdout.readline()
            if not line: return None
            try:
                resp = json.loads(line)
                if "error" in resp: return f"ERROR: {resp['error']}"
                if "result" in resp: return resp["result"]["content"][0]["text"]
            except: pass

    def close(self):
        self.process.terminate()
        self.process.wait(timeout=5)


def phase(n, title):
    print(f"\n{CYAN}{'='*55}\n  Phase {n}: {title}\n{'='*55}{RESET}")


def main():
    print(f"\n{CYAN}{'='*55}\n  iPhone 15 — Amazon vs Flipkart\n  Smart Mode: Direct URLs + LLM Extraction Only\n{'='*55}{RESET}")

    client = GoWebMCPClient()

    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Full product name"},
                "price": {"type": "string", "description": "Price with currency"},
                "rating": {"type": "string", "description": "Star rating"},
                "reviews": {"type": "string", "description": "Number of reviews"}
            }
        },
        "description": "Extract the top 5 product listings with title, price, rating, reviews"
    }

    try:
        # ─── Phase 1: Stealth Check ───
        phase(1, "Stealth Verification")
        client.call("browse", {"url": "about:blank"})
        res = client.call("execute_js", {
            "script": "JSON.stringify({webdriver: navigator.webdriver, plugins: navigator.plugins.length, chrome: typeof chrome !== 'undefined'}, null, 2)"
        })
        print(f"  {GREEN}{res}{RESET}")

        # ─── Phase 2: Amazon (Direct URL — no LLM wasted) ───
        phase(2, "Amazon — Direct Search URL")
        print(f"  {DIM}>> browse(amazon.in/s?k=iPhone+15) — NO LLM needed!{RESET}")
        client.call("browse", {"url": "https://www.amazon.in/s?k=iPhone+15"})
        time.sleep(3)
        client.call("wait_for_load_state", {"state": "networkidle"})

        print(f"  {BOLD}>> Extracting products (LLM Map-Reduce)...{RESET}")
        amazon_raw = client.call("extract", {"schema": schema})
        amazon_data = []
        if amazon_raw:
            try:
                amazon_data = json.loads(amazon_raw)
                print(f"  {GREEN}Extracted {len(amazon_data)} products from Amazon{RESET}")
                for i, p in enumerate(amazon_data[:5]):
                    print(f"    [{i+1}] {p.get('title', 'N/A')[:55]}")
                    print(f"        {BOLD}{p.get('price', '?')}{RESET} | {p.get('rating', '?')} | {p.get('reviews', '?')} reviews")
            except:
                print(f"  {YELLOW}Raw: {amazon_raw[:300]}{RESET}")

        # ─── Phase 3: Flipkart (Direct URL — no LLM wasted) ───
        phase(3, "Flipkart — Direct Search URL (New Tab)")
        client.call("open_tab", {})
        print(f"  {DIM}>> browse(flipkart.com/search?q=iphone+15) — NO LLM needed!{RESET}")
        client.call("browse", {"url": "https://www.flipkart.com/search?q=iphone+15"})
        time.sleep(3)
        client.call("wait_for_load_state", {"state": "networkidle"})

        print(f"  {BOLD}>> Extracting products (LLM Map-Reduce)...{RESET}")
        flipkart_raw = client.call("extract", {"schema": schema})
        flipkart_data = []
        if flipkart_raw:
            try:
                flipkart_data = json.loads(flipkart_raw)
                print(f"  {GREEN}Extracted {len(flipkart_data)} products from Flipkart{RESET}")
                for i, p in enumerate(flipkart_data[:5]):
                    print(f"    [{i+1}] {p.get('title', 'N/A')[:55]}")
                    print(f"        {BOLD}{p.get('price', '?')}{RESET} | {p.get('rating', '?')} | {p.get('reviews', '?')} reviews")
            except:
                print(f"  {YELLOW}Raw: {flipkart_raw[:300]}{RESET}")

        # ─── Phase 4: Multi-Tab Proof ───
        phase(4, "Multi-Tab Proof")
        tabs = client.call("list_tabs", {})
        print(f"  {GREEN}{tabs}{RESET}")

        # ─── Phase 5: Comparison ───
        phase(5, "Best Deal Comparison")

        print(f"\n  {BOLD}{'Product':<45} {'Amazon':>12} {'Flipkart':>12}{RESET}")
        print(f"  {'─'*70}")

        # Match by rough title and compare
        a_best = amazon_data[0] if amazon_data else {}
        f_best = flipkart_data[0] if flipkart_data else {}

        if a_best or f_best:
            a_title = a_best.get('title', 'N/A')[:40]
            a_price = a_best.get('price', 'N/A')
            f_title = f_best.get('title', 'N/A')[:40]
            f_price = f_best.get('price', 'N/A')

            print(f"  {a_title:<45} {a_price:>12}")
            print(f"  {f_title:<45} {'':>12} {f_price:>12}")
            print(f"\n  {GREEN}{BOLD}>> Compare prices above to find the best deal!{RESET}")

        print(f"\n{GREEN}{'='*55}\n  DEMO COMPLETE — LLM used ONLY for extraction\n{'='*55}{RESET}\n")

    except Exception as e:
        print(f"\n{RED}EXCEPTION: {e}{RESET}")
        import traceback; traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    main()
