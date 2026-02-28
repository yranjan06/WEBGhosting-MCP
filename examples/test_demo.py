import subprocess
import json
import sys
import time
import os

# Colors
GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"

def rpc_message(method, params=None, id=None):
    msg = {
        "jsonrpc": "2.0",
        "method": method
    }
    if params is not None:
        msg["params"] = params
    if id is not None:
        msg["id"] = id
    return json.dumps(msg)

def read_response(process):
    while True:
        line = process.stdout.readline()
        if not line:
            return None
        line = line.decode('utf-8').strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            # Ignore log lines
            # print(f"Log: {line}", file=sys.stderr)
            pass

def run_test():
    print(f"{GREEN}[TEST] Starting WebMCP Integration Test...{RESET}")
    
    # Get absolute path to demo html
    cwd = os.getcwd()
    demo_url = f"file://{cwd}/demo/index.html"
    
    # Start Server
    process = subprocess.Popen(
        ['./webmcp'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True
    )

    try:
        # 1. Initialize
        print("\n[INFO] Sending 'initialize' request...")
        init_msg = rpc_message("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-runner", "version": "1.0"}
        }, id=1)
        process.stdin.write(init_msg + '\n')
        process.stdin.flush()
        
        # Read Init Response
        resp = json.loads(process.stdout.readline())
        print(f"[Got Response]: {json.dumps(resp)[:100]}...")

        # Notify initialized
        notify_msg = rpc_message("notifications/initialized")
        process.stdin.write(notify_msg + '\n')
        process.stdin.flush()

        # Helper to call tool
        req_id = 2
        def call_tool(name, args):
            nonlocal req_id
            msg = rpc_message("tools/call", {
                "name": name,
                "arguments": args
            }, id=req_id)
            process.stdin.write(msg + '\n')
            process.stdin.flush()
            
            line = process.stdout.readline()
            if not line: return None
            try:
                resp = json.loads(line)
            except: return None

            req_id += 1
            if "error" in resp:
                print(f"{RED}[FAIL] {name} error: {resp['error']}{RESET}")
                return None
            return resp["result"]["content"][0]["text"]


        # TEST 1: Browse
        print("\n--> Testing Browse & Stealth...")
        res = call_tool("browse", {"url": demo_url})
        print(f"Browse Result: {res}")
        
        # Verify Stealth via JS
        js_res = call_tool("execute_js", {"script": "document.getElementById('stealth-result').innerText"})
        if "PASS" in js_res:
            print(f"{GREEN}[PASS] Stealth Active{RESET}")
        else:
            print(f"{RED}[FAIL] Stealth Failed: {js_res}{RESET}")

        # TEST 2: Typing (Requires OpenAI)
        print("\n--> Testing Type (AI)...")
        type_res = call_tool("type", {"prompt": "Input Field", "text": "Hello WebMCP"})
        if type_res:
            # Verify value
            val = call_tool("execute_js", {"script": "document.getElementById('test-input').value"})
            if "Hello WebMCP" in val:
                 print(f"{GREEN}[PASS] Typing Success{RESET}")
            else:
                 print(f"{RED}[FAIL] Expected 'Hello WebMCP', got '{val}'{RESET}")
        else:
            print(f"{RED}[SKIP] Typing skipped (AI Agent failed/missing key){RESET}")

        # TEST 3: Console Logs
        print("\n--> Testing Console Logs...")
        call_tool("execute_js", {"script": "console.error('Test Simulated Error')"})
        logs = call_tool("get_console_logs", {})
        # Logs might be wrapped in TextContent, call_tool extracts the text.
        if logs and "Test Simulated Error" in logs:
            print(f"{GREEN}[PASS] Console Log Captured{RESET}")
        else:
            print(f"{RED}[FAIL] Log not captured. Logs: {logs}{RESET}")

        # TEST 4: Accessibility Tree
        print("\n--> Testing Semantic Perception...")
        tree = call_tool("get_accessibility_tree", {})
        if tree and "Aria Label Button" in tree:
            print(f"{GREEN}[PASS] Semantic Tree Retrieved{RESET}")
        else:
            print(f"{RED}[FAIL] Tree missing content. Tree: {tree[:100] if tree else 'None'}...{RESET}")

        # TEST 5: Dialog Handling
        print("\n--> Testing Dialogs...")
        # Configure to dismiss
        call_tool("configure_dialog", {"action": "dismiss"})
        # Trigger confirm
        call_tool("execute_js", {"script": "document.querySelector('button[onclick=\"triggerConfirm()\"]').click()"})
        # Check result
        dialog_res = call_tool("execute_js", {"script": "document.getElementById('dialog-result').innerText"})
        if dialog_res and "false" in dialog_res: # Dismiss = false for confirm
             print(f"{GREEN}[PASS] Dialog Auto-Dismissed{RESET}")
        else:
             print(f"{RED}[FAIL] Dialog check failed: {dialog_res}{RESET}")

    except Exception as e:
        print(f"{RED}[ERROR] {e}{RESET}")
        if process.poll() is not None:
             print(f"{RED}[DEBUG] Process exited with code: {process.returncode}{RESET}")
    finally:
        process.terminate()

if __name__ == "__main__":
    run_test()
