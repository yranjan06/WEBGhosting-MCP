import subprocess
import json
import sys
import time

GREEN = "\033[32m"
RESET = "\033[0m"

client = subprocess.Popen(['./webmcp'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
req_id = 1

def rpc(method, params=None):
    global req_id
    msg = {"jsonrpc": "2.0", "method": method, "id": req_id}
    if params: msg["params"] = params
    client.stdin.write(json.dumps(msg) + '\n')
    client.stdin.flush()
    while True:
        line = client.stdout.readline()
        if not line: return None
        try:
            resp = json.loads(line)
            if "id" in resp and resp["id"] == req_id:
                req_id += 1
                return resp
        except: pass

rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}})
client.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + '\n')
client.stdin.flush()

print("Browsing...")
rpc("tools/call", {"name": "browse", "arguments": {"url": "https://www.naukri.com/data-engineering-jobs"}})
rpc("tools/call", {"name": "wait_for_load_state", "arguments": {"state": "networkidle"}})
time.sleep(5)

print("Executing JS to get innerText...")
resp = rpc("tools/call", {"name": "execute_js", "arguments": {"script": "document.body.innerText"}})

text = resp["result"]["content"][0]["text"]
print(f"Length of text: {len(text)}")
with open('debug_text.txt', 'w') as f:
    f.write(text)
print("Saved to debug_text.txt")

client.terminate()
