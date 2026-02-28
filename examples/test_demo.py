#!/usr/bin/env python3
"""
Go-WebMCP — Stealth & Demo Page Test
Validates browser stealth and core page interaction using demo/index.html
"""

import sys, os, json
sys.path.insert(0, '.')
from examples.client import *

client = GoWebMCPClient()

demo_url = f"file://{os.getcwd()}/examples/demo/index.html"

try:
    print(f"\n{CYAN}{'='*50}\n  Stealth + Demo Page Validation\n{'='*50}{RESET}\n")

    # Browse to demo page
    client.call("browse", {"url": demo_url})

    # Stealth check
    js_res = client.call("execute_js", {"script": "document.getElementById('stealth-result').innerText"})
    if js_res and "PASS" in js_res:
        print(f"  {GREEN}Stealth: ACTIVE (webdriver=false){RESET}")
    else:
        print(f"  {RED}Stealth: FAILED ({js_res}){RESET}")

    # Full fingerprint
    fp = client.call("execute_js", {
        "script": "JSON.stringify({webdriver: navigator.webdriver, plugins: navigator.plugins.length, languages: navigator.languages, platform: navigator.platform}, null, 2)"
    })
    print(f"  Fingerprint:\n{DIM}{fp}{RESET}")

    # Dialog test
    client.call("configure_dialog", {"action": "accept"})
    client.call("execute_js", {"script": "alert('Hello WebMCP Test!'); 'Dialog Triggered';"})
    print(f"  {GREEN}Dialog handling: OK{RESET}")

    print(f"\n{GREEN}Demo validation complete!{RESET}")

except Exception as e:
    print(f"\n{RED}Error: {e}{RESET}")
finally:
    client.close()
