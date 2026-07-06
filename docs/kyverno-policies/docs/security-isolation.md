# Security & Isolation Policies

Category: `security-isolation` · 7 policies · All Wave 1 · PRD-2026-KYVERNO-POLICY-001

These policies enforce the platform's baseline pod security posture. They apply to Pods and, via Kyverno autogen, to Deployments, StatefulSets, DaemonSets, Jobs, and CronJobs. System namespaces (kube-system, argocd, kyverno, datadog, external-secrets, envoy-gateway-system, cilium-system) are excluded.

---

## disallow-privileged-containers

**Severity: high · Wave 1 · Test: `tests/security-isolation/disallow-privileged-containers/`**

Blocks any container (including init and ephemeral containers) with `securityContext.privileged: true`. Privileged containers have full access to the host and defeat every other isolation control, so there is no tenant-workload use case for them on this platform.

**How to comply:** Don't set `privileged: true`. If your workload needs a specific kernel capability, use the capability allow-list (see `restrict-capabilities`) or file an exception.

---

## disallow-host-namespaces

**Severity: high · Wave 1 · Test: `tests/security-isolation/disallow-host-namespaces/`**

Blocks `hostPID`, `hostIPC`, and `hostNetwork`. Sharing host namespaces lets a pod observe or interfere with processes and network traffic outside its own boundary — a multi-tenant isolation break.

**How to comply:** Omit these fields entirely (they default to false). Workloads needing host network access are platform-level components, not tenant workloads.

---

## disallow-privilege-escalation

**Severity: high · Wave 1 · Test: `tests/security-isolation/disallow-privilege-escalation/`**

Requires `allowPrivilegeEscalation: false` to be **explicitly set** on every container. Note this is stricter than "not true" — the field must be present and false, which keeps manifests self-documenting.

**How to comply:**
```yaml
securityContext:
  allowPrivilegeEscalation: false
```

---

## require-run-as-nonroot

**Severity: high · Wave 1 · Test: `tests/security-isolation/require-run-as-nonroot/`**

Requires `runAsNonRoot: true` at the pod or container level. Containers running as UID 0 dramatically expand the impact of a container escape.

**How to comply:** Set at pod level (preferred, covers all containers):
```yaml
spec:
  securityContext:
    runAsNonRoot: true
```
Your image must also actually run as a non-root user (`USER` directive or `runAsUser`), or the kubelet will reject the pod at runtime.

---

## require-readonly-rootfs

**Severity: medium · Wave 1 · Test: `tests/security-isolation/require-readonly-rootfs/`**

Requires `readOnlyRootFilesystem: true` on all containers. An immutable root filesystem prevents attackers from writing tools or persistence into a compromised container.

**How to comply:** Set the flag and mount `emptyDir` volumes for legitimately writable paths (e.g. `/tmp`, Spring Boot temp dirs):
```yaml
securityContext:
  readOnlyRootFilesystem: true
volumeMounts:
  - name: tmp
    mountPath: /tmp
```

**Exceptions expected:** Some runtimes need broader writable paths. This is the policy most likely to need PolicyExceptions — request one via the exception process rather than skipping the control fleet-wide.

---

## restrict-capabilities

**Severity: medium · Wave 1 · Test: `tests/security-isolation/restrict-capabilities/`**

Requires every container to `drop: ["ALL"]` capabilities; only `NET_BIND_SERVICE` may be added back (for binding ports <1024 as non-root).

**How to comply:**
```yaml
securityContext:
  capabilities:
    drop: ["ALL"]
    add: ["NET_BIND_SERVICE"]   # only if actually needed
```

---

## require-seccomp-profile

**Severity: medium · Wave 1 · Test: `tests/security-isolation/require-seccomp-profile/`**

Requires a seccomp profile of `RuntimeDefault` or `Localhost` at pod or container level. Unconfined syscall access widens the kernel attack surface.

**How to comply:**
```yaml
spec:
  securityContext:
    seccompProfile:
      type: RuntimeDefault
```
