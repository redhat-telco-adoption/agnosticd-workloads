# ocp4_workload_coo_incident_detection

AgnosticDv2 workload role that provisions the **COO Incident Detection Demo** on an OpenShift 4.20+ cluster.

This demo showcases the Cluster Observability Operator (COO) incident detection feature using a simulated 5G NOC environment. It installs a full observability stack (logging, tracing, network flow, AI-assisted troubleshooting) and a realistic multi-service application that can simulate various failure scenarios.

## What Gets Installed

### Operators (8 total, installed sequentially)

| Operator | Namespace | Channel |
|---|---|---|
| cluster-observability-operator | openshift-cluster-observability-operator | stable |
| loki-operator | openshift-operators-redhat | stable-6.4 |
| cluster-logging | openshift-logging | stable-6.4 |
| web-terminal | openshift-operators | fast |
| lightspeed-operator | openshift-lightspeed | stable |
| tempo-product | openshift-tempo-operator | stable |
| opentelemetry-product | openshift-opentelemetry-operator | stable |
| netobserv-operator | openshift-netobserv-operator | stable |

### Infrastructure

- **MinIO** — In-cluster S3 backend (namespace: `openshift-logging`) for Loki, Tempo, and NetObserv
- **LokiStack** (logging-loki) — Log aggregation via Vector collectors
- **TempoStack** (tempo-sample) — Distributed tracing backend
- **NetObserv LokiStack** (netobserv-loki) — Network flow log storage

### Applications

| Namespace | Components |
|---|---|
| `incident-simulator` | frontend, backend-api, worker (3-tier incident simulator) |
| `acme-5gc-edge` | NRF, AMF, SMF, UPF, Charging CDR (simulated 5G core edge site) |
| `5g-noc` | 5G NOC Dashboard (edge site health, failure cascade, active faults, business impact) |

### Observability

- COO UIPlugins: Monitoring (incidents + Perses), Logging, TroubleshootingPanel, DistributedTracing
- ServiceMonitors + PrometheusRules for both application namespaces
- Perses dashboard for ACME 5G Core Edge site health
- Alertmanager silences for 5 noisy platform alerts (1-week duration)

### AI / Lightspeed

- Cluster Health Analyzer MCP Server (incident data exposed via Model Context Protocol)
- OpenShift Lightspeed connected to LiteLLM gateway with MCP integration

### Demo User

- Username: `noc-intern` (configurable)
- HTPasswd IDP added to cluster OAuth
- RBAC: cluster-wide view, pod logs, monitoring CRDs, Lightspeed access, web terminal, pod exec in acme-5gc-edge

## Requirements

- OpenShift 4.20+ (4.21 recommended)
- AWS cluster with `gp3-csi` storage class (or override `ocp4_workload_coo_incident_detection_storage_class`)
- LLM API token for OpenShift Lightspeed

## Role Variables

### Required

| Variable | Description |
|---|---|
| `ocp4_workload_coo_incident_detection_llm_api_token` | LLM API token for OpenShift Lightspeed |

### Optional

| Variable | Default | Description |
|---|---|---|
| `ocp4_workload_coo_incident_detection_storage_class` | `gp3-csi` | StorageClass for MinIO, LokiStack, TempoStack |
| `ocp4_workload_coo_incident_detection_minio_access_key` | `minio` | MinIO root user |
| `ocp4_workload_coo_incident_detection_minio_secret_key` | `minio123` | MinIO root password |
| `ocp4_workload_coo_incident_detection_loki_channel` | `stable-6.4` | Loki Operator channel |
| `ocp4_workload_coo_incident_detection_logging_channel` | `stable-6.4` | Cluster Logging Operator channel |
| `ocp4_workload_coo_incident_detection_llm_api_url` | `https://litellm-prod.apps.maas.redhatworkshops.io/v1` | LLM provider base URL |
| `ocp4_workload_coo_incident_detection_llm_model` | `llama-scout-17b` | LLM model name |
| `ocp4_workload_coo_incident_detection_llm_provider_name` | `LiteLLM` | Lightspeed provider display name |
| `ocp4_workload_coo_incident_detection_demo_user_name` | `noc-intern` | Demo user username |
| `ocp4_workload_coo_incident_detection_demo_user_password` | `""` | Demo user password (must match the user created by `ocp4_workload_authentication_htpasswd`) |
| `ocp4_workload_coo_incident_detection_slack_webhook_url` | `""` | Optional Slack incoming webhook for Alertmanager notifications |
| `ocp4_workload_coo_incident_detection_app_image_tag` | `latest` | Image tag for incident-simulator containers |
| `ocp4_workload_coo_incident_detection_alert_silence_duration_hours` | `168` | Duration (hours) for Alertmanager silences |

## Demo Walkthrough

See [WALKTHROUGH.md](WALKTHROUGH.md) for the full demo narrative, pre-demo checklist, and stage-by-stage presenter guide.

## Usage

This role is deployed using [AgnosticDv2](https://github.com/agnosticd/agnosticd-v2), a framework for provisioning cloud-based demo and workshop environments. AgnosticDv2 handles cluster connectivity, variable injection, and workload lifecycle (`provision` / `destroy`). See the [AgnosticDv2 setup guide](https://github.com/agnosticd/agnosticd-v2/blob/main/docs/setup.adoc) to install the `agd` CLI and configure secrets before running this role.

### Base environment

This demo has been tested against the **AWS with OpenShift Open Environment** on the [Red Hat Demo Platform](https://catalog.demo.redhat.com/catalog?item=babylon-catalog-prod/sandboxes-gpte.sandbox-ocp.prod). It will need adaptation (storage class, cluster credentials) if deployed against a different base environment.

### Sample vars file

Create a vars file (e.g. `agnosticd-v2-vars/openshift-workloads-coo.yml`). The `openshift-workloads` config deploys workloads listed under `workloads:` in sequence to the target cluster. Both `ocp4_workload_authentication_htpasswd` (creates users) and this role must be included — the demo user password is managed by the htpasswd workload.

```yaml
tag: main
cloud_provider: none
config: openshift-workloads

requirements_content:
  collections:
  - name: https://github.com/agnosticd/core_workloads.git
    type: git
    version: "{{ tag }}"
  - name: https://github.com/redhat-telco-adoption/agnosticd-workloads.git
    type: git
    version: "{{ tag }}"

clusters:
- default:
    api_url: "{{ cluster1.sandbox_openshift_api_url }}"
    api_token: "{{ cluster1.sandbox_openshift_api_token }}"

workloads:
- agnosticd.core_workloads.ocp4_workload_authentication_htpasswd
- redhat_telco_adoption.agnosticd.ocp4_workload_coo_incident_detection

# -------------------------------------------------------------------
# ocp4_workload_authentication_htpasswd
# -------------------------------------------------------------------
ocp4_workload_authentication_htpasswd_admin_user: admin
ocp4_workload_authentication_htpasswd_admin_password: "YOUR_ADMIN_PASSWORD"
ocp4_workload_authentication_htpasswd_user_count: 0
ocp4_workload_authentication_htpasswd_named_users:
- name: noc-intern
  password: "YOUR_NOC_INTERN_PASSWORD"

# -------------------------------------------------------------------
# ocp4_workload_coo_incident_detection
# -------------------------------------------------------------------
ocp4_workload_coo_incident_detection_llm_api_token: "YOUR_LLM_API_TOKEN"
ocp4_workload_coo_incident_detection_demo_user_name: noc-intern

# Optional: Slack incoming webhook for Alertmanager notifications
# ocp4_workload_coo_incident_detection_slack_webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Optional: override LLM provider (defaults shown)
# ocp4_workload_coo_incident_detection_llm_api_url: "https://litellm-prod.apps.maas.redhatworkshops.io/v1"
# ocp4_workload_coo_incident_detection_llm_model: llama-scout-17b

# Optional: override storage class (default gp3-csi is correct for AWS)
# ocp4_workload_coo_incident_detection_storage_class: gp3-csi
```

### Provision

```bash
./bin/agd provision --guid <your-guid> --config openshift-workloads-coo --account <your-account>
```

### Destroy

```bash
./bin/agd destroy --guid <your-guid> --config openshift-workloads-coo --account <your-account>
```

## Provision Timing

Total provision time is approximately 45-60 minutes:

| Phase | Duration |
|---|---|
| Operator installs (sequential) | ~15 min |
| LokiStack Ready | ~8 min |
| TempoStack Ready | ~5 min |
| OLSConfig Ready (Lightspeed) | ~12 min |
| NetObserv LokiStack Ready | ~8 min |
| Applications + observability | ~2 min |

## Post-Provision

The workload info task reports via `agnosticd_user_info`:

- Incident Simulator URL
- 5G NOC Dashboard URL (route `dashboard` in `5g-noc` namespace)
- OpenShift Console URL
- Demo user credentials
- Direct links to Observe > Incidents and Observe > Logs views
