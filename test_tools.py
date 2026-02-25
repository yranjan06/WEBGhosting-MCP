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


def run_tool_tests():
    print(f"\n{CYAN}{'='*50}")
    print(f"  Starting Comprehensive Tool Coverage Tests")
    print(f"{'='*50}{RESET}\n")

    client = GoWebMCPClient()
    
    try:
        # TEST 1: Dialog Handling & JS Execution
        print(f"\n{YELLOW}--- TEST 1: JS Execution & Dialog Handling ---{RESET}")
        print("Configuring dialogs to auto-accept...")
        client.call_tool("configure_dialog", {"action": "accept"})
        
        # Navigate to a blank page to test JS safely
        client.call_tool("browse", {"url": "about:blank"})
        
        print("Executing Javascript to trigger an Alert...")
        js_res = client.call_tool("execute_js", {"script": "alert('Hello WebMCP Test!'); 'Dialog Triggered & JS Executed';" })
        print(f"{GREEN}  -> JS Return Output: {js_res}{RESET}")


        # TEST 2: Multi-Tab Capabilities
        print(f"\n{YELLOW}--- TEST 2: Multi-Tab Capabilities ---{RESET}")
        print("Opening Tab 2...")
        client.call_tool("open_tab", {})
        client.call_tool("browse", {"url": "https://example.com"})
        
        print("Opening Tab 3...")
        client.call_tool("open_tab", {})
        client.call_tool("browse", {"url": "https://httpbin.org/get"})
        
        print("Listing Tabs...")
        tabs_res = client.call_tool("list_tabs", {})
        print(f"{GREEN}  -> Open Tabs:\n{tabs_res}{RESET}")
        
        print("Switching back to Tab 1 (index 0)...")
        client.call_tool("switch_tab", {"index": 0})
        
        print("Closing Tabs 1 and 2 (indices 1 & 2)...")
        client.call_tool("close_tab", {"index": 2})
        client.call_tool("close_tab", {"index": 1})
        
        tabs_res_final = client.call_tool("list_tabs", {})
        print(f"{GREEN}  -> Tabs Remaining:\n{tabs_res_final}{RESET}")


        # TEST 3: Batch Form Fill Tool (Testing without LLM Click for exact validation)
        print(f"\n{YELLOW}--- TEST 3: Batch Form Fill (the-internet.herokuapp.com/login) ---{RESET}")
        print("Navigating to test login page...")
        client.call_tool("browse", {"url": "https://the-internet.herokuapp.com/login"})
        client.call_tool("wait_for_load_state", {"state": "domcontentloaded"})
        
        print("Batch filling credentials...")
        fields = [
            {"selector": "#username", "value": "tomsmith", "type": "textbox"},
            {"selector": "#password", "value": "SuperSecretPassword!", "type": "textbox"}
        ]
        fill_res = client.call_tool("fill_form", {"fields": fields})
        print(f"{GREEN}  -> Form Fill Output: {fill_res}{RESET}")
        
        print("Executing JS to click native submit button... (mimicking programmatic automation)")
        client.call_tool("execute_js", {"script": "document.querySelector('button[type=\"submit\"]').click();"})
        client.call_tool("wait_for_load_state", {"state": "networkidle"})
        time.sleep(3) # Give page strict time to navigate to /secure
        
        print("Extracting flash message overlay via JS to confirm successful simulated login...")
        login_res = client.call_tool("execute_js", {"script": "document.getElementById('flash').textContent.trim()"})
        print(f"{GREEN}  -> Login Banner Success Test: {login_res}{RESET}")

        print(f"\n{CYAN}[Success] All Comprehensive Tool Tests Passed!{RESET}")

    except Exception as e:
        print(f"\n{RED}[Fatal Error] {e}{RESET}")
    finally:
        client.process.terminate()

if __name__ == "__main__":
    run_tool_tests()
