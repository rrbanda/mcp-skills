# Red Hat OpenShift Dev Spaces & DevWorkspace Operator: Technical Analysis

**Purpose:** Comprehensive technical analysis of how Red Hat OpenShift Dev Spaces creates and manages workspace pods via the DevWorkspace Operator (DWO), suitable for comparison against agent-sandbox architectures.

**Sources:** DWO GitHub repo, Eclipse Che docs, Red Hat Dev Spaces docs, devfile.io, CRD documentation (doc.crds.dev)

---

## 1. Custom Resource Definitions (CRDs)

### 1.1 DevWorkspace CRD

**API:** `workspace.devfile.io/v1alpha2`  
**Kind:** `DevWorkspace`

The DevWorkspace CR is the Kubernetes representation of a Che workspace. It contains the full devfile specification and workspace metadata.

#### Key Spec Fields

| Field | Description |
|-------|-------------|
| `spec.started` | Boolean; when `true`, DWO reconciles and creates the workspace pod. When `false`, workspace is stopped. |
| `spec.template` | The devfile structure (same as DevWorkspaceTemplate spec). Contains commands, components, projects, attributes. |
| `spec.template.attributes` | Top-level attributes for storage, project clone, config, etc. |
| `spec.template.components` | List of components (container, volume, plugin, kubernetes, openshift, etc.). |
| `spec.template.commands` | Commands (apply, exec, composite, custom). |
| `spec.template.projects` | Git projects to clone. |
| `spec.template.contributions` | Contributions from parent/plugins. |
| `spec.routingClass` | Routing class (e.g., `basic`, `che`). Controls which routing controller manages this workspace. |

#### Devfile → DevWorkspace Mapping

- **Che Dashboard** creates a DevWorkspace CR when a user creates a workspace.
- The devfile (from the repo or sample) is embedded in `spec.template`.
- Che adds the **editor definition** (e.g., Che Code / VS Code) as a component or plugin reference.
- Che adds attributes from `CheCluster` config (e.g., `controller.devfile.io/devworkspace-config`, storage type).

#### Reserved Attributes

- `controller.devfile.io/storage-type`: `per-user`, `per-workspace`, `ephemeral`, `async`, `common`
- `controller.devfile.io/project-clone`: `disable` to skip project clone init container
- `controller.devfile.io/devworkspace-config`: Reference to alternate DevWorkspaceOperatorConfig
- `controller.devfile.io/runtime-class`: RuntimeClass for workspace pods
- `controller.devfile.io/restricted-access`: `"true"` for stricter access control

#### Reserved Environment Variables (cannot be overridden)

- `$PROJECT_SOURCE`: Path to first project (`$PROJECTS_ROOT/<first-project>`)
- `$PROJECTS_ROOT`: Project root (default `/projects`)

---

### 1.2 DevWorkspaceTemplate CRD

**API:** `workspace.devfile.io/v1alpha2`  
**Kind:** `DevWorkspaceTemplate`

Reusable template for DevWorkspace `spec.template` content. Used primarily for **editor definitions** (e.g., Che Code / VS Code Open Source).

#### Structure

- `spec` mirrors the DevWorkspace `spec.template` structure.
- Contains `commands`, `components`, `attributes`, etc.
- Can be referenced via `parent` or `plugin` in a devfile:
  - `kubernetes` reference: `name`, `namespace` (for DevWorkspaceTemplate CR)
  - `registryUrl`, `id`, `version` for registry-based templates

#### Usage in Che

- Che stores editor definitions as DevWorkspaceTemplate CRs.
- When a user selects an editor, Che merges the template into the DevWorkspace.
- Editors are typically container components (e.g., Che Code on port 3100) with endpoints and plugins.

---

### 1.3 DevWorkspaceRouting CRD

**API:** `controller.devfile.io/v1alpha1`  
**Kind:** `DevWorkspaceRouting`

Defines how workspace endpoints are exposed. Each DevWorkspace has a corresponding DevWorkspaceRouting.

#### Spec Fields

| Field | Description |
|-------|-------------|
| `spec.devworkspaceId` | ID of the DevWorkspace being routed |
| `spec.endpoints` | Map: machine/container name → list of endpoints |
| `spec.podSelector` | Selector for the workspace pod (e.g., `controller.devfile.io/devworkspace_id`) |
| `spec.routingClass` | Routing class (e.g., `basic`, `che`) |

#### Endpoint Structure

Each endpoint has:

- `name`, `targetPort`, `protocol` (http, https, ws, wss, tcp, udp)
- `exposure`: `none`, `internal`, `public`
- `secure`: boolean
- `path`: URL path
- `attributes`: Che-specific (e.g., `type: "ide"`, `cookiesAuthEnabled`, `urlRewriteSupported`)

#### Status

- `status.exposedEndpoints`: Machine → exposed endpoint URLs
- `status.phase`: Reconcile phase
- `status.message`: User-readable message
- `status.podAdditions`: Container/annotation additions from the routing controller

#### Routing Classes

- **basic**: Uses OpenShift Routes or Kubernetes Ingress; no gateway; subdomain-only.
- **che**: Uses Che gateway (Traefik + OAuth2 Proxy); supports subpath + subdomain; auth via OIDC.

---

### 1.4 DevWorkspaceOperatorConfig CRD

**API:** `controller.devfile.io/v1alpha1`  
**Kind:** `DevWorkspaceOperatorConfig`

Operator configuration. Two types:

- **Global**: `devworkspace-operator-config` in DWO namespace. Applies to all DevWorkspaces.
- **Non-global**: e.g., `devworkspace-config` in Che namespace. Referenced via `controller.devfile.io/devworkspace-config` workspace attribute. Overrides global for Che workspaces.

#### Config Sections

| Section | Key Fields |
|---------|------------|
| `config.routing` | `clusterHostSuffix`, `defaultRoutingClass` |
| `config.workspace` | `cleanupOnStop`, `containerSecurityContext`, `defaultStorageSize`, `defaultTemplate` |
| `config.proxyConfig` | `httpProxy`, `httpsProxy`, `noProxy` |
| `config.webhooks` | `nodeSelector`, `replicas`, `tolerations` |
| `config.enableExperimentalFeatures` | Boolean for experimental features |

#### Storage Defaults

- `defaultStorageSize.common`: Default 10Gi (per-user, async)
- `defaultStorageSize.perWorkspace`: Default 5Gi

---

## 2. Pod Creation

### 2.1 DevWorkspace → Deployment/Pod Translation

1. **Reconciliation**: DWO controller watches DevWorkspace CRs. When `spec.started` is true, it reconciles.
2. **Resource creation**: DWO creates Deployment, Service(s), ConfigMaps, Secrets, PVCs (if needed), and Routes/Ingress.
3. **Result**: A workspace pod represents the development environment.

### 2.2 Container Composition

| Container Type | Source | Behavior |
|----------------|--------|----------|
| **Init containers** | `apply` commands bound to `preStart` | Run before main containers; component with `dedicatedPod: false` becomes init container |
| **Project clone** | DWO default | Init container added by DWO when `controller.devfile.io/project-clone` ≠ `disable` |
| **Main containers** | Devfile container components | Default components (no `apply` or `deployByDefault: false`) run as main containers |
| **Routing pod additions** | DevWorkspaceRouting `status.podAdditions` | Containers/annotations added by routing controller (e.g., Che gateway sidecar) |

### 2.3 Init Containers

- **Project clone**: Clones git projects from `spec.template.projects` into `$PROJECTS_ROOT` (default `/projects`). Uses `projectCloneContainer` config from CheCluster if available.
- **preStart apply**: Components with `apply` command bound to `preStart` run as init containers (unless `dedicatedPod: true`).

### 2.4 Volumes

| Volume Type | Storage Strategy | Behavior |
|-------------|------------------|----------|
| **Project volume** | All | Mount path from `sourceMapping` (default `/projects`). Backed by PVC or emptyDir depending on strategy. |
| **Per-user PVC** | `per-user`, `common` | Single PVC per user; devfile volumes as subpaths |
| **Per-workspace PVC** | `per-workspace` | One PVC per workspace; devfile volumes as subpaths |
| **Ephemeral** | `ephemeral` | All volumes replaced with `emptyDir` |
| **Async** | `async` | `emptyDir` + sidecar syncs to persistent volume |

### 2.5 Environment Variables & Config

- **Reserved**: `$PROJECT_SOURCE`, `$PROJECTS_ROOT` (set by DWO).
- **Proxy**: `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` from cluster/DWOC.
- **User env**: From devfile `env` on container components.
- **Mounted config**: ConfigMaps/Secrets with `controller.devfile.io/mount-to-devworkspace: "true"` can be mounted as env or files.
- **Git credentials**: Mounted at `/.git-credentials/credentials` when `controller.devfile.io/git-credential` secret is used.

---

## 3. Networking and Routing

### 3.1 DevWorkspaceRouting Flow

1. DWO creates a DevWorkspaceRouting for each DevWorkspace.
2. `routingClass` determines which controller reconciles it (e.g., Che’s routing controller for `che`).
3. Routing controller creates Services, Routes/Ingress, and optionally gateway components.

### 3.2 Endpoint Exposure

- **OpenShift**: Routes (one per endpoint or subpath).
- **Kubernetes**: Ingress.
- **Subpath**: Endpoints with `urlRewriteSupported: true` can be exposed under a path (e.g., `/workspace/...`) via gateway.
- **Subdomain**: Default; each endpoint gets its own host.

### 3.3 Che Gateway

- **Components**: Traefik (routing), OAuth2 Proxy (OIDC), kube-rbac-proxy (RBAC).
- **Deployment**: `che-gateway`.
- **Protects**: Dashboard, Che server, plugin registry, devfile registry, workspaces.
- **Auth**: OIDC flow; user redirected to IdP, then back to gateway with token.

### 3.4 Authentication

- **OAuth2 Proxy**: Validates tokens, enforces auth for protected routes.
- **Subpath endpoints**: Can be protected with auth.
- **Subdomain endpoints**: May require auth depending on gateway configuration.

---

## 4. Storage Strategies

| Strategy | PVC | Behavior | Use Case |
|----------|-----|----------|----------|
| **per-user** | One per user | Shared PVC; all workspaces use subpaths | Default; shared home across workspaces |
| **per-workspace** | One per workspace | Isolated PVC per workspace | Isolation, different storage classes |
| **ephemeral** | None | `emptyDir` only | Ephemeral, no persistence |
| **async** | One per user | `emptyDir` + sync sidecar | Faster startup; avoids slow PVC mount |

### Sizing

- Per-user: default 10Gi (configurable via `claimSize`).
- Per-workspace: default 5Gi (configurable via `claimSize`).

### Notes

- PVCs can slow startup; ReadWriteOnce can block concurrent starts.
- `controller.devfile.io/mount-to-devworkspace: "true"` on PVCs allows mounting even in ephemeral workspaces.

---

## 5. Lifecycle

### 5.1 Start

- User sets `spec.started: true` (or Che does it).
- DWO reconciles: creates Deployment, Services, PVCs, Routes, etc.
- Project clone init container runs.
- preStart apply containers run.
- Main containers start.
- Routing controller exposes endpoints.

### 5.2 Stop

- User sets `spec.started: false`.
- **cleanupOnStop: true**: Deployment, Services, ConfigMaps, etc. are deleted.
- **cleanupOnStop: false** (default): Deployment scaled to 0; resources remain on cluster.

### 5.3 State Preservation

- **Per-user**: Data in shared PVC persists across restarts.
- **Per-workspace**: Data in workspace PVC persists.
- **Ephemeral**: No persistence; data lost on stop.
- **Async**: Sync sidecar keeps data in PVC; workspace uses emptyDir.

### 5.4 Idling

- `secondsOfInactivityBeforeIdling`: Workspace idled after inactivity.
- `secondsOfRunBeforeIdling`: Max run time before idling.
- Idling typically scales deployment to 0.

---

## 6. What Runs Inside the Workspace Pod

### 6.1 Universal Developer Image (UDI)

- **Default**: Used when no devfile or no container components.
- **Image**: `quay.io/devfile/universal-developer-image:ubi9-latest` (community); Red Hat: `registry.redhat.io/devspaces/udi-rhel9`.
- **Contents**: Base tools, languages (Java, Python, Go, Node.js, .NET, PHP, Scala), and cloud tooling.
- **Resources**: e.g., 6G memory limit, 512Mi request, 1000m CPU request, 4000m limit.

### 6.2 Che Code Editor

- **Injection**: Added as a component (often from a DevWorkspaceTemplate) when user selects Che Code.
- **Port**: Typically 3100.
- **Endpoint**: `type: "ide"`, `cookiesAuthEnabled`, `urlRewriteSupported` for subpath routing.
- **Runs**: As a container in the workspace pod (or sidecar).

### 6.3 Project Clone

- **Init container**: Runs before main containers.
- **Source**: `spec.template.projects` (git remotes, revision, sparse checkout).
- **Destination**: `$PROJECTS_ROOT` (default `/projects`).
- **Config**: `controller.devfile.io/project-clone: disable` to skip.
- **Sparse checkout**: `sparseCheckout` attribute on project for partial clone.

---

## 7. Summary: Comparison-Ready Points

| Aspect | DevWorkspace / Dev Spaces |
|--------|---------------------------|
| **Orchestration** | Kubernetes CRs (DevWorkspace, DevWorkspaceRouting) |
| **Pod model** | Single pod (or multi-pod with `dedicatedPod`) |
| **Containers** | Devfile containers + editor + optional init/sidecars |
| **Storage** | Per-user, per-workspace, ephemeral, async |
| **Networking** | Routes/Ingress; Che gateway for auth + subpath |
| **Lifecycle** | `spec.started`; scale down vs delete on stop |
| **Project clone** | Init container |
| **Editor** | Injected via DevWorkspaceTemplate |

---

## References

- [DevWorkspace Operator](https://github.com/devfile/devworkspace-operator)
- [Eclipse Che DevWorkspace Operator](https://eclipse.dev/che/docs/stable/administration-guide/devworkspace-operator/)
- [Eclipse Che Gateway](https://www.eclipse.org/che/docs/stable/administration-guide/gateway/)
- [Eclipse Che Storage Strategy](https://www.eclipse.org/che/docs/stable/administration-guide/configuring-the-storage-strategy/)
- [DWO Additional Configuration](https://github.com/devfile/devworkspace-operator/blob/main/docs/additional-configuration.adoc)
- [Red Hat OpenShift Dev Spaces](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces)
- [DevWorkspace CRD](https://doc.crds.dev/github.com/devfile/devworkspace-operator/workspace.devfile.io/DevWorkspace/v1alpha2)
- [DevWorkspaceOperatorConfig CRD](https://doc.crds.dev/github.com/devfile/devworkspace-operator/controller.devfile.io/DevWorkspaceOperatorConfig/v1alpha1)
- [DevWorkspaceRouting CRD](https://doc.crds.dev/github.com/devfile/devworkspace-operator/controller.devfile.io/DevWorkspaceRouting/v1alpha1)
