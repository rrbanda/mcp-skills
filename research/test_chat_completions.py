#!/usr/bin/env python3
"""
Test Llama Stack's /v1/chat/completions endpoint directly (no proxy).

Verifies that switching from Responses API to Chat Completions API
eliminates the need for llm_proxy.py entirely.

Usage:
  export LLAMASTACK_URL=https://llamastack-llamastack.apps.your-cluster.com
  python3 research/test_chat_completions.py
"""

import json
import os
import sys
import urllib3

import httpx

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

UPSTREAM = os.environ.get("LLAMASTACK_URL", "").rstrip("/")
MODEL = os.environ.get("GOOSE_MODEL", "vllm-inference/gpt-oss-120b")
TIMEOUT = 60.0

if not UPSTREAM:
    print("ERROR: Set LLAMASTACK_URL environment variable first.")
    print("  export LLAMASTACK_URL=https://llamastack-llamastack.apps.ocp.v7hjl.sandbox2288.opentlc.com")
    sys.exit(1)

URL = f"{UPSTREAM}/v1/chat/completions"
RESULTS = {}


def report(test_id: str, name: str, passed: bool, detail: str):
    status = "PASS" if passed else "FAIL"
    RESULTS[test_id] = (name, passed, detail)
    print(f"  [{status}] {test_id}. {name}")
    if detail:
        for line in detail.strip().splitlines():
            print(f"         {line}")
    print()


def test_non_streaming():
    """Test A: basic non-streaming chat completion."""
    print("--- Test A: Non-streaming Chat Completion ---")
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "Say hello in one word."}],
        "max_tokens": 256,
        "stream": False,
    }
    try:
        with httpx.Client(verify=False, timeout=TIMEOUT) as c:
            resp = c.post(URL, json=payload)
        if resp.status_code == 200:
            body = resp.json()
            choices = body.get("choices", [])
            msg = choices[0].get("message", {}) if choices else {}
            content = msg.get("content")
            if content:
                report("A", "non-streaming", True, f"Response: {content[:80]}")
            elif msg.get("reasoning") or msg.get("reasoning_content"):
                report("A", "non-streaming", False,
                       "Model returned reasoning but no content — increase max_tokens")
            else:
                report("A", "non-streaming", False,
                       f"No content in response: {json.dumps(body)[:200]}")
        else:
            report("A", "non-streaming", False, f"HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        report("A", "non-streaming", False, f"Request error: {e}")


def test_streaming():
    """Test B: streaming chat completion with SSE parsing."""
    print("--- Test B: Streaming Chat Completion ---")
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "Count from 1 to 5."}],
        "max_tokens": 64,
        "stream": True,
    }
    events = []
    content_chunks = []
    try:
        with httpx.Client(verify=False, timeout=TIMEOUT) as c:
            with c.stream("POST", URL, json=payload) as resp:
                if resp.status_code != 200:
                    report("B", "streaming", False, f"HTTP {resp.status_code}")
                    return
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if not data_str or data_str == "[DONE]":
                        continue
                    try:
                        obj = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    events.append(obj)
                    delta = obj.get("choices", [{}])[0].get("delta", {})
                    if "content" in delta and delta["content"]:
                        content_chunks.append(delta["content"])
    except Exception as e:
        report("B", "streaming", False, f"Stream error: {e}")
        return

    if not events:
        report("B", "streaming", False, "No SSE events received")
        return

    full_content = "".join(content_chunks)
    report("B", "streaming", True,
           f"{len(events)} events, {len(content_chunks)} content chunks\n"
           f"Content: {full_content[:100]}")


def test_max_tokens():
    """Test C: max_tokens is accepted (unlike max_output_tokens in Responses API)."""
    print("--- Test C: max_tokens accepted ---")
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 16,
        "stream": False,
    }
    try:
        with httpx.Client(verify=False, timeout=TIMEOUT) as c:
            resp = c.post(URL, json=payload)
        if resp.status_code == 200:
            report("C", "max_tokens", True, "HTTP 200 -- max_tokens accepted without errors")
        else:
            report("C", "max_tokens", False, f"HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        report("C", "max_tokens", False, f"Request error: {e}")


def test_tool_calling():
    """Test D: tool/function calling works in streaming mode (how Goose uses it)."""
    print("--- Test D: Tool/Function Calling (streaming) ---")
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "What is the weather in San Francisco?"}],
        "tools": [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather for a location.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City name"}
                    },
                    "required": ["location"]
                }
            }
        }],
        "max_tokens": 256,
        "stream": True,
    }
    func_name = ""
    func_args = ""
    events = []
    try:
        with httpx.Client(verify=False, timeout=TIMEOUT) as c:
            with c.stream("POST", URL, json=payload) as resp:
                if resp.status_code != 200:
                    report("D", "tool calling", False, f"HTTP {resp.status_code}")
                    return
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if not data_str or data_str == "[DONE]":
                        continue
                    try:
                        obj = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    events.append(obj)
                    delta = obj.get("choices", [{}])[0].get("delta", {})
                    tcs = delta.get("tool_calls")
                    if tcs:
                        tc = tcs[0]
                        fn = tc.get("function", {})
                        if fn.get("name"):
                            func_name = fn["name"]
                        if fn.get("arguments"):
                            func_args += fn["arguments"]
    except Exception as e:
        report("D", "tool calling", False, f"Stream error: {e}")
        return

    if func_name:
        report("D", "tool calling", True,
               f"Tool call: {func_name}({func_args[:80]})")
    else:
        report("D", "tool calling", False,
               f"No tool_calls deltas in {len(events)} streaming events")


if __name__ == "__main__":
    print(f"Target: {UPSTREAM}/v1/chat/completions")
    print(f"Model:  {MODEL}")
    print()

    test_non_streaming()
    test_streaming()
    test_max_tokens()
    test_tool_calling()

    print("=" * 55)
    print("  Chat Completions Compatibility Report")
    print("=" * 55)
    for test_id in ("A", "B", "C", "D"):
        if test_id in RESULTS:
            name, passed, _ = RESULTS[test_id]
            status = "PASS" if passed else "FAIL"
            print(f"  {test_id}. {name:20s}  {status}")
    print("=" * 55)

    all_pass = all(passed for _, passed, _ in RESULTS.values())
    if all_pass:
        print("\n  All tests passed. Safe to switch from Responses API to Chat Completions.")
        print("  The proxy (llm_proxy.py) can be removed.")
    else:
        failed = [f"{tid}. {name}" for tid, (name, passed, _) in RESULTS.items() if not passed]
        print(f"\n  Some tests failed: {', '.join(failed)}")
        print("  Investigate before removing the proxy.")
    print()
