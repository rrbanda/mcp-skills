#!/usr/bin/env python3
"""
DEPRECATED: The proxy (llm_proxy.py) has been removed.

Goose now talks directly to Llama Stack via the Chat Completions API
(/v1/chat/completions) instead of the Responses API (/v1/responses).
All three incompatibilities this script tests are specific to the
Responses API and do not apply to Chat Completions.

See research/test_chat_completions.py for the current validation script.

--- Original description ---

Diagnostic script to test whether llm_proxy.py was still needed.

Sent requests directly to Llama Stack's /v1/responses endpoint and
checked for each incompatibility that the proxy worked around:

  Fix 1: max_output_tokens rejection
  Fix 2: missing sequence_number in SSE events
  Fix 3: reasoning_text content parts Goose can't parse
  Fix 4: nested error in response.failed events

Usage:
  export LLAMASTACK_URL=https://llamastack-llamastack.apps.your-cluster.com
  python3 research/test_proxy_necessity.py
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

RESULTS = {}


def report(fix_id: str, name: str, passed: bool, detail: str):
    status = "PASS" if passed else "FAIL"
    tag = "no longer needed" if passed else "STILL NEEDED"
    RESULTS[fix_id] = (name, passed, detail)
    print(f"  [{status}] Fix {fix_id} ({name}): {tag}")
    if detail:
        for line in detail.strip().splitlines():
            print(f"         {line}")
    print()


# ---------------------------------------------------------------------------
# Test A: max_output_tokens acceptance
# ---------------------------------------------------------------------------
def test_max_output_tokens():
    print("--- Test A: max_output_tokens acceptance ---")
    url = f"{UPSTREAM}/v1/responses"
    payload = {
        "model": MODEL,
        "input": "Say hello in one word.",
        "stream": False,
        "max_output_tokens": 64,
    }
    try:
        with httpx.Client(verify=False, timeout=TIMEOUT) as c:
            resp = c.post(url, json=payload)
        if resp.status_code == 200:
            body = resp.json()
            if "id" in body:
                report("1", "max_output_tokens", True, f"HTTP 200, response id={body['id']}")
            else:
                report("1", "max_output_tokens", False, f"HTTP 200 but unexpected body: {json.dumps(body)[:200]}")
        else:
            body_text = resp.text[:300]
            if "max_output_tokens" in body_text.lower():
                report("1", "max_output_tokens", False, f"HTTP {resp.status_code}, rejected max_output_tokens: {body_text}")
            else:
                report("1", "max_output_tokens", False, f"HTTP {resp.status_code}: {body_text}")
    except Exception as e:
        report("1", "max_output_tokens", False, f"Request error: {e}")


# ---------------------------------------------------------------------------
# Test B & C: sequence_number + reasoning_text (combined streaming test)
# ---------------------------------------------------------------------------
def test_streaming():
    print("--- Test B: sequence_number in SSE stream ---")
    print("--- Test C: reasoning_text content parts ---")
    url = f"{UPSTREAM}/v1/responses"
    payload = {
        "model": MODEL,
        "input": "Think step by step: what is 17 * 23? Show your reasoning.",
        "stream": True,
    }

    events = []
    missing_seq = []
    reasoning_events = []
    raw_lines = []

    try:
        with httpx.Client(verify=False, timeout=TIMEOUT) as c:
            with c.stream("POST", url, json=payload) as resp:
                if resp.status_code != 200:
                    detail = f"HTTP {resp.status_code}"
                    report("2", "sequence_number", False, f"Streaming request failed: {detail}")
                    report("3", "reasoning_text", False, f"Streaming request failed: {detail}")
                    return

                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if not data_str or data_str == "[DONE]":
                        continue
                    raw_lines.append(data_str)
                    try:
                        obj = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(obj, dict):
                        continue
                    events.append(obj)

                    if "sequence_number" not in obj:
                        missing_seq.append(obj.get("type", "<unknown>"))

                    evt_type = obj.get("type", "")
                    if evt_type in ("response.content_part.added", "response.content_part.done"):
                        part = obj.get("part", {})
                        if isinstance(part, dict) and part.get("type") == "reasoning_text":
                            reasoning_events.append(evt_type)

    except Exception as e:
        report("2", "sequence_number", False, f"Stream error: {e}")
        report("3", "reasoning_text", False, f"Stream error: {e}")
        return

    if not events:
        report("2", "sequence_number", False, "No SSE events received")
        report("3", "reasoning_text", False, "No SSE events received")
        return

    # Fix 2: sequence_number
    if missing_seq:
        unique_types = sorted(set(missing_seq))
        report("2", "sequence_number", False,
               f"{len(missing_seq)}/{len(events)} events missing sequence_number\n"
               f"Event types missing it: {', '.join(unique_types)}")
    else:
        report("2", "sequence_number", True,
               f"All {len(events)} events contain sequence_number")

    # Fix 3: reasoning_text
    if reasoning_events:
        report("3", "reasoning_text", False,
               f"{len(reasoning_events)} events with reasoning_text content parts found")
    else:
        report("3", "reasoning_text", True,
               f"No reasoning_text content parts in {len(events)} events")

    # Dump a sample of raw events for manual inspection
    print("  [INFO] Sample of first 5 SSE event types received:")
    for evt in events[:5]:
        seq = evt.get("sequence_number", "<MISSING>")
        print(f"         type={evt.get('type', '?')!r}  sequence_number={seq}")
    print()


# ---------------------------------------------------------------------------
# Test D: error nesting in response.failed
# ---------------------------------------------------------------------------
def test_error_nesting():
    print("--- Test D: error nesting in response.failed ---")
    url = f"{UPSTREAM}/v1/responses"
    payload = {
        "model": "nonexistent-model-that-should-fail-12345",
        "input": "hello",
        "stream": True,
    }

    try:
        with httpx.Client(verify=False, timeout=TIMEOUT) as c:
            with c.stream("POST", url, json=payload) as resp:
                if resp.status_code != 200:
                    try:
                        body = json.loads(resp.read().decode())
                    except Exception:
                        body = resp.read().decode()[:300]
                    report("4", "error nesting", True,
                           f"HTTP {resp.status_code} returned directly (not SSE): {json.dumps(body) if isinstance(body, dict) else body}")
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
                    if not isinstance(obj, dict):
                        continue

                    if obj.get("type") == "response.failed":
                        has_top_error = "error" in obj
                        nested_error = obj.get("response", {}).get("error") if isinstance(obj.get("response"), dict) else None

                        if has_top_error:
                            report("4", "error nesting", True,
                                   f"Error at top level as expected: {json.dumps(obj.get('error'))[:200]}")
                        elif nested_error:
                            report("4", "error nesting", False,
                                   f"Error nested in response.error (Goose won't see it): {json.dumps(nested_error)[:200]}")
                        else:
                            report("4", "error nesting", True,
                                   "response.failed event found but no error object anywhere (unexpected)")
                        return

        report("4", "error nesting", True,
               "No response.failed event received (error returned as HTTP status, not SSE — no nesting issue)")

    except Exception as e:
        report("4", "error nesting", False, f"Request error: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Target: {UPSTREAM}")
    print(f"Model:  {MODEL}")
    print()

    test_max_output_tokens()
    test_streaming()
    test_error_nesting()

    print("=" * 55)
    print("  Llama Stack Compatibility Report")
    print("=" * 55)
    for fix_id in ("1", "2", "3", "4"):
        if fix_id in RESULTS:
            name, passed, _ = RESULTS[fix_id]
            status = "PASS — no longer needed" if passed else "FAIL — STILL NEEDED"
            print(f"  Fix {fix_id} ({name:20s}):  {status}")
    print("=" * 55)

    all_pass = all(passed for _, passed, _ in RESULTS.values())
    if all_pass:
        print("\n  All fixes passed. The proxy can likely be REMOVED entirely.")
        print("  Next: test Goose end-to-end pointing directly at Llama Stack.")
    else:
        needed = [f"Fix {fid} ({name})" for fid, (name, passed, _) in RESULTS.items() if not passed]
        print(f"\n  Proxy is STILL NEEDED for: {', '.join(needed)}")
        print("  Consider simplifying llm_proxy.py to only these fixes.")
    print()
