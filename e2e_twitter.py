import subprocess
import json
import sys
import time
import os

# Colors
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RESET = "\033[0m"

class GoWebMCPClient:
    def __init__(self):
        env = os.environ.copy()
        
        # Hardcoding the provided NVIDIA API credentials for Core Agent init
        env["AI_API_KEY"] = "***REDACTED_KEY***"
        env["AI_BASE_URL"] = "https://integrate.api.nvidia.com/v1"
        env["AI_MODEL"] = "moonshotai/kimi-k2.5"
            
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
        init_msg = self._make_rpc_msg("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "e2e-orchestrator", "version": "1.0"}
        })
        self.process.stdin.write(init_msg + '\n')
        self.process.stdin.flush()
        
        while True:
            line = self.process.stdout.readline()
            if not line: break
            try:
                if "jsonrpc" in json.loads(line): break
            except: pass
            
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + '\n')
        self.process.stdin.flush()
        print(f"{GREEN}[System] Go-WebMCP initialized successfully.{RESET}")

    def _make_rpc_msg(self, method, params=None):
        msg = {"jsonrpc": "2.0", "method": method, "id": self.req_id}
        if params is not None:
            msg["params"] = params
        self.req_id += 1
        return json.dumps(msg)

    def call_tool(self, name, args):
        msg = self._make_rpc_msg("tools/call", {"name": name, "arguments": args})
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


def run_twitter_benchmark():
    print(f"\n{CYAN}{'='*50}")
    print(f"  Starting E2E Benchmark: Twitter (X.com) Search & Scroll")
    print(f"{'='*50}{RESET}\n")

    client = GoWebMCPClient()
    
    try:
        # Step 1: Navigate to Login Page
        print(f"{YELLOW}[Action] Navigating to X.com (Twitter) Login...{RESET}")
        client.call_tool("browse", {"url": "https://x.com/login"})
        client.call_tool("wait_for_load_state", {"state": "domcontentloaded"})
        
        # Step 2: Manual Google SSO/Login Auth Pause
        # Twitter's anti-bot is extremely aggressive. Manual Google Auth is the most reliable path for testing extraction.
        print(f"\n{CYAN}===================================================={RESET}")
        print(f"{CYAN}  MANUAL LOGIN REQUIRED: X.COM (TWITTER)            {RESET}")
        print(f"{CYAN}===================================================={RESET}")
        print(f"{YELLOW}1. Please look at the opened Chromium browser window.{RESET}")
        print(f"{YELLOW}2. Complete your login (Google SSO recommended).{RESET}")
        print(f"{YELLOW}3. You have 260 seconds to complete this before the script continues.{RESET}")
        
        for i in range(260, 0, -1):
            sys.stdout.write(f"\rWaiting... {i} seconds remaining ")
            sys.stdout.flush()
            time.sleep(1)
        print("\n")
        
        # Step 3: Navigate to Target Search via URL
        # To avoid complex DOM navigation, directly load the search URL for a trending hashtag/topic
        target_search = "https://x.com/search?q=Artificial%20Intelligence"
        print(f"\n{YELLOW}[Action] Opening Target Search: {target_search}{RESET}")
        client.call_tool("browse", {"url": target_search})
        client.call_tool("wait_for_load_state", {"state": "networkidle"})
        
        print(f"{CYAN}[WAITING 5 SECONDS] Initial feed hydration...{RESET}")
        time.sleep(5)
        
        # Step 4: Test Agentic Scroll Logic
        print(f"\n{YELLOW}[Action] Testing Agentic Scrolling (3 Scrolls to load more tweets)...{RESET}")
        for i in range(3):
            # Using the `scroll` tool added to perception.go/browser
            scroll_res = client.call_tool("scroll", {"direction": "down", "amount": 800})
            print(f"  -> Scroll {i+1}/3: {scroll_res}")
            time.sleep(3) # Wait for infinite feed to load new elements
            
        print(f"{CYAN}[WAITING 5 SECONDS] Finalizing dynamic feed DOM stabilization...{RESET}")
        time.sleep(5)
            
        # Step 5: Extract Tweets
        print(f"\n{YELLOW}[Action] Extracting Loaded Tweets using LLM Map-Reduce Pipeline...{RESET}")
        schema = {
            "type": "object",
            "properties": {
                "tweets": {
                    "type": "array",
                    "description": "List of the top Tweets found on the X.com search feed",
                    "items": {
                        "type": "object",
                        "properties": {
                            "author_name": {"type": "string"},
                            "tweet_text": {"type": "string"},
                            "metrics": {
                                "type": "string",
                                "description": "e.g. 10K likes, 500 reposts"
                            }
                        },
                        "required": ["author_name", "tweet_text"]
                    }
                }
            },
            "required": ["tweets"]
        }
        
        # The Map-Reduce engine should handle the massive JS-bloated X.com DOM due to the previous LinkedIn fixes
        extract_res = client.call_tool("extract", {"schema": schema})
        print(f"  -> Extracted JSON Tweet Result:")
        print(f"{GREEN}{extract_res}{RESET}")
        
        print(f"\n{CYAN}[Success] Twitter Benchmark Complete!{RESET}")

    except Exception as e:
        print(f"\n{RED}[Fatal Error] {e}{RESET}")
    finally:
        client.process.terminate()

if __name__ == "__main__":
    run_twitter_benchmark()
