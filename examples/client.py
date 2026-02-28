#!/usr/bin/env python3
"""
Shared Go-WebMCP Python Client
Reusable MCP stdio client for all example scripts.

Usage:
    from client import GoWebMCPClient
    client = GoWebMCPClient()
    client.call("browse", {"url": "https://example.com"})
    client.close()
"""

import subprocess
import json
import sys
import os

# Terminal colors
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
DIM    = "\033[2m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


class GoWebMCPClient:
    """MCP stdio client for Go-WebMCP server.

    Reads API config from environment variables:
        AI_API_KEY  (required)
        AI_BASE_URL (default: https://api.openai.com/v1)
        AI_MODEL    (default: gpt-4o)
    """

    def __init__(self, binary="./webmcp"):
        env = os.environ.copy()
        if not env.get("AI_API_KEY"):
            print(f"{RED}ERROR: AI_API_KEY not set!{RESET}")
            print("Run: export AI_API_KEY='your-key-here'")
            sys.exit(1)

        self.process = subprocess.Popen(
            [binary],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            env=env
        )
        self.req_id = 1
        self._initialize()

    def _initialize(self):
        msg = self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "webmcp-client", "version": "1.0"}
        })
        self.process.stdin.write(msg + '\n')
        self.process.stdin.flush()

        while True:
            line = self.process.stdout.readline()
            if not line:
                break
            try:
                if "jsonrpc" in json.loads(line):
                    break
            except (json.JSONDecodeError, ValueError):
                pass

        self.process.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + '\n'
        )
        self.process.stdin.flush()
        print(f"{GREEN}[OK] Go-WebMCP server initialized{RESET}")

    def _rpc(self, method, params=None):
        msg = {"jsonrpc": "2.0", "method": method, "id": self.req_id}
        if params is not None:
            msg["params"] = params
        self.req_id += 1
        return json.dumps(msg)

    def call(self, name, args):
        """Call an MCP tool and return the text result."""
        self.process.stdin.write(
            self._rpc("tools/call", {"name": name, "arguments": args}) + '\n'
        )
        self.process.stdin.flush()

        while True:
            line = self.process.stdout.readline()
            if not line:
                return None
            try:
                resp = json.loads(line)
                if "error" in resp:
                    return f"ERROR: {resp['error']}"
                if "result" in resp:
                    return resp["result"]["content"][0]["text"]
            except (json.JSONDecodeError, KeyError, IndexError):
                pass

    def close(self):
        """Terminate the server process."""
        self.process.terminate()
        self.process.wait(timeout=5)
