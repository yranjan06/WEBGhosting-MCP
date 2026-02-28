#!/usr/bin/env python3
"""Twitter (X.com) Search + Infinite Scroll — E2E Benchmark"""

import sys, time, json
sys.path.insert(0, '.')
from examples.client import *

client = GoWebMCPClient()

try:
    print(f"\n{CYAN}{'='*50}\n  Twitter: AI Search + Infinite Scroll Extraction\n{'='*50}{RESET}\n")

    # Step 1: Login (manual — X requires auth)
    print(f"{YELLOW}[Action] Opening X.com Login...{RESET}")
    client.call("browse", {"url": "https://x.com/login"})
    client.call("wait_for_load_state", {"state": "domcontentloaded"})

    print(f"\n{CYAN}  MANUAL LOGIN REQUIRED (120 seconds){RESET}")
    print(f"{DIM}  Complete login in the browser window{RESET}")
    for i in range(120, 0, -1):
        sys.stdout.write(f"\r  Waiting... {i}s ")
        sys.stdout.flush()
        time.sleep(1)
    print()

    # Step 2: Direct search URL
    target = "https://x.com/search?q=Artificial%20Intelligence"
    print(f"\n{YELLOW}[Action] Opening search: {target}{RESET}")
    client.call("browse", {"url": target})
    client.call("wait_for_load_state", {"state": "networkidle"})
    time.sleep(5)

    # Step 3: Scroll to load more tweets (infinite feed pattern)
    print(f"\n{YELLOW}[Action] Scrolling to load more tweets (3x)...{RESET}")
    for i in range(3):
        res = client.call("scroll", {"direction": "down", "amount": 800})
        print(f"  Scroll {i+1}/3: {res}")
        time.sleep(3)
    time.sleep(5)

    # Step 4: Extract tweets
    print(f"\n{YELLOW}[Action] Extracting tweets (Map-Reduce)...{RESET}")
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "author_name": {"type": "string"},
                "tweet_text": {"type": "string"},
                "metrics": {"type": "string", "description": "likes, reposts, views"}
            },
            "required": ["author_name", "tweet_text"]
        },
        "description": "Extract tweets from this X.com search feed"
    }
    res = client.call("extract", {"schema": schema})
    print(f"{GREEN}{res}{RESET}")
    print(f"\n{GREEN}Twitter benchmark complete!{RESET}")

except Exception as e:
    print(f"\n{RED}Error: {e}{RESET}")
finally:
    client.close()
