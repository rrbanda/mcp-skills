#!/bin/bash
#
# cleanup.sh — Remove all demo resources.
#
# Usage:
#   ./demo/cleanup.sh

set -euo pipefail

NAMESPACE="sandbox-devspaces"

echo "=== Cleaning up Secure Agent Sandbox Demo ==="
echo ""

echo "1. Deleting SandboxClaims..."
oc delete sandboxclaim --all -n "$NAMESPACE" 2>/dev/null || true

echo "2. Deleting SandboxWarmPool..."
oc delete sandboxwarmpool --all -n "$NAMESPACE" 2>/dev/null || true

echo "3. Waiting for warm pool sandboxes to terminate..."
sleep 5

echo "4. Deleting SandboxTemplate..."
oc delete sandboxtemplate --all -n "$NAMESPACE" 2>/dev/null || true

echo "5. Deleting remaining Sandboxes..."
oc delete sandbox --all -n "$NAMESPACE" 2>/dev/null || true

echo "6. Deleting NetworkPolicies..."
oc delete networkpolicy --all -n "$NAMESPACE" 2>/dev/null || true

echo "7. Deleting any Routes and Services..."
oc delete route --all -n "$NAMESPACE" 2>/dev/null || true
oc delete svc -l app.kubernetes.io/part-of=agent-sandbox-demo -n "$NAMESPACE" 2>/dev/null || true

echo ""
echo "=== Cleanup Complete ==="
echo "Namespace $NAMESPACE still exists. To remove it: oc delete namespace $NAMESPACE"
