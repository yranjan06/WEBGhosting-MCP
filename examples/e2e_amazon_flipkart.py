#!/usr/bin/env python3
"""
Go-WebMCP — Smart Demo: iPhone 15 Price Comparison
Strategy: Direct search URLs (no LLM wasted on finding buttons).
          LLM used ONLY for structured data extraction.
"""

import sys, time, json
sys.path.insert(0, '.')
from examples.client import *

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
    print(f"\n{CYAN}{'='*55}\n  iPhone 15 — Amazon vs Flipkart\n  Smart Mode: Direct URLs + LLM Extraction Only\n{'='*55}{RESET}")

    # Phase 1: Stealth
    print(f"\n{BOLD}Phase 1: Stealth Verification{RESET}")
    client.call("browse", {"url": "about:blank"})
    res = client.call("execute_js", {
        "script": "JSON.stringify({webdriver: navigator.webdriver, plugins: navigator.plugins.length, chrome: typeof chrome !== 'undefined'}, null, 2)"
    })
    print(f"  {GREEN}{res}{RESET}")

    # Phase 2: Amazon (direct URL)
    print(f"\n{BOLD}Phase 2: Amazon India{RESET}")
    print(f"  {DIM}browse(amazon.in/s?k=iPhone+15) — NO LLM needed{RESET}")
    client.call("browse", {"url": "https://www.amazon.in/s?k=iPhone+15"})
    time.sleep(3)
    client.call("wait_for_load_state", {"state": "networkidle"})

    print(f"  Extracting products (Map-Reduce)...")
    amazon_raw = client.call("extract", {"schema": schema})
    amazon_data = []
    if amazon_raw:
        try:
            amazon_data = json.loads(amazon_raw)
            print(f"  {GREEN}Extracted {len(amazon_data)} products{RESET}")
            for i, p in enumerate(amazon_data[:5]):
                print(f"    [{i+1}] {p.get('title', 'N/A')[:55]}")
                print(f"        {BOLD}{p.get('price', '?')}{RESET} | {p.get('rating', '?')} | {p.get('reviews', '?')} reviews")
        except:
            print(f"  {YELLOW}Raw: {amazon_raw[:300]}{RESET}")

    # Phase 3: Flipkart (direct URL, new tab)
    print(f"\n{BOLD}Phase 3: Flipkart (New Tab){RESET}")
    client.call("open_tab", {})
    print(f"  {DIM}browse(flipkart.com/search?q=iphone+15) — NO LLM needed{RESET}")
    client.call("browse", {"url": "https://www.flipkart.com/search?q=iphone+15"})
    time.sleep(3)
    client.call("wait_for_load_state", {"state": "networkidle"})

    print(f"  Extracting products (Map-Reduce)...")
    flipkart_raw = client.call("extract", {"schema": schema})
    flipkart_data = []
    if flipkart_raw:
        try:
            flipkart_data = json.loads(flipkart_raw)
            print(f"  {GREEN}Extracted {len(flipkart_data)} products{RESET}")
            for i, p in enumerate(flipkart_data[:5]):
                print(f"    [{i+1}] {p.get('title', 'N/A')[:55]}")
                print(f"        {BOLD}{p.get('price', '?')}{RESET} | {p.get('rating', '?')} | {p.get('reviews', '?')} reviews")
        except:
            print(f"  {YELLOW}Raw: {flipkart_raw[:300]}{RESET}")

    # Phase 4: Multi-Tab
    print(f"\n{BOLD}Phase 4: Multi-Tab Proof{RESET}")
    tabs = client.call("list_tabs", {})
    print(f"  {GREEN}{tabs}{RESET}")

    # Phase 5: Comparison
    print(f"\n{BOLD}Phase 5: Comparison{RESET}")
    a = amazon_data[0] if amazon_data else {}
    f = flipkart_data[0] if flipkart_data else {}
    if a: print(f"  Amazon:   {a.get('title', '?')[:40]} — {BOLD}{a.get('price', '?')}{RESET}")
    if f: print(f"  Flipkart: {f.get('title', '?')[:40]} — {BOLD}{f.get('price', '?')}{RESET}")

    print(f"\n{GREEN}{'='*55}\n  DEMO COMPLETE — LLM used ONLY for extraction\n{'='*55}{RESET}\n")

except Exception as e:
    print(f"\n{RED}EXCEPTION: {e}{RESET}")
    import traceback; traceback.print_exc()
finally:
    client.close()
