# redhat_telco_adoption.agnosticd

AgnosticD V2 workload roles for the Red Hat Telco Adoption team, deployed on OpenShift via the Red Hat Demo Platform.

## Overview

This Ansible Collection provides AgnosticD V2 workload roles used to provision workshops, demos, and training content on
the [Red Hat Demo Platform](https://demo.redhat.com). Workloads are deployed onto OpenShift 4.x clusters using the
AgnosticD framework.

**Audience:** Demo Platform operators and content creators.

## Prerequisites

- AgnosticD V2 installed and configured
- OpenShift 4.x cluster accessible via kubeconfig
- Ansible 2.9+
- Required Ansible collections: `kubernetes.core`, `agnosticd.core`

## Collection Information

| Field     | Value                   |
|-----------|-------------------------|
| Namespace | `redhat_telco_adoption` |
| Name      | `agnosticd`             |
| Version   | `1.0.0`                 |
| License   | `GPL-2.0-or-later`      |

## Available Workloads

| Workload Role                                | Description                                                                                                            |
|----------------------------------------------|------------------------------------------------------------------------------------------------------------------------|
| `ocp4_workload_ocp_troubleshooting_workshop` | Deploys the OpenShift Troubleshooting Workshop — per-attendee namespaces with 19 broken lab scenarios across 6 modules |

## Workload Details

### ocp4_workload_ocp_troubleshooting_workshop

**Purpose:** Provisions per-attendee lab environments for an OpenShift troubleshooting workshop.

**What it deploys:**

- HTPasswd identity provider
- Per-user namespaces (one per module): `{username}-{module}`
- Resource quotas and LimitRanges per namespace
- 19 intentionally broken application scenarios that participants must diagnose and fix

**Workshop Modules:**

| Module | Topic         | Labs                                                               |
|--------|---------------|--------------------------------------------------------------------|
| 01     | Configuration | Missing ConfigMap, Missing Secret, Invalid Env                     |
| 02     | Storage       | Missing PVC, PVC Pending, Volume Permissions                       |
| 03     | Security      | RBAC, SCC, Image Pull Secret                                       |
| 04     | Networking    | Selector Mismatch, Route Misconfigured, DNS Failure, NetworkPolicy |
| 05     | Resources     | Insufficient Resources, OOMKilled, Quota Exceeded                  |
| 06     | Lifecycle     | CrashLoopBackOff, Probe Failure, Wrong Image Tag                   |

**Key Variables:**

| Variable                                              | Default        | Description              |
|-------------------------------------------------------|----------------|--------------------------|
| `ocp_username`                                        | `system:admin` | OpenShift admin username |
| `ocp4_workload_ocp_troubleshooting_workshop_idp_name` | `htpasswd`     | HTPasswd IDP name        |

**Actions supported:** `provision`, `destroy`

## Usage with AgnosticD V2

Reference the workload in an AgnosticD V2 config vars file:

```yaml
workloads:
  - redhat_telco_adoption.agnosticd.ocp4_workload_ocp_troubleshooting_workshop

ocp_username: "system:admin"
ocp4_workload_ocp_troubleshooting_workshop_idp_name: "htpasswd"
```

Then provision with:

```bash
agd provision
```
