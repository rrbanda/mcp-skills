#!/bin/bash
#
# setup.sh — Create all demo resources for Secure AI Agent Sandbox demo.
#
# Prerequisites:
#   1. oc login to your OpenShift cluster
#   2. agent-sandbox operator installed (oc get pods -n agent-sandbox-system)
#   3. OpenShift Sandboxed Containers operator installed with KataConfig
#
# Usage:
#   ./demo/setup.sh

set -euo pipefail

NAMESPACE="sandbox-devspaces"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Secure Agent Sandbox Demo Setup ==="
echo ""

echo "1. Verifying prerequisites..."
echo -n "   agent-sandbox controller: "
if oc get pods -n agent-sandbox-system --no-headers 2>/dev/null | grep -q Running; then
  echo "RUNNING"
else
  echo "NOT FOUND — install agent-sandbox first"
  echo "   oc apply -f https://github.com/kubernetes-sigs/agent-sandbox/releases/download/v0.2.1/manifest.yaml"
  echo "   oc apply -f https://github.com/kubernetes-sigs/agent-sandbox/releases/download/v0.2.1/extensions.yaml"
  exit 1
fi

echo -n "   kata-remote RuntimeClass: "
if oc get runtimeclass kata-remote &>/dev/null; then
  echo "AVAILABLE"
else
  echo "NOT FOUND — install OpenShift Sandboxed Containers operator and create KataConfig"
  echo "   Continuing without Kata (sandboxes will use standard container runtime)"
  echo "   To add Kata later, just update the SandboxTemplate runtimeClassName"
fi
echo ""

echo "2. Creating namespace $NAMESPACE..."
oc create namespace "$NAMESPACE" 2>/dev/null || echo "   Namespace already exists"
echo ""

echo "3. Granting SCC permissions (OpenShift only)..."
oc adm policy add-scc-to-user anyuid -z agent-sandbox-controller -n agent-sandbox-system 2>/dev/null || true
oc adm policy add-scc-to-user anyuid -z default -n "$NAMESPACE" 2>/dev/null || true
echo ""

echo "4. Creating SandboxTemplate..."
oc apply -f "$SCRIPT_DIR/sandbox-template.yaml"
echo ""

echo "5. Creating SandboxWarmPool (3 replicas)..."
oc apply -f "$SCRIPT_DIR/sandbox-warmpool.yaml"
echo ""

echo "6. Applying NetworkPolicy for egress isolation..."
oc apply -f "$SCRIPT_DIR/sandbox-networkpolicy.yaml"
echo ""

echo "7. Waiting for warm pool pods..."
echo -n "   "
for i in $(seq 1 30); do
  READY=$(oc get sandbox -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l | tr -d ' ')
  if [[ "$READY" -ge 1 ]]; then
    echo ""
    echo "   $READY sandbox(es) ready"
    break
  fi
  echo -n "."
  sleep 5
done
echo ""

echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Create a sandbox claim:  oc apply -f $SCRIPT_DIR/sandbox-claim.yaml"
echo "  2. Execute in the sandbox:  $SCRIPT_DIR/sandbox-exec.sh python3 -c \"print('hello')\""
echo "  3. View sandbox pods:       oc get sandbox,pod -n $NAMESPACE"
echo ""
