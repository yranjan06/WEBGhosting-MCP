import subprocess, json, sys, time

# Colors
G = "\033[32m"; R = "\033[31m"; Y = "\033[33m"; C = "\033[36m"; D = "\033[2m"; B = "\033[1m"; X = "\033[0m"

SITES = [
    ("Google",        "https://www.google.com",                         "document.title"),
    ("GitHub",        "https://github.com/trending",                    "document.title"),
    ("Wikipedia",     "https://en.wikipedia.org/wiki/Main_Page",        "document.title"),
    ("Amazon",        "https://www.amazon.com",                         "document.title"),
    ("Twitter/X",     "https://x.com",                                  "document.title"),
    ("Reddit (new)",  "https://www.reddit.com/r/technology",            "document.body.innerText.substring(0,200)"),
    ("Reddit (old)",  "https://old.reddit.com/r/technology",            "document.title"),
    ("LinkedIn",      "https://www.linkedin.com",                       "document.title"),
    ("Cloudflare",    "https://www.cloudflare.com",                     "document.title"),
    ("HackerNews",    "https://news.ycombinator.com",                   "document.title"),
    ("StackOverflow", "https://stackoverflow.com",                      "document.title"),
]

def run():
    print(f"\n{B}{C}{'='*60}")
    print(f"  GO-WebMcp Stealth Audit — Bot Detection Test")
    print(f"{'='*60}{X}\n")

    proc = subprocess.Popen(
        ['./webmcp'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, text=True
    )

    req_id = 1

    def rpc(method, params=None):
        nonlocal req_id
        msg = {"jsonrpc": "2.0", "method": method, "id": req_id}
        if params: msg["params"] = params
        proc.stdin.write(json.dumps(msg) + '\n')
        proc.stdin.flush()
        line = proc.stdout.readline()
        if not line: return None
        resp = json.loads(line)
        req_id += 1
        return resp

    def call_tool(name, args):
        resp = rpc("tools/call", {"name": name, "arguments": args})
        if not resp or "error" in resp: return None
        try: return resp["result"]["content"][0]["text"]
        except: return None

    try:
        # Init MCP
        rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "stealth-audit", "version": "1.0"}
        })
        proc.stdin.write(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"}) + '\n')
        proc.stdin.flush()
        print(f"  {G}✓ MCP Connected{X}\n")

        # Test stealth
        results = []
        for name, url, js_check in SITES:
            print(f"  {D}Testing {name}...{X}", end=" ", flush=True)

            # Browse
            browse_res = call_tool("browse", {"url": url})
            if not browse_res or "Failed" in browse_res:
                print(f"{R}✗ BROWSE FAILED{X}")
                results.append((name, url, "BROWSE_FAIL", ""))
                continue

            time.sleep(2)

            # Check page content
            content = call_tool("execute_js", {"script": js_check})
            if not content:
                print(f"{R}✗ JS FAILED{X}")
                results.append((name, url, "JS_FAIL", ""))
                continue

            # Detect bot checks
            bot_check = call_tool("execute_js", {"script": """
                (() => {
                    const text = document.body.innerText.toLowerCase();
                    const title = document.title.toLowerCase();
                    if (text.includes('prove your humanity') || text.includes('captcha') || text.includes('verify you are human'))
                        return 'CAPTCHA';
                    if (text.includes('unusual traffic') || text.includes('automated queries'))
                        return 'RATE_LIMIT';
                    if (text.includes('access denied') || text.includes('403 forbidden'))
                        return 'BLOCKED';
                    if (text.includes('please enable javascript') || text.includes('enable cookies'))
                        return 'JS_REQUIRED';
                    if (title.includes('just a moment') || text.includes('checking your browser'))
                        return 'CLOUDFLARE_CHALLENGE';
                    return 'PASSED';
                })()
            """})

            status = bot_check or "UNKNOWN"
            preview = (content[:60] + "...") if len(content) > 60 else content

            if status == "PASSED":
                print(f"{G}✓ PASSED{X}  {D}{preview}{X}")
            elif status == "CAPTCHA":
                print(f"{Y}⚠ CAPTCHA{X}  {D}{preview}{X}")
            elif status == "CLOUDFLARE_CHALLENGE":
                print(f"{Y}⚠ CLOUDFLARE{X}  {D}{preview}{X}")
            else:
                print(f"{R}✗ {status}{X}  {D}{preview}{X}")

            results.append((name, url, status, preview))

        # Summary
        passed = sum(1 for _, _, s, _ in results if s == "PASSED")
        total = len(results)
        print(f"\n{C}{'─'*60}")
        print(f"  Results: {passed}/{total} sites passed stealth check")
        print(f"{'─'*60}{X}")

        print(f"\n  {B}Summary:{X}")
        for name, url, status, _ in results:
            sym = f"{G}✓{X}" if status == "PASSED" else (f"{Y}⚠{X}" if status in ["CAPTCHA","CLOUDFLARE_CHALLENGE"] else f"{R}✗{X}")
            print(f"  {sym} {name:15s} → {status}")

        # Print recommendations
        blocked = [r for r in results if r[2] != "PASSED"]
        if blocked:
            print(f"\n  {B}Recommendations:{X}")
            for name, url, status, _ in blocked:
                if status == "CAPTCHA":
                    print(f"  {Y}→{X} {name}: Use alternative URL (e.g. old.reddit.com) or API")
                elif status == "CLOUDFLARE_CHALLENGE":
                    print(f"  {Y}→{X} {name}: Add delay before interaction, consider proxy")
                elif status == "RATE_LIMIT":
                    print(f"  {Y}→{X} {name}: Add random delays between requests")
                else:
                    print(f"  {Y}→{X} {name}: May need additional stealth headers or cookies")

        print()

    except Exception as e:
        print(f"\n{R}Error: {e}{X}")
    finally:
        proc.terminate()

if __name__ == "__main__":
    run()
