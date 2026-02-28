#!/usr/bin/env python3
"""Reddit r/technology — E2E Benchmark: AI Click + Extraction"""

import sys, time, json
sys.path.insert(0, '.')
from examples.client import *

client = GoWebMCPClient()

try:
    print(f"\n{CYAN}{'='*50}\n  Reddit: r/technology Post + Comment Extraction\n{'='*50}{RESET}\n")

    # Direct URL (no LLM wasted)
    target = "https://www.reddit.com/r/technology/hot/"
    print(f"{YELLOW}[Action] Opening: {target}{RESET}")
    client.call("browse", {"url": target})
    client.call("wait_for_load_state", {"state": "networkidle"})
    time.sleep(5)

    # AI Click — test natural language element finding
    print(f"\n{YELLOW}[Action] AI Click: 'first post title'...{RESET}")
    res = client.call("click", {"prompt": "Click on the title of the very first post"})
    print(f"  {GREEN}{res}{RESET}")
    time.sleep(8)

    # Extract comments
    print(f"\n{YELLOW}[Action] Extracting comments (Map-Reduce)...{RESET}")
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "author": {"type": "string"},
                "comment_text": {"type": "string"},
                "upvotes": {"type": "string"}
            },
            "required": ["author", "comment_text"]
        },
        "description": "Extract the top user comments from this Reddit post"
    }
    res = client.call("extract", {"schema": schema})
    print(f"{GREEN}{res}{RESET}")
    print(f"\n{GREEN}Reddit benchmark complete!{RESET}")

except Exception as e:
    print(f"\n{RED}Error: {e}{RESET}")
finally:
    client.close()
