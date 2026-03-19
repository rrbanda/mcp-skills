# Clean-Slate Workshop Walkthrough Report (Run 2)

**Date**: 2026-03-19  
**Cluster**: OpenShift 4.20.14 / Kubernetes 1.33.6 on AWS (us-east-2)  
**Agent Sandbox**: v0.2.1  
**Previous run**: Found 6 critical bugs + 11 additional issues. All were fixed. Repo was then restructured (renamed `site.yml`, removed orphans, moved `docs/` to `research/`).  
**Purpose**: Validate that everything works end-to-end after all fixes and the repo restructure.

## Summary

| Phase | Module | Result | New Issues | Notes |
|-------|--------|--------|-----------|-------|
| 0 | Teardown | PASS | 0 | Cleaned all CRDs, operator, namespace. Namespace stuck in Terminating (finalizer issue from old Kata VMs) -- force-cleaned via finalize API. |
| 1 | Antora Build | PASS | 0 | `npx antora site.yml` -- 13 pages generated, zero errors. Rename from `github-pages.yml` works correctly. |
| 2 | Module 0: Prerequisites | PASS | 0 | `oc whoami` = admin, OCP 4.20.14, 5 DevSpaces pods healthy. |
| 3 | Modules 1-3: Concepts | PASS | 0 | `printenv` shows env vars, `curl httpbin.org` returns IP, repos clone, `oc get sandboxtemplates` confirms clean slate. |
| 4 | Module 4: Setup | PASS | 0 | All 7 steps work in order: operator, extensions, namespace, SCC grants, template, warmpool, networkpolicy. 3 warm pool pods Running after ~4 min (Kata VM startup). |
| 5 | Module 6: Secure Execution | PASS | 0 | SandboxClaim binds, `sandbox-exec.sh` works, all 4 isolation tests pass, disposable sandbox test passes. |
| 6 | Modules 5/7/8: Goose Content | PASS | 0 | All referenced files exist. Recipe `--params` keys match adoc exactly. `.goosehints` content matches Module 5 output. |
| 7 | Module 9: Orchestrator | PASS | 0 | Recipe well-formed YAML. Goosehints file exists (421 lines). Parameter keys match adoc. |
| 8 | Module 10: Cleanup | PASS | 0 | `cleanup.sh` removes all resources (claims, warmpool, template, networkpolicy, sandboxes). Pods terminate. |

**Overall: 0 new issues found. All previously fixed bugs remain fixed. Workshop is fully functional.**

## Phase Details

### Phase 0: Teardown

```
./demo/cleanup.sh              -- removed NetworkPolicy "sandbox-isolation"
oc delete namespace sandbox-devspaces  -- namespace deleted
oc delete -f .../extensions.yaml       -- 3 CRDs + ClusterRole + ClusterRoleBinding deleted
oc delete -f .../manifest.yaml         -- namespace, SA, deployment, CRD, ClusterRole deleted
```

Namespace stuck in `Terminating` due to old Kata VM pods failing `KillPodSandbox`. Resolved by patching finalizers via `/api/v1/namespaces/sandbox-devspaces/finalize`.

### Phase 1: Antora Site Build

```
npx antora site.yml
```

13 pages generated:
- `gh-pages/404.html`
- `gh-pages/index.html`
- `gh-pages/secure-ai-agents-workshop/v1.0/index.html`
- `gh-pages/secure-ai-agents-workshop/v1.0/01-the-problem.html` through `10-wrapup.html`

Zero build errors or warnings.

### Phase 2: Prerequisites

| Check | Result |
|-------|--------|
| `oc whoami` | `admin` |
| Client version | 4.20.1 |
| Server version | 4.20.14 |
| Kubernetes | v1.33.6 |
| DevSpaces pods | 5/5 Running (che-gateway, devspaces, dashboard, operator, devworkspace-controller) |

### Phase 3: Modules 1-3

| Test | Result |
|------|--------|
| `printenv \| grep -i key` | Shows env vars (AWS keys visible on host -- confirms the risk Module 1 teaches about) |
| `curl https://httpbin.org/ip` | Returns `{"origin": "108.77.162.145"}` |
| SA token (`cat /var/run/secrets/...`) | "not in a pod" (correct for local terminal) |
| `git clone sandbox-runtime` | Cloned to `/tmp/sandbox-runtime` |
| `git clone agent-sandbox` | Cloned to `/tmp/agent-sandbox` |
| `oc get sandboxtemplates` | "Agent Sandbox not yet installed" (correct -- clean slate) |

### Phase 4: Module 4 Setup

All 7 steps executed in sequence:

1. `oc apply -f .../manifest.yaml` -- namespace, SA, CRD, deployment created
2. `oc apply -f .../extensions.yaml` -- 3 extension CRDs, ClusterRole created
3. `oc create namespace sandbox-devspaces` -- created
4. SCC grants:
   - `oc adm policy add-scc-to-user anyuid -z agent-sandbox-controller -n agent-sandbox-system` -- added
   - `oc adm policy add-scc-to-user anyuid -z default -n sandbox-devspaces` -- added
5. `oc apply -f demo/sandbox-template.yaml` -- `secure-agent-sandbox` created
6. `oc apply -f demo/sandbox-warmpool.yaml` -- `agent-sandbox-pool` created
7. `oc apply -f demo/sandbox-networkpolicy.yaml` -- `sandbox-isolation` created

Verification:
- 4 CRDs registered (sandboxes, sandboxclaims, sandboxtemplates, sandboxwarmpools)
- Controller pod: `agent-sandbox-controller-8484c7bc74-7d85s` Running 1/1
- RuntimeClass: `kata-remote` (handler: `kata-remote`)
- Warm pool pods: 3/3 Running after ~4 minutes (Kata peer-pod VM startup)

### Phase 5: Module 6 Secure Execution

| Test | Expected | Actual | Result |
|------|----------|--------|--------|
| SandboxClaim binding | Bound with status Ready | `message: Pod is Ready; Service Exists`, `reason: DependenciesReady` | PASS |
| Basic exec (`print('Hello')`) | "Hello from secure sandbox!" | "Hello from secure sandbox!" | PASS |
| Env vars (`printenv \| grep key`) | No credential env vars | Only `SDKMAN_CANDIDATES_API` (a URL, not a secret) | PASS |
| Network egress (`curl httpbin.org`) | Blocked/timeout | Blocked (timeout after 15s) | PASS |
| SA token mount | Not found | `No such file or directory` | PASS |
| RuntimeClass | `kata-remote` | `kata-remote` | PASS |
| Disposable sandbox (delete + recreate) | New sandbox works | "Hello from fresh sandbox!" | PASS |

### Phase 6: Modules 5/7/8 Content Verification

| Check | Result |
|-------|--------|
| `skills/create-fastmcp-server.yaml` exists | Yes (155 lines) |
| `skills/deploy-fastmcp-server.yaml` exists | Yes (153 lines) |
| `skills/deploy-agent-sandbox.yaml` exists | Yes (224 lines) |
| `skills/create-orchestrator-workflow.yaml` exists | Yes (207 lines) |
| `.goosehints` exists | Yes (165 lines) |
| `skills/agent-sandbox.goosehints` exists | Yes |
| `skills/orchestrator-workflow.goosehints` exists | Yes (421 lines) |
| Module 5 recipe list matches `ls skills/*.yaml` | Exact match (4 files) |
| Module 5 `.goosehints` excerpt matches actual file | Lines 1-20 match exactly |
| Module 7 `--params output_filename=, server_name=` | Matches recipe keys |
| Module 7 `--params server_file=, namespace=, image_name=` | Matches recipe keys |
| Module 4 `--params namespace=, warmpool_replicas=` | Matches recipe keys |

### Phase 7: Module 9 Orchestrator Verification

| Check | Result |
|-------|--------|
| `skills/create-orchestrator-workflow.yaml` valid YAML | Yes (python3 yaml.safe_load passes) |
| Recipe parameters: `project_name` (required) | Matches adoc |
| Recipe parameters: `workflow_id` (required) | Matches adoc |
| Recipe parameters: `workflow_description` (optional) | Matches adoc TIP |
| `skills/orchestrator-workflow.goosehints` exists | Yes (421 lines) |
| Recipe references goosehints | Yes (1 reference) |

### Phase 8: Module 10 Cleanup

```
=== Cleaning up Secure Agent Sandbox Demo ===
1. Deleting SandboxClaims...        sandboxclaim "my-agent-sandbox" deleted
2. Deleting SandboxWarmPool...      sandboxwarmpool "agent-sandbox-pool" deleted
3. Waiting for warm pool sandboxes to terminate...
4. Deleting SandboxTemplate...      sandboxtemplate "secure-agent-sandbox" deleted
5. Deleting remaining Sandboxes...  No resources found
6. Deleting NetworkPolicies...      networkpolicy "sandbox-isolation" deleted
7. Deleting any Routes/Services...  No resources found
=== Cleanup Complete ===
```

Post-cleanup verification:
- SandboxClaims: `No resources found`
- WarmPool: `No resources found`
- SandboxTemplate: `No resources found`
- NetworkPolicy: `No resources found`
- Sandboxes: `No resources found`

## Items Not Testable from CLI

These modules require an interactive Goose AI agent session inside a DevSpaces workspace:

- **Module 5**: `goose session` interactive prompt, VS Code extension install
- **Module 7**: MCP server generation via `goose run --recipe skills/create-fastmcp-server.yaml`
- **Module 7**: MCP server deployment via `goose run --recipe skills/deploy-fastmcp-server.yaml`
- **Module 8**: Full MCP server testing flow (curl, `goose configure`, Goose interactions)
- **Module 9**: Workflow generation via `goose run --recipe skills/create-orchestrator-workflow.yaml`

All referenced files, recipe parameters, and goosehints content have been verified to be correct and consistent with the adoc documentation.

## Comparison with Previous Run

| Metric | Run 1 | Run 2 (this run) |
|--------|-------|-------------------|
| Critical bugs | 6 | 0 |
| Additional issues | 11 | 0 |
| Fixes applied | 17 | 0 |
| Antora build | PASS (after rename) | PASS |
| Operator install | PASS (after SCC fix) | PASS |
| Isolation tests | PASS (after NP + exec fix) | PASS |
| Cleanup | PASS (after NP fix) | PASS |

All 17 fixes from Run 1 remain effective. No regressions found.
