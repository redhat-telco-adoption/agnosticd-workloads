# Stage 2 Plan: ocp4_workload_rhoai3x — RHOAI 3.3 Operator + GPU + DataScienceCluster

## Context

This is Stage 2 of the RHOAI 3.3 deployment on a bare OpenShift cluster on AWS (Red Hat Demo Platform).

**Stage 1 (already deployed via `openshift-workloads-rhoai.yml`):**
- htpasswd identity provider (admin user + 5 regular users)
- Node Feature Discovery (NFD) operator — detects GPU nodes
- MinIO — S3-compatible storage for KServe model artifacts and AI Pipeline artifacts/logs

**Stage 2 (this role):** Custom `agnosticd-workloads` role that installs:
1. NVIDIA GPU Operator
2. Red Hat OpenShift AI (RHOAI) 3.3 Operator
3. `DataScienceCluster` CR — enables Dashboard, Workbenches, KServe, AI Pipelines

**Target RHOAI components:** Dashboard, Workbenches, KServe (model serving), AI Pipelines, NVIDIA GPU support.

---

## Role Pattern

Follows the [ocp4_workload_example](https://github.com/agnosticd/core_workloads/tree/main/roles/ocp4_workload_example) pattern:

```
roles/ocp4_workload_rhoai3x/
├── PLAN.md                          # This file
├── readme.adoc                      # Role documentation
├── defaults/
│   └── main.yml                     # All user-facing defaults (prefixed ocp4_workload_rhoai3x_*)
├── vars/
│   └── main.yml                     # Internal variables (prefixed _ocp4_workload_rhoai3x_*)
├── tasks/
│   ├── main.yml                     # Dispatches on ACTION: provision | destroy
│   ├── workload.yml                 # Orchestrates provision task files
│   ├── remove_workload.yml          # Deprovision stub
│   ├── nvidia_gpu_operator.yml      # NVIDIA GPU Operator install
│   ├── rhoai_operator.yml           # RHOAI operator install
│   ├── datasciencecluster.yml       # DataScienceCluster CR
│   └── pipeline_app.yml             # Optional: DataSciencePipelineApplication CR
└── meta/
    └── main.yml                     # Role metadata
```

**Entry point:** `tasks/main.yml` dispatches to `workload.yml` (when `ACTION == "provision"`) or `remove_workload.yml` (when `ACTION == "destroy"`), matching the framework pattern exactly.

---

## `tasks/main.yml`

```yaml
# --------------------------------------------------
# Do not modify this file
# --------------------------------------------------
- name: Running workload provision tasks
  when: ACTION == "provision"
  ansible.builtin.include_tasks: workload.yml

- name: Running workload removal tasks
  when: ACTION == "destroy"
  ansible.builtin.include_tasks: remove_workload.yml
```

---

## `tasks/workload.yml`

Orchestrates task files in order:

```yaml
- name: Install NVIDIA GPU Operator
  ansible.builtin.include_tasks: nvidia_gpu_operator.yml
  when: ocp4_workload_rhoai3x_nvidia_gpu_operator_install | bool

- name: Install RHOAI Operator
  ansible.builtin.include_tasks: rhoai_operator.yml

- name: Configure DataScienceCluster
  ansible.builtin.include_tasks: datasciencecluster.yml

- name: Configure DataSciencePipelineApplication
  ansible.builtin.include_tasks: pipeline_app.yml
  when: ocp4_workload_rhoai3x_pipeline_app_configure | bool
```

---

## Task File Details

### `nvidia_gpu_operator.yml`

**Goal:** Install the NVIDIA GPU Operator via OLM. NFD (Stage 1) must already be running to provide GPU node labels.

**Steps:**
1. Create namespace `{{ ocp4_workload_rhoai3x_nvidia_gpu_operator_namespace }}`
2. Create `OperatorGroup` scoped to that namespace
3. Create `Subscription` for `gpu-operator-certified` from `certified-operators` catalog
4. Wait for `ClusterServiceVersion` to reach `Succeeded` phase (retries × delay)
5. The operator auto-creates `ClusterPolicy` `gpu-cluster-policy` — no manual CR needed

### `rhoai_operator.yml`

**Goal:** Install the RHOAI 3.3 operator via OLM into `redhat-ods-operator`.

**Steps:**
1. Create namespace `{{ ocp4_workload_rhoai3x_operator_namespace }}`
2. Create `OperatorGroup` scoped to that namespace
3. Create `Subscription` for `rhods-operator` from `redhat-operators` catalog
4. Wait for `ClusterServiceVersion` to reach `Succeeded` phase
5. The operator auto-creates the `redhat-ods-applications` namespace

**Pre-flight check:** Verify channel name at deploy time:
```bash
oc get packagemanifest rhods-operator -n openshift-marketplace \
  -o jsonpath='{range .status.channels[*]}{.name}{"\n"}{end}'
```

### `datasciencecluster.yml`

**Goal:** Create the `DataScienceCluster` CR to enable specific RHOAI components.

**Steps:**
1. Wait for the `DataScienceCluster` CRD to be available (operator must be `Succeeded` first)
2. Apply `DataScienceCluster` CR `{{ ocp4_workload_rhoai3x_dsc_name }}`
3. Wait for `DataScienceCluster` status to report `Ready`

**Component management state:**

| Component | managementState | Reason |
|---|---|---|
| `dashboard` | `Managed` | Enable RHOAI web UI |
| `workbenches` | `Managed` | Enable Jupyter workbenches |
| `datasciencepipelines` | `Managed` | AI Pipelines (MinIO from Stage 1) |
| `kserve` | `Managed` | KServe model serving |
| `modelmeshserving` | `Removed` | Not needed — KServe only |
| `ray` | `Removed` | Out of scope |
| `trainingoperator` | `Removed` | Out of scope |
| `codeflare` | `Removed` | Out of scope |

**KServe mode:** `serving.managementState: Unmanaged` + `deploymentMode: RawDeployment`
RHOAI 3.x does NOT require Service Mesh or Serverless (those were 2.x requirements).

### `pipeline_app.yml`

**Goal:** Pre-create a `DataSciencePipelineApplication` CR pointing to the MinIO instance from Stage 1, so users don't need to configure storage manually.

**Steps:**
1. Create project `{{ ocp4_workload_rhoai3x_pipeline_app_project }}`
2. Apply `DataSciencePipelineApplication` CR with MinIO connection details

---

## `defaults/main.yml` — Full Variable Reference

```yaml
# NVIDIA GPU Operator
ocp4_workload_rhoai3x_nvidia_gpu_operator_install: true
ocp4_workload_rhoai3x_nvidia_gpu_operator_channel: "v24.9"
ocp4_workload_rhoai3x_nvidia_gpu_operator_namespace: nvidia-gpu-operator
ocp4_workload_rhoai3x_nvidia_gpu_operator_csv_wait_retries: 30
ocp4_workload_rhoai3x_nvidia_gpu_operator_csv_wait_delay: 20

# RHOAI Operator
ocp4_workload_rhoai3x_operator_channel: "stable"
ocp4_workload_rhoai3x_operator_namespace: redhat-ods-operator
ocp4_workload_rhoai3x_operator_csv_wait_retries: 45
ocp4_workload_rhoai3x_operator_csv_wait_delay: 20

# DataScienceCluster
ocp4_workload_rhoai3x_dsc_name: default-dsc
ocp4_workload_rhoai3x_kserve_serving_management_state: "Unmanaged"
ocp4_workload_rhoai3x_kserve_deployment_mode: "RawDeployment"
ocp4_workload_rhoai3x_dsc_wait_retries: 30
ocp4_workload_rhoai3x_dsc_wait_delay: 20

# DataSciencePipelineApplication (optional)
ocp4_workload_rhoai3x_pipeline_app_configure: true
ocp4_workload_rhoai3x_pipeline_app_project: rhoai-shared
ocp4_workload_rhoai3x_pipeline_minio_endpoint: "http://minio.minio.svc.cluster.local:9000"
ocp4_workload_rhoai3x_pipeline_minio_bucket: rhoai-pipelines
ocp4_workload_rhoai3x_pipeline_minio_access_key: "minio"
ocp4_workload_rhoai3x_pipeline_minio_secret_key: "minio123"
```

---

## Open Questions / Decisions Before Implementation

1. **RHOAI OLM channel name** — verify exact channel string for RHOAI 3.3 (likely `stable` but confirm on target cluster)

2. **NVIDIA GPU Operator channel** — `v24.9` is current as of early 2026; confirm on target cluster:
   ```bash
   oc get packagemanifest gpu-operator-certified -n openshift-marketplace \
     -o jsonpath='{range .status.channels[*]}{.name}{"\n"}{end}'
   ```

3. **GPU nodes present?** — If the cluster has no GPU nodes, `ClusterPolicy` may never fully initialize. Set `ocp4_workload_rhoai3x_nvidia_gpu_operator_install: false` to skip.

4. **KServe ingress** — `RawDeployment` mode creates OpenShift Routes. Confirm wildcard domain on the target cluster's `IngressController`.

---

## Reference Documentation

| Topic | URL |
|---|---|
| RHOAI 3.3 — Installation & prerequisites | [Installing and deploying OpenShift AI Self-Managed 3.3](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.3/html/installing_and_uninstalling_openshift_ai_self-managed/installing-and-deploying-openshift-ai_install) |
| RHOAI 3.3 — DataScienceCluster component management | [Managing OpenShift AI 3.3](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.3/html/managing_openshift_ai/index) |
| RHOAI 3.3 — KServe / RawDeployment model serving | [Deploying models on OpenShift AI 3.3](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.3/html/deploying_models/index) |
| RHOAI 3.3 — AI Pipelines (DataSciencePipelineApplication) | [Working with AI Pipelines 3.3](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.3/html/working_with_ai_pipelines/index) |
| NVIDIA GPU Operator on OpenShift | [NVIDIA GPU Operator — OpenShift Guide](https://docs.nvidia.com/datacenter/cloud-native/openshift/latest/index.html) |
| Node Feature Discovery (NFD) Operator | [NFD Operator — OpenShift 4.17](https://docs.redhat.com/en/documentation/openshift_container_platform/4.17/html/specialized_hardware_and_driver_enablement/psap-node-feature-discovery-operator) |
| OLM — Installing operators via Subscription | [Adding Operators to a cluster — OCP 4.17](https://docs.redhat.com/en/documentation/openshift_container_platform/4.17/html/operators/administrator-tasks#olm-adding-operators-to-a-cluster) |
| AgnosticD workload role pattern | [ocp4_workload_example on GitHub](https://github.com/agnosticd/core_workloads/tree/main/roles/ocp4_workload_example) |
| vLLM CUDA image tags (RHOAI/RHAIIS) | [odh-vllm-cuda-rhel9 — Red Hat Container Catalog](https://catalog.redhat.com/en/software/containers/rhoai/odh-vllm-cuda-rhel9/68af11f5fad01b87e349f2fa) |

---

## MLflow

### Access

MLflow is deployed in `redhat-ods-applications` and exposed via path-based routing under the RHOAI data science gateway — no separate hostname needed.

```
https://data-science-gateway.apps.<cluster-domain>/mlflow
```

Also linked in the OCP console Application Menu → **OpenShift Self Managed Services → MLflow**.

### Instrumenting workloads

```bash
export MLFLOW_TRACKING_TOKEN="$(oc whoami --show-token)"
export MLFLOW_TRACKING_URI="https://data-science-gateway.apps.<cluster-domain>/mlflow"
export MLFLOW_WORKSPACE="<your-namespace>"
```

> **Note:** The token is session-scoped — refresh it with `oc whoami --show-token` each time.

---

## Verification After Deployment

```bash
# NVIDIA GPU Operator
oc get csv -n nvidia-gpu-operator | grep gpu-operator
oc get clusterpolicy gpu-cluster-policy

# RHOAI Operator
oc get csv -n redhat-ods-operator | grep rhods
oc get pods -n redhat-ods-applications

# DataScienceCluster
oc get datasciencecluster default-dsc -o jsonpath='{.status.conditions}' | jq .

# RHOAI Dashboard route
oc get route -n redhat-ods-applications | grep dashboard

# KServe
oc get pods -n redhat-ods-applications | grep kserve

# AI Pipelines
oc get pods -n redhat-ods-applications | grep pipeline

# Pipeline Application (if configured)
oc get datasciencepipelinesapplication -n rhoai-shared
```
