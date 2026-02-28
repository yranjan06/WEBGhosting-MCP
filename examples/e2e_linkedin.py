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


def run_linkedin_benchmark():
    print(f"\n{CYAN}{'='*50}")
    print(f"  Starting E2E Benchmark: LinkedIn Secure Profile Scrape")
    print(f"{'='*50}{RESET}\n")

    client = GoWebMCPClient()
    
    try:
        # Step 1: Navigate to Login Page
        print(f"{YELLOW}[Action] Navigating to LinkedIn Login...{RESET}")
        client.call_tool("browse", {"url": "https://www.linkedin.com/login"})
        client.call_tool("wait_for_load_state", {"state": "domcontentloaded"})
        
        # Step 2: Manual Google SSO Auth Pause
        print(f"\n{CYAN}===================================================={RESET}")
        print(f"{CYAN}  MANUAL LOGIN REQUIRED: GOOGLE SSO                 {RESET}")
        print(f"{CYAN}===================================================={RESET}")
        print(f"{YELLOW}1. Please look at the opened Chromium browser window.{RESET}")
        print(f"{YELLOW}2. Click 'Continue with Google' and complete your login.{RESET}")
        print(f"{YELLOW}3. You have 60 seconds to complete this before the script continues.{RESET}")
        
        for i in range(60, 0, -1):
            sys.stdout.write(f"\rWaiting... {i} seconds remaining ")
            sys.stdout.flush()
            time.sleep(1)
        print("\n")
        
        # Step 4: Navigate to target Job Search
        target_search = "https://www.linkedin.com/jobs/search/?keywords=Data%20Engineering"
        print(f"\n{YELLOW}[Action] Opening Target Job Search: {target_search}{RESET}")
        client.call_tool("browse", {"url": target_search})
        client.call_tool("wait_for_load_state", {"state": "domcontentloaded"})
        
        print(f"{CYAN}[WAITING 8 SECONDS] Loading dynamic job postings segments...{RESET}")
        time.sleep(8)
        
        # Step 5: Extract Job Postings
        print(f"\n{YELLOW}[Action] Extracting Job Postings using LLM Map-Reduce Pipeline...{RESET}")
        schema = {
            "type": "object",
            "properties": {
                "job_postings": {
                    "type": "array",
                    "description": "List of Data Engineering job postings found on the search page",
                    "items": {
                        "type": "object",
                        "properties": {
                            "job_title": {"type": "string"},
                            "company": {"type": "string"},
                            "location": {"type": "string"},
                            "posted_time": {"type": "string"}
                        },
                        "required": ["job_title", "company"]
                    }
                }
            },
            "required": ["job_postings"]
        }
        
        extract_res = client.call_tool("extract", {"schema": schema})
        print(f"  -> Extracted JSON Profile Result:")
        print(f"{GREEN}{extract_res}{RESET}")
        
        print(f"\n{CYAN}[Success] LinkedIn Benchmark Complete!{RESET}")

    except Exception as e:
        print(f"\n{RED}[Fatal Error] {e}{RESET}")
    finally:
        client.process.terminate()

if __name__ == "__main__":
    run_linkedin_benchmark()
