#!/usr/bin/env python3
"""
WEBGhosting — Multi-Site Page Context Test
==========================================
Tests get_page_context on 10 major websites to validate detection accuracy.
Reports: page_type, features detected, and any issues found.

NOTE: No AI_API_KEY needed — get_page_context is pure JS, zero LLM.
"""

import subprocess, json, sys, os, time

# Terminal colors
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
DIM    = "\033[2m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


class LightClient:
    """Minimal MCP client — no AI_API_KEY required."""
    def __init__(self):
        env = os.environ.copy()
        # Set dummy key so server starts (it won't be used for get_page_context)
        env.setdefault("AI_API_KEY", "dummy-for-non-ai-tools")
        self.process = subprocess.Popen(
            ["./webmcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=sys.stderr, text=True, env=env
        )
        self.req_id = 1
        # Initialize
        self._send("initialize", {
            "protocolVersion": "2025-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-context", "version": "1.0"}
        })
        self._read_response()
        self.process.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + '\n'
        )
        self.process.stdin.flush()
        print(f"{GREEN}[OK] Server ready{RESET}")

    def _send(self, method, params=None):
        msg = {"jsonrpc": "2.0", "method": method, "id": self.req_id}
        if params: msg["params"] = params
        self.req_id += 1
        self.process.stdin.write(json.dumps(msg) + '\n')
        self.process.stdin.flush()

    def _read_response(self):
        while True:
            line = self.process.stdout.readline()
            if not line: return None
            try:
                resp = json.loads(line)
                if "result" in resp: return resp["result"]
                if "error" in resp: return f"ERROR: {resp['error']}"
                if "jsonrpc" in resp: return resp
            except: pass

    def call(self, name, args=None):
        self._send("tools/call", {"name": name, "arguments": args or {}})
        resp = self._read_response()
        if isinstance(resp, dict) and "content" in resp:
            return resp["content"][0]["text"]
        return str(resp)

    def close(self):
        self.process.terminate()
        self.process.wait(timeout=5)


SITES = [
    ("Google Search",     "https://www.google.com/search?q=python+programming"),
    ("YouTube",           "https://www.youtube.com"),
    ("Reddit",            "https://www.reddit.com/r/programming"),
    ("Wikipedia",         "https://en.wikipedia.org/wiki/Python_(programming_language)"),
    ("Amazon Product",    "https://www.amazon.in/dp/B0CHX1W1XY"),
    ("GitHub Repo",       "https://github.com/nicepkg/gpt-runner"),
    ("Hacker News",       "https://news.ycombinator.com"),
    ("Twitter/X",         "https://x.com/explore"),
    ("LinkedIn",          "https://www.linkedin.com"),
    ("Stack Overflow",    "https://stackoverflow.com/questions/tagged/python"),
]

EXPECTED = {
    "Google Search":     {"type": "search_results", "search": True},
    "YouTube":           {"type": "video_platform",  "search": True},
    "Reddit":            {"type": "social_feed",     "search": True},
    "Wikipedia":         {"type": "article",         "search": True},
    "Amazon Product":    {"type": "product_page",    "cart": True},
    "GitHub Repo":       {"type": "code_repository"},
    "Hacker News":       {"type": "listing_page"},
    "Twitter/X":         {"type": "login_page",      "login": True},
    "LinkedIn":          {"type": "login_page",      "login": True},
    "Stack Overflow":    {"type": "listing_page",    "search": True},
}

client = LightClient()
results = []

try:
    print(f"\n{CYAN}{'='*70}")
    print(f"  PAGE CONTEXT TEST — 10 Major Websites")
    print(f"  Testing get_page_context detection accuracy")
    print(f"{'='*70}{RESET}\n")

    for name, url in SITES:
        print(f"{BOLD}▸ {name}{RESET}  {DIM}{url}{RESET}")

        try:
            # Navigate
            client.call("browse", {"url": url})
            time.sleep(3)
            client.call("wait_for_load_state", {"state": "domcontentloaded"})
            time.sleep(2)

            # Get context
            raw = client.call("get_page_context", {})
            ctx = json.loads(raw) if raw else {}

            # Evaluate
            exp = EXPECTED.get(name, {})
            issues = []

            # Check page type
            actual_type = ctx.get("page_type", "?")
            expected_type = exp.get("type", "")
            type_match = actual_type == expected_type
            if not type_match:
                issues.append(f"type: expected '{expected_type}' got '{actual_type}'")

            # Check features
            for feat, expected_val in exp.items():
                if feat == "type":
                    continue
                key = f"has_{feat}"
                actual_val = ctx.get(key, False)
                if actual_val != expected_val:
                    issues.append(f"{key}: expected {expected_val} got {actual_val}")

            # Print result
            status = f"{GREEN}» PASS{RESET}" if not issues else f"{RED}✗ FAIL{RESET}"
            print(f"  {status}  type={actual_type:<16} links={ctx.get('link_count',0):<5} "
                  f"search={'»' if ctx.get('has_search') else '✗'}  "
                  f"login={'»' if ctx.get('has_login') else '✗'}  "
                  f"reviews={'»' if ctx.get('has_reviews') else '✗'}  "
                  f"cart={'»' if ctx.get('has_cart') else '✗'}  "
                  f"video={'»' if ctx.get('has_video') else '✗'}  "
                  f"pagination={'»' if ctx.get('has_pagination') else '✗'}")
            if issues:
                for issue in issues:
                    print(f"         {YELLOW}→ {issue}{RESET}")

            # Print headings
            headings = ctx.get("main_headings", [])
            if headings:
                print(f"         {DIM}Headings: {', '.join(h[:40] for h in headings[:3])}{RESET}")

            results.append({"name": name, "passed": not issues, "issues": issues, "ctx": ctx})

        except Exception as e:
            print(f"  {RED}✗ ERROR: {e}{RESET}")
            results.append({"name": name, "passed": False, "issues": [str(e)], "ctx": {}})

        print()

    # Summary
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    color = GREEN if passed == total else YELLOW if passed > total//2 else RED

    print(f"{CYAN}{'='*70}")
    print(f"  RESULTS: {color}{passed}/{total} PASSED{RESET}")
    print(f"{CYAN}{'='*70}{RESET}\n")

    if passed < total:
        print(f"{BOLD}Issues Found:{RESET}")
        for r in results:
            if not r["passed"]:
                print(f"  {RED}✗ {r['name']}{RESET}")
                for issue in r["issues"]:
                    print(f"    → {issue}")
        print()

    # Dump full JSON for analysis
    print(f"\n{DIM}--- Full JSON dump for analysis ---{RESET}")
    for r in results:
        print(f"\n{BOLD}{r['name']}{RESET}:")
        print(json.dumps(r["ctx"], indent=2))

except Exception as e:
    print(f"\n{RED}FATAL: {e}{RESET}")
    import traceback; traceback.print_exc()
finally:
    client.close()
