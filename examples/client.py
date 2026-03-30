#!/usr/bin/env python3
"""
Shared WEBGhosting Python Client
Reusable MCP stdio client for all example scripts.

Usage:
    from client import WEBGhostingClient
    client = WEBGhostingClient()
    client.call("browse", {"url": "https://example.com"})
    client.close()
"""

import subprocess
import json
import sys
import os
from pathlib import Path

# Terminal colors
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
DIM    = "\033[2m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


class WEBGhostingClient:
    """MCP stdio client for WEBGhosting server.

    Reads API config from environment variables:
        AI_API_KEY  (required)
        AI_BASE_URL (default: https://api.openai.com/v1)
        AI_MODEL    (default: gpt-4o)
    """

    def __init__(self, binary="./webmcp", env_overrides=None, show_server_logs=True):
        env = os.environ.copy()
        if env_overrides:
            env.update(env_overrides)
            
        if not env.get("AI_API_KEY"):
            print(f"{RED}ERROR: AI_API_KEY not set!{RESET}")
            print("Run: export AI_API_KEY='your-key-here'")
            sys.exit(1)

        self._warn_if_binary_is_stale(binary)

        stderr_target = sys.stderr if show_server_logs else subprocess.DEVNULL

        self.process = subprocess.Popen(
            [binary],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr_target,
            text=True,
            env=env
        )
        self.req_id = 1
        self._initialize()

    def _warn_if_binary_is_stale(self, binary):
        """Warn during local development if the compiled binary is older than server source."""
        try:
            binary_path = Path(binary).resolve()
            if not binary_path.exists():
                return

            source_candidates = [
                Path(__file__).resolve().parents[1] / "cmd" / "server" / "main.go",
                Path(__file__).resolve().parents[1] / "cmd" / "server" / "tools.go",
                Path(__file__).resolve().parents[1] / "cmd" / "server" / "config.go",
                Path(__file__).resolve().parents[1] / "cmd" / "server" / "banner.go",
            ]
            existing_sources = [path for path in source_candidates if path.exists()]
            if not existing_sources:
                return

            binary_mtime = binary_path.stat().st_mtime
            newest_source = max(path.stat().st_mtime for path in existing_sources)

            if newest_source > binary_mtime:
                print(f"{YELLOW}WARNING: ./webmcp is older than the current Go source.{RESET}")
                print(f"{DIM}Rebuild it so banner/code changes appear: make build{RESET}")
        except Exception:
            # Never block startup on a dev-only freshness check.
            pass

    def _initialize(self):
        msg = self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "webghosting-client", "version": "1.0"}
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
        print(f"{GREEN}[OK] WEBGhosting server initialized{RESET}")

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
