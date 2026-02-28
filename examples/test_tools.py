#!/usr/bin/env python3
"""
Go-WebMCP — Core Tool Test Suite
Tests: browse, stealth, type, console logs, accessibility tree, dialog handling
Uses the local demo/index.html test page.
"""

import sys, os, json
sys.path.insert(0, '.')
from examples.client import *

client = GoWebMCPClient()

demo_url = f"file://{os.getcwd()}/examples/demo/index.html"
passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  {GREEN}PASS{RESET} {name}")
    else:
        failed += 1
        print(f"  {RED}FAIL{RESET} {name} {detail}")

try:
    print(f"\n{CYAN}{'='*50}\n  Go-WebMCP Core Tool Test Suite\n{'='*50}{RESET}\n")

    # TEST 1: Browse + Stealth
    print(f"{BOLD}Browse + Stealth{RESET}")
    res = client.call("browse", {"url": demo_url})
    check("browse", res and "Successfully" in res)

    js_res = client.call("execute_js", {"script": "document.getElementById('stealth-result').innerText"})
    check("stealth (webdriver=false)", js_res and "PASS" in js_res, js_res)

    # TEST 2: AI Typing
    print(f"\n{BOLD}AI Typing{RESET}")
    type_res = client.call("type", {"prompt": "Input Field", "text": "Hello WebMCP"})
    if type_res and "ERROR" not in type_res:
        val = client.call("execute_js", {"script": "document.getElementById('test-input').value"})
        check("type", val and "Hello WebMCP" in val, val)
    else:
        check("type (needs AI_API_KEY)", False, type_res)

    # TEST 3: Console Logs
    print(f"\n{BOLD}Console Logs{RESET}")
    client.call("execute_js", {"script": "console.error('Test Simulated Error')"})
    logs = client.call("get_console_logs", {})
    check("console log capture", logs and "Test Simulated Error" in logs)

    # TEST 4: Accessibility Tree
    print(f"\n{BOLD}Accessibility Tree{RESET}")
    tree = client.call("get_accessibility_tree", {})
    check("a11y tree", tree and "Aria Label Button" in tree, f"len={len(tree) if tree else 0}")

    # TEST 5: Dialog Handling
    print(f"\n{BOLD}Dialog Handling{RESET}")
    client.call("configure_dialog", {"action": "dismiss"})
    client.call("execute_js", {"script": "document.querySelector('button[onclick=\"triggerConfirm()\"]').click()"})
    dialog_res = client.call("execute_js", {"script": "document.getElementById('dialog-result').innerText"})
    check("dialog dismiss", dialog_res and "false" in dialog_res, dialog_res)

    # TEST 6: Multi-Tab
    print(f"\n{BOLD}Multi-Tab{RESET}")
    client.call("open_tab", {})
    client.call("browse", {"url": "https://example.com"})
    tabs = client.call("list_tabs", {})
    check("multi-tab", tabs and "example.com" in tabs)
    client.call("close_tab", {"index": 1})

    # TEST 7: Key Press
    print(f"\n{BOLD}Key Press{RESET}")
    res = client.call("press_key", {"key": "Tab"})
    check("press_key", res and "Pressed" in res)

    # TEST 8: Status
    print(f"\n{BOLD}Status{RESET}")
    status = client.call("get_status", {})
    check("get_status", status and "initialized" in status)

    # Summary
    total = passed + failed
    print(f"\n{CYAN}{'='*50}{RESET}")
    print(f"  Results: {GREEN}{passed}/{total} passed{RESET}", end="")
    if failed:
        print(f", {RED}{failed} failed{RESET}")
    else:
        print()
    print(f"{CYAN}{'='*50}{RESET}\n")

except Exception as e:
    print(f"\n{RED}Error: {e}{RESET}")
finally:
    client.close()
