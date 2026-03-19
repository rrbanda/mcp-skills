# Secure AI Coding Agents: DevSpaces + Agent Sandbox on OpenShift

---

## 1. The Problem: AI Agents Execute Untrusted Code

AI coding agents (Goose, Claude Code, Gemini CLI, Copilot) don't just suggest code -- they **execute** it. They run shell commands, install packages, modify files, and call APIs with the same permissions as the developer. This creates a new class of security risk that traditional development environments weren't designed for.

### What can go wrong

| Risk | What happens | Real incident |
|------|-------------|---------------|
| **Prompt injection** | Malicious content in files/issues tricks the agent into running harmful commands | [Clinejection](https://adnanthekhan.com/posts/clinejection/) -- a GitHub issue title exploited an AI triage bot, compromising Cline's npm releases and affecting ~4,000 developer machines |
| **Credential theft** | Agent reads `~/.ssh/id_rsa`, `~/.aws/credentials`, `.env` files and exfiltrates them | [Kilo Code CVE-2025-11445](https://mcpsec.dev/advisories/2025-10-02-kilo-code-ai-agent-supply-chain-attack/) -- malicious prompts manipulated the agent to modify security settings and push unauthorized git commits |
| **Supply chain poisoning** | Malicious agent skills/plugins contain hidden payloads | [ClawHavoc](https://simonroses.com/2026/02/ai-agent-skill-poisoning-the-supply-chain-attack-you-havent-heard-of/) -- 12% of skills on OpenClaw marketplace contained base64-encoded credential-harvesting payloads |
| **Command injection** | Pre-approved tools like `git`, `grep` are exploited via argument injection | [Trail of Bits](https://blog.trailofbits.com/2025/10/22/prompt-injection-to-rce-in-ai-agents/) -- demonstrated RCE across three popular AI agent platforms through argument injection on approved commands |
| **Resource abuse** | Agent runs fork bombs, infinite loops, or mines crypto | Standard container escape risk when agents have unrestricted execution |

### The planning-execution split

The key insight is that agents have two phases, with very different risk profiles:

| Phase | What it does | Risk |
|-------|-------------|------|
| **Planning** | Reads code, reasons about changes, generates plans | **Safe** -- no side effects |
| **Execution** | Runs commands, writes files, calls APIs | **Dangerous** -- real system impact |

Sandboxing the execution phase while leaving the planning phase unrestricted gives agents the autonomy they need while containing the blast radius of anything that goes wrong. Studies show sandboxed agents reduce security incidents by ~90% ([Zylos Research](https://zylos.ai/research/2026-02-21-ai-agent-sandbox-execution-isolation)).

---

## 2. How the Industry Solves This

Every major AI platform has converged on the same pattern: **isolate agent code execution from the developer environment**.

### Anthropic (Claude Code)

Two-layer isolation: filesystem (bubblewrap on Linux, Seatbelt on macOS) + network (proxy restricting outbound connections). The agent can only access the working directory and approved domains. Result: 84% fewer permission prompts.

When running Claude Code on the web, each session gets an isolated cloud sandbox. Credentials (git tokens, signing keys) are never stored inside the sandbox -- they're injected through a validated proxy.

Open source: [anthropic-experimental/sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime)

### Google (Gemini CLI + Agent Sandbox)

Two approaches:
- **Local**: Gemini CLI uses Seatbelt (macOS) or Docker/Podman containers for isolation
- **Kubernetes**: [agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) -- a SIG-Apps project providing a `Sandbox` CRD for isolated, stateful, singleton workloads. Supports gVisor and Kata Containers for VM-level isolation. Includes WarmPool for sub-second sandbox allocation.

Google's motivation: "Autonomous AI agents generate and execute untrusted, unverified code. The security gap is how to safely allow agents to run code in mission-critical environments with proprietary data." ([Google Open Source Blog](https://opensource.googleblog.com/2025/11/unleashing-autonomous-ai-agents-why-kubernetes-needs-a-new-standard-for-agent-execution.html))

### GitHub / Microsoft (Copilot)

GitHub Copilot's coding agent uses **GitHub Actions as the compute sandbox**. Each task boots an ephemeral VM, clones the repo, and executes. All work appears as commits on a draft PR -- a human must approve before anything merges. VS Code adds terminal sandboxing that restricts file system and network access for agent-executed commands.

### OpenAI (Codex)

Code Interpreter runs in a fully sandboxed virtual machine. GPT-5.1-Codex-Max uses sandbox isolation as a product-level mitigation with configurable network access controls.

### E2B, Daytona, Modal

Cloud sandbox providers using Firecracker microVMs (E2B, <200ms cold start), gVisor (Modal, 50k+ concurrent sandboxes), or custom runtimes (Daytona, <90ms creation). All provide SDK/API for agents to execute code in isolated environments.

### The pattern

Every approach follows the same architecture:

```
┌──────────────────────┐          ┌──────────────────────┐
│  Developer / Agent   │          │  Execution Sandbox   │
│  Environment         │          │                      │
│                      │          │  - Isolated runtime  │
│  - IDE / Editor      │  ──────> │  - No credentials    │
│  - AI Agent          │  code    │  - Network restricted │
│  - Planning phase    │  exec    │  - Disposable        │
│  - Credentials       │  ──────> │  - VM-level isolation│
│                      │          │                      │
└──────────────────────┘          └──────────────────────┘
       TRUSTED                          UNTRUSTED
```

---

## 3. The Enterprise Gap

The cloud sandbox providers (E2B, Modal, Daytona) solve this for SaaS. But enterprises need:

- **On-premises execution** -- code can't leave the network
- **Existing identity/auth** -- OIDC, LDAP, RBAC from the enterprise IdP
- **Compliance** -- audit trails, data residency, approved base images
- **Integration** -- with existing CI/CD, GitOps, container registries
- **Multi-tenancy** -- hundreds of developers, each with isolated sandboxes

This is where **DevSpaces + Agent Sandbox on OpenShift** fits.

---

## 4. The Vision: DevSpaces Workspace with Secure Agent Execution

### What it looks like

A developer opens a DevSpaces workspace. It comes pre-configured with:
- **Che Code** (VS Code in browser) as the IDE
- **A coding agent** (Goose, Claude Code, or similar) pre-installed
- **Agent Sandbox** as the execution backend -- when the agent runs code, it executes in an isolated pod with Kata or gVisor runtime

```
┌─────────────────────────────────────────────────────────────────┐
│  OpenShift Cluster                                              │
│                                                                 │
│  ┌─────────────────────────────┐  ┌──────────────────────────┐  │
│  │  DevSpaces Workspace        │  │  Agent Sandbox Pod       │  │
│  │                             │  │  (Kata / gVisor runtime) │  │
│  │  Che Code IDE               │  │                          │  │
│  │  ┌───────────────────────┐  │  │  ┌────────────────────┐  │  │
│  │  │  Coding Agent (Goose) │──┼──┼─>│  Code Execution    │  │  │
│  │  │  - Plans here (safe)  │  │  │  │  - Runs here       │  │  │
│  │  │  - Has credentials    │  │  │  │  - No credentials  │  │  │
│  │  └───────────────────────┘  │  │  │  - Network locked  │  │  │
│  │                             │  │  │  - Disposable       │  │  │
│  │  /projects (persistent)     │  │  └────────────────────┘  │  │
│  │  OIDC auth via Che gateway  │  │                          │  │
│  │  Devfile-driven config      │  │  NetworkPolicy: deny all │  │
│  └─────────────────────────────┘  │  except DevSpaces pod    │  │
│                                   └──────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────┐                                   │
│  │  SandboxWarmPool         │                                   │
│  │  Pre-warmed pods ready   │                                   │
│  │  for instant allocation  │                                   │
│  └──────────────────────────┘                                   │
└─────────────────────────────────────────────────────────────────┘
```

### What each component provides

| Component | Role | What it handles |
|-----------|------|----------------|
| **DevSpaces** | Developer experience | IDE, devfiles, OIDC auth, dashboard, project clone, persistent storage, self-service workspace creation |
| **Coding Agent** | AI assistant | Code understanding, planning, code generation, tool use |
| **Agent Sandbox** | Secure execution | Isolated code execution with VM-level isolation (Kata/gVisor), NetworkPolicy, lifecycle management |
| **SandboxWarmPool** | Performance | Pre-warmed pods for sub-second sandbox allocation (no cold-start penalty) |
| **SandboxTemplate** | Security policy | Defines allowed resources, network rules, runtime class -- enforced by the controller |

### Why this is better than each piece alone

| Compared to | What's missing | What this adds |
|-------------|---------------|---------------|
| **DevSpaces alone** | No execution isolation -- agent runs code in the workspace pod with full access | Agent Sandbox provides VM-level isolation for code execution |
| **Agent Sandbox alone** | No IDE, no devfiles, no auth, no dashboard | DevSpaces provides the full developer experience |
| **E2B / Modal / Daytona** | SaaS only, code leaves the network | Everything runs on-premises on OpenShift |
| **Claude Code local sandbox** | Single-machine, no enterprise controls | Multi-tenant, RBAC, audit, compliance on Kubernetes |

### How the agent uses the sandbox

The coding agent in the DevSpaces workspace delegates code execution to the Agent Sandbox pod. This can work through:

1. **`oc exec`** -- the simplest approach. The agent runs `oc exec <sandbox-pod> -- <command>` to execute code in the sandbox. Works today with no additional tooling.

2. **Agent Sandbox Python SDK** -- the agent uses `SandboxClient.run(command)` to execute code, `write()` to upload files, `read()` to download results. The SDK handles sandbox lifecycle automatically.

3. **MCP server** -- a thin MCP server wraps the SDK, so agents that support MCP (Goose, Claude Code) can use the sandbox as a tool without modification.

### Security properties

| Property | How it's enforced |
|----------|------------------|
| **Kernel isolation** | Kata Containers (lightweight VM) or gVisor (user-space kernel) via `runtimeClassName` |
| **No credentials** | Sandbox pod has no service account token (`automountServiceAccountToken: false`), no mounted secrets |
| **Network lockdown** | SandboxTemplate NetworkPolicy: default deny, only allow ingress from the DevSpaces workspace pod |
| **Resource limits** | CPU/memory limits in the SandboxTemplate prevent resource abuse |
| **Disposable** | Sandbox can be destroyed and recreated after each task. WarmPool provides instant replacement |
| **Filesystem isolation** | Separate PVC from the workspace. Agent can't access workspace credentials or config |
| **Audit trail** | OpenShift audit logging captures all `oc exec` and API calls to the sandbox |

---

## 5. Validated on OpenShift 4.20

The following was validated on an OpenShift 4.20.14 cluster with DevSpaces 3.26.1.

### What we proved works

| Test | Result |
|------|--------|
| Install agent-sandbox v0.2.1 alongside DevSpaces | **Works** -- both operators coexist, no conflicts |
| Create Sandbox pod with UDI image + goose | **Works** -- same image as DevSpaces workspace |
| Project clone via init container | **Works** -- `alpine/git` clones to PVC |
| IDE (code-server) in Sandbox pod | **Works** -- accessible via OpenShift Route |
| Goose CLI available in Sandbox | **Works** -- goose 1.27.2, FastMCP, Goose VS Code extension |
| Stop/resume with persistence | **Works** -- `replicas 0→1` preserves PVC data |
| Environment variables | **Works** -- GOOSE/OPENAI/LLAMA vars set correctly |

### What needs additional work

| Item | Status | Path forward |
|------|--------|-------------|
| **Kata runtime** | Not available on this cluster | Install OpenShift Sandboxed Containers operator, create KataConfig |
| **gVisor** | Not available on this cluster | gVisor is primarily a GKE feature; on OpenShift, Kata is the standard |
| **Agent → Sandbox delegation** | Not wired | Build MCP server or use `oc exec` bridge from DevSpaces workspace |
| **SandboxTemplate NetworkPolicy** | Not tested | Create template with deny-all + allow from DevSpaces namespace |
| **WarmPool** | Not tested | Create SandboxWarmPool referencing a SandboxTemplate |

### Cluster access

- **Console**: https://console-openshift-console.apps.ocp.v7hjl.sandbox2288.opentlc.com
- **Sandbox namespace**: `sandbox-devspaces`
- **Agent Sandbox controller**: `agent-sandbox-system`

---

## 6. Comparison: How This Maps to Industry Approaches

| Aspect | Anthropic (Claude Code) | Google (Agent Sandbox) | GitHub (Copilot) | **DevSpaces + Agent Sandbox** |
|--------|------------------------|----------------------|-----------------|-------------------------------|
| **IDE** | Terminal / VS Code local | VS Code in sandbox | github.com / VS Code | Che Code in DevSpaces |
| **Agent** | Claude Code | Gemini CLI | Copilot | Goose (or any agent) |
| **Execution isolation** | bubblewrap / Seatbelt | gVisor / Kata on GKE | GitHub Actions VM | Kata / gVisor on OpenShift |
| **Credential handling** | Proxy-injected, not in sandbox | No built-in | Branch protections | OIDC via Che gateway, not in sandbox |
| **Network controls** | Proxy allowlist | NetworkPolicy | VM network isolation | SandboxTemplate NetworkPolicy |
| **Warm pools** | N/A | SandboxWarmPool | N/A | SandboxWarmPool |
| **Multi-tenant** | Single user | Kubernetes RBAC | GitHub orgs | OpenShift RBAC + DevSpaces namespaces |
| **On-premises** | Yes (local) | GKE only | GitHub.com (SaaS) | **Yes -- fully on-premises** |
| **Devfile support** | No | No | No | **Yes -- DevSpaces devfiles** |
| **Self-service** | CLI | kubectl | GitHub UI | **Che Dashboard** |

---

## 7. Next Steps

1. **Install OpenShift Sandboxed Containers** operator to enable Kata runtime on the cluster
2. **Create a SandboxTemplate** with Kata runtime, deny-all NetworkPolicy, and no service account token
3. **Build the agent-to-sandbox bridge** -- MCP server or `oc exec` wrapper that the coding agent uses to delegate execution
4. **Create a devfile** that pre-installs the coding agent and sandbox bridge in every DevSpaces workspace
5. **Test with WarmPool** -- pre-warm sandbox pods for instant agent execution
6. **Upstream contribution** -- propose the DevSpaces + Agent Sandbox pattern to both communities

---

## 8. References

### Research and security
- [NVIDIA: Practical Security Guidance for Sandboxing Agentic Workflows](https://developer.nvidia.com/blog/practical-security-guidance-for-sandboxing-agentic-workflows-and-managing-execution-risk/)
- [Zylos: AI Agent Code Execution Sandboxing](https://zylos.ai/research/2026-01-24-ai-agent-code-execution-sandboxing)
- [Trail of Bits: Prompt Injection to RCE in AI Agents](https://blog.trailofbits.com/2025/10/22/prompt-injection-to-rce-in-ai-agents/)
- [Pillar Security: Your AI Agent Will Run Untrusted Code](https://www.pillar.security/blog/your-ai-agent-will-run-untrusted-code-now-what)

### Vendor approaches
- [Anthropic: Claude Code Sandboxing](https://www.anthropic.com/engineering/claude-code-sandboxing)
- [Google: Why Kubernetes Needs Agent Sandbox](https://opensource.googleblog.com/2025/11/unleashing-autonomous-ai-agents-why-kubernetes-needs-a-new-standard-for-agent-execution.html)
- [GitHub: Copilot Coding Agent](https://docs.github.com/en/copilot/concepts/coding-agent/coding-agent)
- [OpenAI: Codex Sandboxing](https://developers.openai.com/codex/concepts/sandboxing)

### Projects
- [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) (v0.2.1)
- [anthropic-experimental/sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime)
- [E2B](https://e2b.dev/ai-agents) | [Daytona](https://www.daytona.io/) | [Modal](https://modal.com/products/sandboxes)
- [DevWorkspace Operator](https://github.com/devfile/devworkspace-operator)
- [Red Hat Dev Spaces](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces)
