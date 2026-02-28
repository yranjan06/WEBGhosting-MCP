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
        # Using Llama 3 for the core agent to ensure reliable JSON click/type generation
        env["AI_MODEL"] = "meta/llama-3.1-8b-instruct"
            
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


def run_reddit_benchmark():
    print(f"\n{CYAN}{'='*50}")
    print(f"  Starting E2E Benchmark: Reddit r/technology Upvote & Read")
    print(f"{'='*50}{RESET}\n")

    client = GoWebMCPClient()
    
    try:
        # Step 1: Navigate to Subreddit
        target_sub = "https://www.reddit.com/r/technology/hot/"
        print(f"\n{YELLOW}[Action] Opening Subreddit: {target_sub}{RESET}")
        client.call_tool("browse", {"url": target_sub})
        client.call_tool("wait_for_load_state", {"state": "networkidle"})
        
        print(f"{CYAN}[WAITING 5 SECONDS] feed hydration...{RESET}")
        time.sleep(5)
        
        # Step 4: Test Agentic AI Click (Upvoting/Opening Post)
        # Note: Testing the Agent's ability to map natural language to an interactable DOM element
        print(f"\n{YELLOW}[Action] Testing Agentic NL Click...{RESET}")
        click_res = client.call_tool("click", {"prompt": "Click on the title of the very first or top post on the page to open its main comment section"})
        print(f"  -> NL Click Result: {click_res}")
        
        print(f"{CYAN}[WAITING 8 SECONDS] Waiting for the comment overlay or page to load...{RESET}")
        time.sleep(8)
            
        # Step 5: Extract Threads/Comments
        print(f"\n{YELLOW}[Action] Extracting Post Comments using LLM Map-Reduce Pipeline...{RESET}")
        schema = {
            "type": "object",
            "properties": {
                "comments": {
                    "type": "array",
                    "description": "List of top user comments found on the Reddit post page",
                    "items": {
                        "type": "object",
                        "properties": {
                            "author": {"type": "string"},
                            "comment_text": {"type": "string"},
                            "upvotes_metrics": {"type": "string"}
                        },
                        "required": ["author", "comment_text"]
                    }
                }
            },
            "required": ["comments"]
        }
        
        extract_res = client.call_tool("extract", {"schema": schema})
        print(f"  -> Extracted JSON Comments Result:")
        print(f"{GREEN}{extract_res}{RESET}")
        
        print(f"\n{CYAN}[Success] Reddit Benchmark Complete!{RESET}")

    except Exception as e:
        print(f"\n{RED}[Fatal Error] {e}{RESET}")
    finally:
        client.process.terminate()

if __name__ == "__main__":
    run_reddit_benchmark()
