#!/usr/bin/env python3
"""
Go-WebMCP — Hacker News E2E Demo
Tests: stealth, browse, accessibility tree, AI click, extraction, multi-tab
"""

import sys, time, json
sys.path.insert(0, '.')
from examples.client import *

client = GoWebMCPClient()

try:
    print(f"\n{CYAN}{'='*55}\n  Go-WebMCP E2E Demo — Hacker News\n{'='*55}{RESET}")

    # Phase 1: Stealth Navigation
    print(f"\n{BOLD}Phase 1: Stealth Navigation{RESET}")
    client.call("browse", {"url": "https://news.ycombinator.com"})
    print(f"  {GREEN}Navigated to Hacker News{RESET}")

    # Phase 2: Stealth Verification
    print(f"\n{BOLD}Phase 2: Stealth Verification{RESET}")
    res = client.call("execute_js", {
        "script": "JSON.stringify({webdriver: navigator.webdriver, plugins: navigator.plugins.length, languages: navigator.languages}, null, 2)"
    })
    print(f"  {GREEN}{res}{RESET}")

    # Phase 3: Server Status
    print(f"\n{BOLD}Phase 3: Server Status{RESET}")
    status = client.call("get_status", {})
    print(f"  {GREEN}{status}{RESET}")

    # Phase 4: Accessibility Tree
    print(f"\n{BOLD}Phase 4: Accessibility Tree{RESET}")
    tree = client.call("get_accessibility_tree", {})
    if tree:
        lines = tree.strip().split('\n')
        print(f"  {GREEN}{len(lines)} ARIA nodes. First 5:{RESET}")
        for l in lines[:5]:
            print(f"   {DIM}{l}{RESET}")

    # Phase 5: AI Click
    print(f"\n{BOLD}Phase 5: AI Click{RESET}")
    res = client.call("click", {"prompt": "More link at the bottom"})
    print(f"  {GREEN}{res}{RESET}")

    # Phase 6: Extraction
    print(f"\n{BOLD}Phase 6: Map-Reduce Extraction{RESET}")
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "url": {"type": "string"},
                "points": {"type": "string"},
                "author": {"type": "string"}
            }
        },
        "description": "Extract all Hacker News story titles with URL, points, author"
    }
    res = client.call("extract", {"schema": schema})
    if res:
        try:
            data = json.loads(res)
            print(f"  {GREEN}Extracted {len(data)} stories{RESET}")
            for s in data[:3]:
                print(f"    - {s.get('title', '?')[:50]} ({s.get('points', '?')} pts)")
        except:
            print(f"  {YELLOW}{res[:200]}{RESET}")

    # Phase 7: Multi-Tab
    print(f"\n{BOLD}Phase 7: Multi-Tab{RESET}")
    client.call("open_tab", {})
    client.call("browse", {"url": "https://example.com"})
    tabs = client.call("list_tabs", {})
    print(f"  {GREEN}{tabs}{RESET}")
    client.call("close_tab", {"index": 1})

    print(f"\n{GREEN}{'='*55}\n  ALL 7 PHASES COMPLETE\n{'='*55}{RESET}\n")

except Exception as e:
    print(f"\n{RED}EXCEPTION: {e}{RESET}")
    import traceback; traceback.print_exc()
finally:
    client.close()
