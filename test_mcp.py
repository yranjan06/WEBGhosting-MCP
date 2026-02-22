import subprocess
import json
import sys
import time

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
            print(f"Log: {line}", file=sys.stderr)

def main():
    # Start the server
    print("[INFO] Starting WebMCP Server...")
    process = subprocess.Popen(
        ['./webmcp'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr
    )

    try:
        # 1. Initialize
        print("\n[INFO] Sending 'initialize' request...")
        init_msg = rpc_message("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"}
        }, id=1)
        process.stdin.write(init_msg.encode('utf-8') + b'\n')
        process.stdin.flush()

        resp = read_response(process)
        print(f"[SUCCESS] Received Initialize Response: {json.dumps(resp, indent=2)}")

        # 2. Initialized Notification
        print("\n[INFO] Sending 'notifications/initialized'...")
        notify_msg = rpc_message("notifications/initialized")
        process.stdin.write(notify_msg.encode('utf-8') + b'\n')
        process.stdin.flush()

        # 3. List Tools
        print("\n[INFO] Sending 'tools/list' request...")
        list_msg = rpc_message("tools/list", id=2)
        process.stdin.write(list_msg.encode('utf-8') + b'\n')
        process.stdin.flush()

        resp = read_response(process)
        print(f"[SUCCESS] Received Tools List: {json.dumps(resp, indent=2)}")

        tools = resp.get("result", {}).get("tools", [])
        tool_names = [t["name"] for t in tools]
        print(f"\n[DONE] Server is working! Found {len(tools)} tools: {', '.join(tool_names)}")

    except Exception as e:
        print(f"[ERROR] Error: {e}")
    finally:
        process.terminate()

if __name__ == "__main__":
    main()
