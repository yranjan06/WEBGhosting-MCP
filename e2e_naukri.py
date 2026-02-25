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
        
        # Hardcoding the provided NVIDIA API credentials
        env["AI_API_KEY"] = "***REDACTED_KEY***"
        env["AI_BASE_URL"] = "https://integrate.api.nvidia.com/v1"
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


def run_naukri_benchmark():
    print(f"\n{CYAN}{'='*50}")
    print(f"  Starting E2E Benchmark: Naukri Data Engineering Jobs")
    print(f"{'='*50}{RESET}\n")

    client = GoWebMCPClient()
    
    try:
        # Step 1: Navigate to Naukri Search Results
        target_url = "https://www.naukri.com/data-engineering-jobs?k=data%20engineering"
        print(f"{YELLOW}[Action] Navigating to Naukri Search: {target_url}{RESET}")
        client.call_tool("browse", {"url": target_url})
        client.call_tool("wait_for_load_state", {"state": "networkidle"})
        
        print(f"{CYAN}[WAITING 5 SECONDS] feed hydration...{RESET}")
        time.sleep(5)
            
        # Step 2: Extract Job Postings
        print(f"\n{YELLOW}[Action] Extracting Job Data using LLM Map-Reduce Pipeline...{RESET}")
        schema = {
            "type": "object",
            "properties": {
                "jobs": {
                    "type": "array",
                    "description": "List of job postings on the page",
                    "items": {
                        "type": "object",
                        "properties": {
                            "job_title": {"type": "string"},
                            "company_name": {"type": "string"},
                            "experience_required": {"type": "string"},
                            "location": {"type": "string"},
                            "skills_or_requirements": {"type": "string"}
                        },
                        "required": ["job_title", "company_name"]
                    }
                }
            },
            "required": ["jobs"]
        }
        
        extract_res = client.call_tool("extract", {"schema": schema})
        print(f"  -> Extracted JSON Jobs Result:")
        print(f"{GREEN}{extract_res}{RESET}")
        
        print(f"\n{CYAN}[Success] Naukri Benchmark Complete!{RESET}")

    except Exception as e:
        print(f"\n{RED}[Fatal Error] {e}{RESET}")
    finally:
        client.process.terminate()

if __name__ == "__main__":
    run_naukri_benchmark()
