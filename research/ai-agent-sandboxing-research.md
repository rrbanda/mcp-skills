# Comprehensive Research: Sandboxing for AI Coding Agents

**Research Date:** March 18, 2026  
**Scope:** Security landscape, vendor approaches, and technical implementations for AI agent sandboxing

---

## 1. Why Do AI Coding Agents Need Sandboxes?

### 1.1 Core Risks AI Agents Pose When Executing Code

AI coding agents introduce a significant attack surface because they **run tools with the same permissions and entitlements as developers**—effectively acting as computer-use agents with elevated privileges. The primary risks include:

| Risk Category | Description |
|---------------|-------------|
| **Security** | Indirect prompt injection, credential theft, data exfiltration, remote code execution (RCE) |
| **Data Exfiltration** | Access to `~/.ssh/id_rsa`, `~/.aws/credentials`, `~/.config/` API tokens, `.env` files |
| **Resource Abuse** | Fork bombs, memory exhaustion, CPU abuse |
| **Supply Chain Attacks** | Malicious skills, poisoned MCP configurations, compromised npm packages |
| **Container/Kernel Escapes** | Exploitation of shared kernel vulnerabilities |

### 1.2 Documented Incidents and Real-World Attacks

**Prompt Injection (OWASP #1 LLM Vulnerability)**
- Appears in **73% of production AI deployments**
- Attack success rates up to **84%** against current safety measures
- Source: [Zylos Research](https://zylos.ai/research/2026-01-24-ai-agent-code-execution-sandboxing)

**Kilo Code (CVE-2025-11445)**
- Malicious prompts in files manipulate AI agents to modify security settings and execute unauthorized git commands
- Enables automated code commits and pushes without user approval
- Source: [MCP Security Research](https://mcpsec.dev/advisories/2025-10-02-kilo-code-ai-agent-supply-chain-attack/)

**ClawHavoc / Skill Poisoning**
- 1,184+ malicious agent skills on OpenClaw marketplace
- Setup instructions contained base64-encoded payloads harvesting API tokens, SSH keys, AWS credentials
- Koi Security found **341 malicious skills out of 2,857** (~12%) in ClawHub
- Source: [Simon Roses Femerling](https://simonroses.com/2026/02/ai-agent-skill-poisoning-the-supply-chain-attack-you-havent-heard-of/)

**Clinejection (February 2026)**
- Single GitHub issue title exploited AI triage bot to compromise Cline's production releases
- Attacker published unauthorized `cline@2.3.0` to npm with postinstall script installing OpenClaw (full system access)
- **~4,000 developer machines** affected during 8-hour window
- Attack chain: prompt injection → arbitrary code execution → cache poisoning → credential theft → malicious publish
- Source: [Snyk Blog](https://snyk.io/blog/cline-supply-chain-attack-prompt-injection-github-actions/), [Adnan Khan Research](https://adnanthekhan.com/posts/clinejection/)

**Trail of Bits: Argument Injection to RCE**
- Pre-approved commands (`find`, `grep`, `git`) bypass human approval through **argument injection**
- Successful RCE demonstrated across three popular AI agent platforms
- Agents don't validate argument flags on pre-approved commands
- Source: [Trail of Bits Blog](https://blog.trailofbits.com/2025/10/22/prompt-injection-to-rce-in-ai-agents/)

**GitHub Actions / HackerBot-Claw**
- Systematic targeting of major repositories via `pull_request_target` workflows
- Poisoning Go init functions, injecting shell scripts, branch name command injection
- Exfiltration of `GITHUB_TOKEN`s and RCE
- Source: [Bastion Security](https://bastion.tech/blog/hackerbot-claw-ai-agent-supply-chain-attacks-github-actions/)

### 1.3 Planning vs. Execution: The Safety Distinction

The **planner-executor pattern** separates agent operations into two phases:

| Phase | Nature | Risk Level |
|-------|--------|------------|
| **Planning** | High-level goal decomposition, task identification, dependency mapping | **Safe**—no side effects, no code execution |
| **Execution** | Running commands, modifying files, API calls, tool invocations | **Dangerous**—actual system impact |

**Why execution is dangerous:**
- The executor carries out actions with real system access
- Each tool call can spawn subprocesses that bypass application-level controls
- "Bridging the gap between AI that can talk about doing something and AI that can reliably do something" is described as **"the hardest problem in modern AI"**
- Source: [Reliable Agentic Reasoning with Safe Autonomy (Medium)](https://medium.com/@vincentkalu02/reliable-agentic-reasoning-with-safe-autonomy-the-hardest-problem-in-modern-ai-321a05b13b2a)

**Safety benefits of separation:**
- Executor becomes a hardened adapter with rate limits, credential scoping, idempotency
- Plans are first-class artifacts—storable, diffable, replayable
- Enterprise controls: permissions, sandboxing, rate/budget limits, human approval at risk boundaries
- Source: [Planner-Executor Pattern Review](https://atoms.dev/insights/the-planner-executor-agent-pattern-a-comprehensive-review-of-its-architecture-evolution-applications-and-future-trends/74820b4ec2b4c07b977045175ded710)

### 1.4 Impact of Sandboxing

**Sandboxed agents reduce security incidents by ~90%** compared to agents with unrestricted access.
- Source: [Zylos Research](https://zylos.ai/research/2026-02-21-ai-agent-sandbox-execution-isolation)

---

## 2. How Does Anthropic Approach Sandboxing?

### 2.1 Claude Code Sandboxing (October 2025)

Anthropic released sandboxing features for Claude Code in October 2025 to enhance security and autonomy while reducing permission prompts.

**Key Features:**
- **Sandboxed Bash Tool**: Beta research preview—define which directories and network hosts the agent can access without container management
- **Open-source research preview**: [anthropic-experimental/sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime)
- **84% reduction in permission prompts** in internal usage
- Source: [Anthropic Engineering Blog](https://www.anthropic.com/engineering/claude-code-sandboxing)

### 2.2 Two-Layer Isolation Approach

**1. Filesystem Isolation**
- Restricts access to specific directories
- Claude can only modify files in the current working directory and subdirectories by default
- Blocks modification of sensitive system files

**2. Network Isolation**
- Controls access through a proxy server
- Claude can only connect to approved domains
- Prevents exfiltration of SSH keys or downloading malware

**Critical insight:** Both layers are required. Without network isolation, a compromised agent could exfiltrate sensitive files. Without filesystem isolation, it could escape the sandbox and gain network access.

### 2.3 Technical Implementation

| Platform | Technology |
|----------|------------|
| **Linux** | [bubblewrap](https://github.com/containers/bubblewrap) |
| **macOS** | Seatbelt |
| **WSL2** | bubblewrap |

**Claude Code on the Web:**
- Each session runs in an isolated cloud sandbox
- Sensitive credentials (git credentials, signing keys) never stored inside the sandbox
- Custom proxy for git operations—validates branch names, repository destinations, auth tokens
- Source: [Claude Code Docs](https://docs.claude.com/en/docs/claude-code/sandboxing)

### 2.4 Computer Use and Safety Features

- Permission-based architecture (read-only by default)
- Command blocklists (e.g., `curl`, `wget`)
- Input sanitization and static analysis before execution
- Prompt injection classifiers
- Human confirmation for consequential actions
- Source: [Anthropic Computer Use](https://anthropic.com/news/developing-computer-use), [Claude API Docs](https://docs.anthropic.com/en/docs/agents-and-tools/computer-use)

### 2.5 Secure Deployment Recommendations

- Dedicated VMs or containers with minimal privileges
- Limit internet access to allowlisted domains
- Avoid exposing sensitive credentials to the agent
- Require human approval for transactions and data access
- Source: [Anthropic Agent SDK](https://console.anthropic.com/docs/en/agent-sdk/secure-deployment)

### 2.6 Anthropic Partnerships

No explicit public documentation found for Anthropic partnerships with E2B or Modal. Sandboxing is implemented via open-source `sandbox-runtime` and OS-level primitives.

---

## 3. How Does Google Approach Sandboxing?

### 3.1 kubernetes-sigs/agent-sandbox Project

**Overview:** Formal Kubernetes subproject under SIG Apps, launched August 2025. Provides secure execution environment for autonomous AI agents on Kubernetes.

**Project Status (March 2026):**
- 1,300+ GitHub stars, 152 forks, 40+ contributors
- Latest release: v0.2.1 (March 2026)
- Official GKE integration documentation
- Source: [GitHub](https://github.com/kubernetes-sigs/agent-sandbox), [Project Site](https://agent-sandbox.sigs.k8s.io/)

### 3.2 Motivation and Design Philosophy

**The Problem:**
- Autonomous AI agents generate and execute **untrusted, unverified code**
- Security gap: how to safely allow agents to run code in mission-critical environments with proprietary data
- **Latency crisis**: Each tool call requires isolated sandbox; spin-up time is the bottleneck
- **Throughput**: Enterprise platforms need tens of thousands of parallel sandboxes, thousands of queries/second

**Why Kubernetes Needs a Sandbox CRD (vs. Deployments/StatefulSets):**
- Sandbox is a **lightweight VM-like abstraction** for single-instance, stateful, singleton workloads
- Designed for: AI agent runtimes, dev environments, notebooks
- Provides: stable identity, persistent storage, lifecycle management
- Backend-agnostic—supports gVisor, Kata Containers
- Standardized controller-based API avoids workarounds

**Source:** [Google Open Source Blog](https://opensource.googleblog.com/2025/11/unleashing-autonomous-ai-agents-why-kubernetes-needs-a-new-standard-for-agent-execution.html)

### 3.3 Core APIs

| Resource | Purpose |
|----------|---------|
| **Sandbox** | Core resource—isolated instance with stable identity, persistent storage |
| **SandboxTemplate** | Defines secure blueprint (resource limits, base image, security policies) |
| **SandboxClaim** | Transactional resource—users/frameworks request execution environment |

### 3.4 WarmPool and Cold-Start

**SandboxWarmPool** maintains a pool of pre-warmed Sandbox Pods:
- When `SandboxClaim` is created, Claim Controller adopts a pod from the WarmPool
- Pre-warmed pods are already initialized
- **Cold-start latency reduced to less than one second**
- WarmPool automatically replenishes after claims

**Note:** Security vulnerability documented—`spec.replicas` lacks upper limit, could enable Pod storm DoS (Issue #251).
- Source: [GKE Agent Sandbox Docs](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/agent-sandbox)

### 3.5 Use Cases (from agent-sandbox docs)

- Stateful code interpretation
- Agentic web browsing
- Computer use
- Sophisticated data analysis
- AI agent runtimes
- Development environments
- Notebooks

### 3.6 GKE Integration

- Official documentation for installing Agent Sandbox on GKE
- gVisor used for strong process, storage, network isolation
- Kata Containers supported as alternative
- Python client: `k8s_agent_sandbox` package
- Source: [GKE Agent Sandbox](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/agent-sandbox)

### 3.7 Gemini CLI and Project IDX

**Gemini CLI Sandboxing:**
- **macOS Seatbelt**: Lightweight built-in sandboxing via `sandbox-exec` with configurable profiles
- **Container-based (Docker/Podman)**: Cross-platform with full process isolation
- Enable via: `-s` flag, `GEMINI_SANDBOX=true|docker|podman`, or config file
- Source: [Gemini CLI Sandbox Docs](https://google-gemini.github.io/gemini-cli/docs/sandbox.html)

**Plan Mode (March 2026):**
- Step-by-step execution plan for review before AI takes action
- Default enabled for safe AI agent development
- Source: [Gemini Lab](https://gemilab.net/en/articles/gemini-dev/gemini-cli-plan-mode)

**Project IDX:**
- Now part of Firebase Studio
- Cloud-based dev environment with Gemini AI integration
- Code assistance, completion, contextual actions
- Source: [Project IDX Guides](https://developers.google.com/idx/guides/code-with-gemini-in-idx)

### 3.8 Gemini Computer Use + agent-sandbox

- Example: [Run VS Code and Gemini in sandbox](https://github.com/kubernetes-sigs/agent-sandbox/pull/45)
- Clone repos, setup devcontainer, start VS Code server
- [google-gemini/computer-use-preview](https://github.com/google-gemini/computer-use-preview) for local Playwright browser control

---

## 4. Other Players

### 4.1 E2B (e2b.dev)

**Position:** Enterprise AI Agent Cloud—secure, isolated sandboxes for AI-generated code.

**Technology:**
- **Firecracker microVMs** for hardware-level isolation
- Sub-200ms cold starts
- Multi-language: Python, JavaScript, Ruby, C++

**Features:**
- Terminals, browsers, file systems, internet connectivity
- Extended sessions up to 24 hours (Pro)
- Custom sandbox templates
- LLM-agnostic (OpenAI, Anthropic, Mistral, Llama, custom)

**Use Cases:** Deep research agents, computer use, coding agents, data analysis, automations, background agents, RL

**Adoption:** Perplexity, Hugging Face, Groq, Manus

**Pricing:** Free tier, Pro ($150/month), Enterprise custom

**Deployment:** E2B cloud, AWS, GCP, Azure, on-premises, self-hosted

**Funding:** $21M Series A

- Source: [E2B AI Agents](https://e2b.dev/ai-agents), [E2B Docs](https://docs.e2b.dev/)

### 4.2 Daytona

**Position:** Secure, open-source infrastructure for AI-generated code and agent workflows.

**Technology:**
- **Sub-90ms** sandbox creation from code to execution
- Isolated runtime protection

**Features:**
- Process execution with real-time output streaming
- File system operations with granular permission controls
- Native Git integration with secure credential handling
- Built-in LSP support
- MCP server for AI agent integration (Claude, Cursor, Windsurf)

**APIs:** Python, TypeScript, Ruby, Go SDKs; CLI; REST API; web dashboard

**Deployment:** Hosted service or air-gapped environments

- Source: [Daytona](https://www.daytona.io/), [Daytona Docs](https://daytonadocs.com/)

### 4.3 Modal

**Position:** Serverless sandboxes for AI agent-generated code at scale.

**Technology:**
- **gVisor runtime** for stronger isolation
- Sub-second startup times
- Scale to **50,000+ concurrent sandboxes**

**Features:**
- Dynamically defined sandboxes (one line of code)
- Memory and filesystem snapshots
- Tunnels for direct encrypted communication
- Granular outbound networking controls
- Filesystem APIs for syncing

**Use Cases:** LLM code interpreters, AI app generators, background coding agents, RL evaluations

**Pricing:** Pay-per-use—CPU $0.00003942/core/sec, Memory $0.00000672/GiB/sec

**Platform:** Integrated with Modal's ML lifecycle (inference, training, batch)

- Source: [Modal Sandboxes](https://modal.com/products/sandboxes), [Modal Docs](https://modal.com/docs/guide/sandbox)

### 4.4 OpenAI

**Code Interpreter:**
- Runs Python code in **fully sandboxed virtual machine** environment
- Container-based architecture

**Container Modes:**
1. **Explicit**: Create via `v1/containers` endpoint, specify memory limits (e.g., "4g")
2. **Auto**: System creates/reuses container automatically

**GPT-5.1-Codex-Max:**
- Sandbox isolation as product-level mitigation
- Configurable network access controls
- Specialized safety training at model level

- Source: [OpenAI Sandboxing](https://developers.openai.com/codex/concepts/sandboxing), [GPT-5.1 System Card](https://deploymentsafety.openai.com/gpt-5.1-codex-max/agent-sandbox)

### 4.5 Microsoft / GitHub

**GitHub Copilot Coding Agent:**
- **Secure, fully customizable dev environment powered by GitHub Actions** as compute sandbox
- Ephemeral environment: VM boots, clones repo, configures per task
- All work as commits to draft PRs—requires human approval before CI/CD
- Branch protections and repository policies apply
- Source: [GitHub Blog](https://github.blog/changelog/), [Copilot Docs](https://docs.github.com/en/copilot/concepts/coding-agent/coding-agent)

**VS Code Terminal Sandboxing:**
- `chat.tools.terminal.sandbox.enabled` on macOS/Linux
- Restricts file system and network access for agent-executed commands
- Workspace Trust boundaries disable agents in untrusted projects
- MCP server trust verification
- Manual approval for sensitive file edits
- Source: [VS Code Security](https://code.visualstudio.com/docs/copilot/security)

**GitHub MCP Secret Scanning:**
- Secret scanning for AI coding agents via GitHub MCP Server (March 2026)
- Source: [GitHub Changelog](https://github.blog/changelog/2026-03-17-secret-scanning-in-ai-coding-agents-via-the-github-mcp-server/)

---

## 5. Isolation Technologies Comparison

| Technology | Isolation Level | Overhead | Cold Start | Used By |
|------------|-----------------|----------|------------|---------|
| **MicroVMs (Firecracker)** | Strongest—dedicated kernel | ~5MB memory | <200ms | E2B, AWS Lambda, Vercel Sandbox |
| **gVisor** | User-space kernel, syscall interception | Medium | Low | GKE Agent Sandbox, Modal |
| **Kata Containers** | Lightweight VM per container | Medium | Higher | agent-sandbox |

| **bubblewrap/Seatbelt** | OS-level, filesystem+network | Low | Minimal | Anthropic Claude Code |
| **Hardened Containers** | Shared kernel | Low | Fast | Trusted code only |
| **WebAssembly** | Memory-safe, capability-based | Microsecond | Zero ambient authority | Emerging (Zylos research) |

---

## 6. Mandatory Security Controls (NVIDIA AI Red Team)

**Required:**
1. Block writes to configuration files (hooks, skills, MCP configs)
2. Block file writes outside workspace
3. Network egress controls (block arbitrary outbound)

**Recommended:**
- Virtualization-based isolation (microVMs, Kata, full VMs)
- Secret injection (not inheritance)
- Lifecycle management
- OS-level enforcement (not application-level—subprocesses bypass app controls)

**Why OS-level:** Application-level controls can't intercept subprocess behavior. Attackers use indirection (calling restricted tools through approved ones). OS-level (Seatbelt, etc.) covers every process in the sandbox.

- Source: [NVIDIA Technical Blog](https://developer.nvidia.com/blog/practical-security-guidance-for-sandboxing-agentic-workflows-and-managing-execution-risk/)

---

## 7. Source URLs Summary

### Research & Reports
- [Zylos AI Agent Sandbox Research](https://zylos.ai/research/2026-01-24-ai-agent-code-execution-sandboxing)
- [Zylos Execution Isolation](https://zylos.ai/research/2026-02-21-ai-agent-sandbox-execution-isolation)
- [Zylos Defense-in-Depth Unstrusted Plugins](https://zylos.ai/research/2026-03-05-ai-agent-security-defense-in-depth-untrusted-plugins)
- [NVIDIA Practical Security Guidance](https://developer.nvidia.com/blog/practical-security-guidance-for-sandboxing-agentic-workflows-and-managing-execution-risk/)
- [NVIDIA Code Execution Risks](https://developer.nvidia.com/blog/how-code-execution-drives-key-risks-in-agentic-ai-systems/)
- [Pillar Security: Your AI Agent Will Run Untrusted Code](https://www.pillar.security/blog/your-ai-agent-will-run-untrusted-code-now-what)

### Incidents & Vulnerabilities
- [MCP Security: Kilo Code CVE](https://mcpsec.dev/advisories/2025-10-02-kilo-code-ai-agent-supply-chain-attack/)
- [Skill Poisoning - Simon Roses](https://simonroses.com/2026/02/ai-agent-skill-poisoning-the-supply-chain-attack-you-havent-heard-of/)
- [Snyk Clinejection](https://snyk.io/blog/cline-supply-chain-attack-prompt-injection-github-actions/)
- [Adnan Khan Clinejection](https://adnanthekhan.com/posts/clinejection/)
- [Trail of Bits: Prompt Injection to RCE](https://blog.trailofbits.com/2025/10/22/prompt-injection-to-rce-in-ai-agents/)
- [Bastion HackerBot-Claw](https://bastion.tech/blog/hackerbot-claw-ai-agent-supply-chain-attacks-github-actions/)

### Anthropic
- [Claude Code Sandboxing](https://www.anthropic.com/engineering/claude-code-sandboxing)
- [Claude Code Sandbox Docs](https://docs.claude.com/en/docs/claude-code/sandboxing)
- [Anthropic Computer Use](https://anthropic.com/news/developing-computer-use)
- [anthropic-experimental/sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime)

### Google / Kubernetes
- [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox)
- [agent-sandbox.sigs.k8s.io](https://agent-sandbox.sigs.k8s.io/)
- [Google Open Source Blog: Why Kubernetes Needs Agent Sandbox](https://opensource.googleblog.com/2025/11/unleashing-autonomous-ai-agents-why-kubernetes-needs-a-new-standard-for-agent-execution.html)
- [GKE Agent Sandbox Docs](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/agent-sandbox)
- [Gemini CLI Sandbox](https://google-gemini.github.io/gemini-cli/docs/sandbox.html)
- [Project IDX + Gemini](https://developers.google.com/idx/guides/code-with-gemini-in-idx)

### Vendors
- [E2B AI Agents](https://e2b.dev/ai-agents)
- [E2B Docs](https://docs.e2b.dev/)
- [Daytona](https://www.daytona.io/)
- [Modal Sandboxes](https://modal.com/products/sandboxes)
- [Modal Sandbox Docs](https://modal.com/docs/guide/sandbox)
- [OpenAI Code Interpreter Sandboxing](https://developers.openai.com/codex/concepts/sandboxing)
- [GitHub Copilot Coding Agent](https://docs.github.com/en/copilot/concepts/coding-agent/coding-agent)
- [VS Code Copilot Security](https://code.visualstudio.com/docs/copilot/security)
