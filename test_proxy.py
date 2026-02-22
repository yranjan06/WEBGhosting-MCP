import subprocess, json, sys, os, time

# Set a fake proxy to prove Playwright is routing traffic through it
os.environ["HTTP_PROXY"] = "http://127.0.0.1:12345"
os.environ["PROXY_USERNAME"] = "testuser"
os.environ["PROXY_PASSWORD"] = "testpass"

print("\n\033[36m" + "="*50)
print("  GO-WebMcp Proxy Routing Test")
print("  HTTP_PROXY = " + os.environ["HTTP_PROXY"])
print("="*50 + "\033[0m\n")

proc = subprocess.Popen(
    ['./webmcp'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, text=True
)

req_id = 1

def rpc(method, params=None):
    global req_id
    msg = {"jsonrpc": "2.0", "method": method, "id": req_id}
    if params: msg["params"] = params
    proc.stdin.write(json.dumps(msg) + '\n')
    proc.stdin.flush()
    resp = json.loads(proc.stdout.readline())
    req_id += 1
    return resp

def call_tool(name, args):
    resp = rpc("tools/call", {"name": name, "arguments": args})
    return resp

try:
    print("\033[2m[1/2] Initializing MCP handshake...\033[0m")
    rpc("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "proxy-test", "version": "1.0"}
    })
    proc.stdin.write(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"}) + '\n')
    proc.stdin.flush()

    print("\n\033[2m[2/2] Attempting to browse Google through fake proxy...\033[0m")
    res = call_tool("browse", {"url": "https://www.google.com"})
    
    # We EXPECT this to fail because the proxy 127.0.0.1:12345 doesn't exist.
    # If the error is ERR_PROXY_CONNECTION_FAILED, our configuration works perfectly!
    
    if "error" in res:
        print(f"\n\033[31mError Context: {res['error']}\033[0m")
    else:
        text = res["result"]["content"][0]["text"]
        print(f"\nResult: {text}")
        
        if "ERR_PROXY_CONNECTION_FAILED" in text:
            print(f"\n\033[32m✅ PROXY ROUTING CONFIRMED!\033[0m")
            print("Playwright successfully attempted to use the configured HTTP_PROXY.")
        else:
            print(f"\n\033[31m✗ PROXY ROUTING FAILED. It bypassed the proxy.\033[0m")

except Exception as e:
    print(f"\nError: {e}")
finally:
    proc.terminate()
