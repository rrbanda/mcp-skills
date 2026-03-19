#!/bin/bash
#
# sandbox-exec.sh — Bridge for executing commands in an Agent Sandbox pod.
#
# Usage from DevSpaces workspace:
#   ./sandbox-exec.sh <command> [args...]
#   ./sandbox-exec.sh python3 -c "print('hello from sandbox')"
#   ./sandbox-exec.sh bash -c "whoami && hostname && cat /etc/os-release"
#
# Environment variables:
#   SANDBOX_POD       — Name of the sandbox pod (default: auto-detect from SandboxClaim)
#   SANDBOX_NAMESPACE — Namespace of the sandbox pod (default: sandbox-devspaces)
#   SANDBOX_CONTAINER — Container name inside the sandbox pod (default: agent-sandbox)

set -euo pipefail

SANDBOX_NAMESPACE="${SANDBOX_NAMESPACE:-sandbox-devspaces}"
SANDBOX_CONTAINER="${SANDBOX_CONTAINER:-agent-sandbox}"

if [[ -z "${SANDBOX_POD:-}" ]]; then
  SANDBOX_NAME=$(oc get sandboxclaim -n "$SANDBOX_NAMESPACE" -o jsonpath='{.items[0].status.sandbox.Name}' 2>/dev/null || true)
  if [[ -n "$SANDBOX_NAME" ]]; then
    SANDBOX_POD=$(oc get sandbox "$SANDBOX_NAME" -n "$SANDBOX_NAMESPACE" -o jsonpath='{.metadata.annotations.agents\.x-k8s\.io/pod-name}' 2>/dev/null || true)
  fi
  if [[ -z "$SANDBOX_POD" ]]; then
    SANDBOX_POD=$(oc get sandbox -n "$SANDBOX_NAMESPACE" -o jsonpath='{.items[0].metadata.annotations.agents\.x-k8s\.io/pod-name}' 2>/dev/null || true)
  fi
  if [[ -z "$SANDBOX_POD" ]]; then
    echo "ERROR: No sandbox pod found. Create a SandboxClaim first:" >&2
    echo "  oc apply -f demo/sandbox-claim.yaml" >&2
    exit 1
  fi
fi

if [[ $# -eq 0 ]]; then
  echo "Usage: sandbox-exec.sh <command> [args...]" >&2
  echo "" >&2
  echo "Sandbox pod: $SANDBOX_POD (namespace: $SANDBOX_NAMESPACE)" >&2
  exit 1
fi

exec oc exec "$SANDBOX_POD" -n "$SANDBOX_NAMESPACE" -c "$SANDBOX_CONTAINER" -- "$@"
