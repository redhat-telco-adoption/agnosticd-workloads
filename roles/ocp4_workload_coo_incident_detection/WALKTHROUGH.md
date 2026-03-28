# COO Incident Detection Demo — Walkthrough

## Objective

Show how the Cluster Observability Operator automatically correlates signals (metrics, logs, events, traces) into a single incident, reducing MTTR from a 30-minute war room to minutes with AI assistance.

---

## Narrative

**ACME Telecom** runs a 5G Core edge site on OpenShift. An NRF database connection pool exhaustion triggers a cascading failure across AMF → SMF → UPF → Charging CDR. The demo progressively reveals seven layers of observability — each making the problem faster and easier to diagnose.

The journey starts with a confused NOC operator (Stage 1) and ends with AI-assisted root cause identification in under 2 minutes (Stage 7).

---

## Deployed Workloads

| Workload | Namespace | URL / Access Path |
|---|---|---|
| 5G NOC Dashboard | `5g-noc` | Route `dashboard` in `5g-noc` namespace (reported in provision output) |
| 5G Core Edge (NRF, AMF, SMF, UPF, Charging) | `acme-5gc-edge` | Internal services only |
| Incident Simulator | `incident-simulator` | Route `incident-simulator` (reported in provision output) |
| Perses Dashboard | `acme-5gc-edge` | OpenShift Console > Observe > Dashboards |
| Alertmanager | `openshift-monitoring` | OpenShift Console > Observe > Alerting |
| Incidents view | COO (built-in) | OpenShift Console > Observe > Incidents |
| Traces | `tempo` | OpenShift Console > Observe > Traces |
| Network Traffic | `netobserv` | OpenShift Console > Observe > Network Traffic |
| Lightspeed | `openshift-lightspeed` | OpenShift Console help icon (?) |

---

## Pre-Demo Checklist

1. **Log in as demo user** (`noc-intern`) in the OpenShift Console — confirm view-only access to `acme-5gc-edge`.
2. **Open browser tabs** in this order:
   - 5G NOC Dashboard
   - OpenShift Console > Observe > Incidents
   - OpenShift Console > Observe > Alerting
   - OpenShift Console > Observe > Dashboards (Perses)
   - OpenShift Console > Observe > Traces
   - OpenShift Console > Observe > Network Traffic
3. **Restart the 5G Core NFs** to reset the fault state:
   ```
   oc rollout restart deployment -n acme-5gc-edge
   ```
   Wait ~60 seconds — the NRF connection pool exhaustion begins automatically and the cascade follows.
4. **Open the 5G NOC Dashboard** and trigger the **NRF Cascade** scenario via the Fault Injection controls. This syncs the dashboard visuals with the cluster-side fault for narrative effect.
5. Confirm the Incident Banner on the NOC dashboard is showing active faults (affected regions, user count, revenue loss/min).

---

## Stage 1: Manual Troubleshooting

**Goal:** Establish the "before" state — a NOC operator with no tooling beyond `oc`.

**Navigate to:** OpenShift Console > Workloads > Pods (namespace: `acme-5gc-edge`)

**Show:**
- Several pods in CrashLoopBackOff or restarting
- `oc logs` output shows cryptic error messages with no clear root cause
- No correlation between which pods are failing and why

**Key lesson:** Without observability tooling, diagnosing a cascade like this requires tribal knowledge and takes 30+ minutes. The operator knows something is broken but not where to start.

---

## Stage 2: Add Monitoring (Metrics + Perses Dashboard)

**Goal:** Show the Perses dashboard giving a structured view of the 5G Core health.

**Navigate to:** OpenShift Console > Observe > Dashboards

**Show:**
- Select the ACME 5G Core Edge Site Health dashboard
- Point out the NRF connection pool exhaustion metric spiking
- Show how AMF/SMF/UPF error rates rise immediately after NRF degrades
- The cascade is visible at a glance — NRF is the root cause

**Key lesson:** Metrics make the cascade visible. You can see the failure propagation path without reading logs. But you still have to manually connect the dots across dashboards.

---

## Stage 3: Add Alerting

**Goal:** Show that alerts fired and provide context on thresholds.

**Navigate to:** OpenShift Console > Observe > Alerting

**Show:**
- Multiple firing alerts: NRF connection pool threshold, AMF registration failures, SMF session failures
- Each alert has severity, description, and runbook links
- Alerts fired in sequence matching the cascade timeline

**Key lesson:** Alerts tell you what crossed a threshold, but they don't tell you which alert caused the others. A war room call would still be needed to sort firing order and blame.

---

## Stage 4: Incident Correlation with COO

**Goal:** Show COO's automatic incident grouping — the core feature.

**Navigate to:** OpenShift Console > Observe > Incidents

**Show:**
- A single incident grouping all cascade-related alerts
- COO identified the NRF alert as the root signal; downstream alerts are correlated into one incident
- Incident timeline shows alert firing order
- One incident = one ticket, instead of 5 separate pages to oncall

**Key lesson:** COO eliminates alert fatigue and war rooms. The operator sees one incident with full context instead of 5 disconnected pages.

---

## Stage 5: Distributed Tracing

**Goal:** Show a request-level view of the failure.

**Navigate to:** OpenShift Console > Observe > Traces

**Show:**
- Filter traces by `acme-5gc-edge` namespace
- Find a failed session establishment trace (long duration, error span)
- Drill into the span tree: the request enters AMF, reaches NRF for service discovery, NRF call fails, no retry, AMF returns error
- The exact line of failure is visible at the span level

**Key lesson:** Metrics told us NRF was degraded. Traces show exactly which request paths are failing and where in the call chain. No log grepping needed.

---

## Stage 6: Network Observability

**Goal:** Show network-level signal for the NRF failure.

**Navigate to:** OpenShift Console > Observe > Network Traffic

**Show:**
- Filter by namespace `acme-5gc-edge`
- Show TCP retransmission spikes between AMF/SMF/UPF pods and NRF
- Show dropped connection flows on NRF egress to DB (connection pool exhaustion manifests as TCP resets)
- Network flows confirm what metrics and traces suggested

**Key lesson:** Network observability adds a fourth signal layer. Some failures are invisible to logs and metrics but show clearly in packet-level flow data (e.g., DB connection exhaustion).

---

## Stage 7: AI-Assisted Troubleshooting with Lightspeed

**Goal:** Show the full COO + Lightspeed integration — root cause in natural language.

**Navigate to:** OpenShift Console > click the **?** (help) icon > OpenShift Lightspeed

**Show:**
- Ask: *"What is causing the current incident in acme-5gc-edge?"*
- Lightspeed reads the active incident via the MCP server (Cluster Health Analyzer)
- Response identifies: NRF DB connection pool exhaustion → cascade to AMF/SMF/UPF → recommended fix (increase pool size or restart NRF)
- Lightspeed can also suggest `oc` commands to confirm the state

**Key lesson:** COO feeds structured incident context to Lightspeed via MCP. The AI answer is grounded in real cluster state — not hallucinated. What took 30 minutes of war room time now takes 90 seconds.

---

## 5G NOC Dashboard Reference

The 5G NOC Dashboard (`5g-noc` namespace, route `dashboard`) is a live-simulation NOC display. All data is client-side simulated — no backend required. Key panels:

| Panel | What it shows |
|---|---|
| Metrics Summary | Edge sites, nodes, Core NF CPU, sessions, gNB count, UPF throughput with sparkline history |
| SLA Panel | 5 3GPP KPIs with thresholds (SESR ≥99.5%, RRC CSR ≥99.7%, HOSR ≥99.5%, PRB Util ≤75%, E2E Latency P95 ≤20ms) |
| Network Slice Dashboard | eMBB (broadband), URLLC (ultra-low latency), mMTC (IoT) — per-slice metrics |
| Incident Banner | Real-time fault impact: affected regions, user count, estimated revenue loss/min |
| Network Map | Geographic Leaflet map + SVG schematic with 4-tier hierarchy (National DC → Regional DC → Edge → Cell) |
| Alert Feed | Live severity-stamped alerts, acknowledge critical, alert count |
| Worst Performers | Top 8 nodes by status/CPU/sessions |
| xApp/rApp Panel | O-RAN automation (QoE Optimizer, MLB, Energy Saving, Anomaly Detector) |
| Fault Injection Controls | Pre-configured scenarios; use **NRF Cascade** for this demo |
| Country/Carrier Selector | 40+ combinations across Americas |

**Role in the demo:** The NOC Dashboard gives attendees a "big picture" view of the simulated 5G network degrading. Inject the NRF cascade fault here first, then pivot to OpenShift Console to show COO detecting and correlating it.
