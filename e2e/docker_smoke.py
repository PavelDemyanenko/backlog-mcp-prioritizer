#!/usr/bin/env python3
"""Smoke test of the Docker image over stdio, exactly as an MCP host starts it.

  python3 e2e/docker_smoke.py <image>

Checks: initialize -> tools/list (4 tools) -> a tool call without a token returns a curated tool
error; every stdout line is JSON-RPC 2.0; the container exits when stdin closes.
"""
import json
import subprocess
import sys
import time

EXPECTED_TOOLS = {"youtrack_query_backlog", "youtrack_count_issues", "adr_list", "adr_read"}


def main(image: str) -> int:
    proc = subprocess.Popen(["docker", "run", "-i", "--rm", image], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def send(msg):
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()

    def receive(want_id, timeout=60):
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            msg = json.loads(line)                       # any non-JSON stdout line fails here
            assert msg.get("jsonrpc") == "2.0", line
            if msg.get("id") == want_id:
                return msg
        raise AssertionError(f"no response with id {want_id}; stderr:\n{proc.stderr.read()[-2000:]}")

    send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "smoke", "version": "1"}}})
    init = receive(1)
    assert init["result"]["serverInfo"]["name"] == "backlog-mcp-prioritizer", init
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = {t["name"] for t in receive(2)["result"]["tools"]}
    assert tools == EXPECTED_TOOLS, tools
    send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
          "params": {"name": "youtrack_count_issues", "arguments": {"search_query": "x"}}})
    call = receive(3)["result"]
    assert call["isError"] and "YOUTRACK_TOKEN" in call["content"][0]["text"], call
    proc.stdin.close()
    assert proc.wait(timeout=30) == 0, "container did not exit cleanly after stdin closed"
    print(f"OK: {image} speaks MCP over stdio, tools={sorted(tools)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "backlog-mcp-prioritizer"))
