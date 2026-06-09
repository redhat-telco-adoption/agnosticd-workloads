# Showcasing Models-as-a-Service (MaaS)

How to demo the Models-as-a-Service feature deployed by this role (RHOAI 3.4+).
MaaS turns a deployed model into a **governed, metered, OpenAI-compatible
endpoint**: users authenticate with an API key, their consumption is capped by a
**subscription** (token rate limits) and gated by an **authorization policy**
(group access), and all usage is **tracked** for cost attribution.

This is what the `ocp4_workload_rhoai3x_maas_*` feature provisions:
- A model published to MaaS (`LLMInferenceService` → `MaaSModelRef`), by default
  `gpt-oss-20b` on a dedicated GPU.
- A `MaaSSubscription` granting the group `rhoai-users` a token rate limit
  (default `1,000,000` tokens / `1h`), and a `MaaSAuthPolicy` granting that group
  endpoint access.
- The API gateway (`maas-default-gateway`) exposed at
  `https://maas.<cluster-apps-domain>`, backed by Kuadrant (Authorino auth +
  Limitador rate limiting).

> Set `MAAS_HOST=maas.$(oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}')`
> to get the gateway host for the commands below.

---

## 1. The dashboard story (no CLI)

**Admin view — governance:**
1. **Gen AI studio → AI asset endpoints → Models** — the published model appears
   with Use case `chat` and Status `Ready`.
2. **Settings / Models-as-a-Service** (admin) — show the **Subscriptions** and
   **Authorization Policies** (enabled by `modelAsService: true` +
   `maasAuthPolicies: true`). Point out the token rate limit and the
   `rhoai-users` group binding.

**User view — consume:**
1. **AI asset endpoints → Models →** click **View** under *Endpoints*. The dialog
   shows a **"Model as a Service"** badge, the external endpoint URL, and a
   **Subscription** selector.
2. Click **Generate API key** (a 1-hour `sk-oai-…` key) — copy it.
3. Click **Try in playground** (or **Gen AI studio → Playground**) to chat with
   the model live.
4. **Gen AI studio → API keys** — create/list/revoke keys with custom expiry.

---

## 2. The CLI story (get a token, call the model, see usage)

```bash
export MAAS_HOST="maas.$(oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}')"

# --- a) Authenticate (OpenShift user token; must be in the subscription group) ---
export OC_TOKEN=$(oc whoami -t)

# --- b) Discover models you can access (user token works for listing) ---
curl -sk -H "Authorization: Bearer ${OC_TOKEN}" \
  "https://${MAAS_HOST}/maas-api/v1/models" | jq
#   -> { "data": [ { "id": "gpt-oss-20b", "ready": true,
#                    "url": ".../rhoai-shared/maas-gpt-oss-20b",
#                    "subscriptions": [ { "name": "rhoai-team" } ] } ] }

# --- c) List your subscriptions ---
curl -sk -H "Authorization: Bearer ${OC_TOKEN}" \
  "https://${MAAS_HOST}/maas-api/v1/subscriptions" | jq

# --- d) Create an API key bound to a subscription ---
export MAAS_API_KEY=$(curl -sk -X POST "https://${MAAS_HOST}/maas-api/v1/api-keys" \
  -H "Authorization: Bearer ${OC_TOKEN}" -H "Content-Type: application/json" \
  -d '{"name":"demo","subscription":"rhoai-team","expiresInDays":1}' | jq -r .key)
echo "key: ${MAAS_API_KEY:0:12}..."   # sk-oai-...

# --- e) Inference (OpenAI-compatible). NOTE: inference requires the sk-oai key;
#         the raw OpenShift token returns 401 here on purpose. ---
curl -sk -X POST \
  "https://${MAAS_HOST}/rhoai-shared/maas-gpt-oss-20b/v1/chat/completions" \
  -H "Authorization: Bearer ${MAAS_API_KEY}" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-20b",
       "messages":[{"role":"user","content":"What is Red Hat OpenShift AI?"}],
       "max_tokens":400}' | jq '{content: .choices[0].message.content, usage}'
```

The response `usage` block (`prompt_tokens` / `completion_tokens` / `total_tokens`)
is the per-request meter that feeds the subscription quota.

> **gpt-oss-20b is a reasoning model.** With a small `max_tokens` the answer can
> land in `choices[0].message.reasoning` (and `content` is `null`,
> `finish_reason: length`). Use `max_tokens >= 300` to get a final `content`.

**Endpoint path shape:** `https://<MAAS_HOST>/<model-namespace>/<llmisvc-name>/v1/...`
(the exact `url` is returned by `/maas-api/v1/models`). It serves the full
OpenAI surface: `/v1/models`, `/v1/chat/completions`, `/v1/completions`.

**Revoke** a demo key when done:
```bash
curl -sk -X POST "https://${MAAS_HOST}/maas-api/v1/api-keys/bulk-revoke" \
  -H "Authorization: Bearer ${OC_TOKEN}" -H "Content-Type: application/json" \
  -d "{\"username\":\"$(oc whoami)\"}"
```

---

## 3. Showcasing the governance (the "as a Service" part)

**Token rate limits (quota enforcement):** when a subscription's token limit for
the window is exhausted, inference returns **HTTP 429**:
```json
{ "error": { "message": "Token limit exceeded...", "type": "token_limit_error", "code": 429 } }
```
with headers `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`,
`Retry-After`. To demo this quickly, deploy with a tiny limit
(`ocp4_workload_rhoai3x_maas_token_limit: 2000`,
`ocp4_workload_rhoai3x_maas_token_window: "1m"`) and run a few large requests.

**Access control:** both a **subscription** (quota) *and* an **authorization
policy** (group access) are required. A user not in `rhoai-users` is rejected at
the gateway — good for demonstrating least-privilege. Subscriptions are assigned
automatically by OpenShift **group membership**.

**Multiple tiers:** create a second `MaaSSubscription` (higher token limit,
higher `priority`) for a different group to show tiered access.

---

## 4. Tracking usage

**a) Observability dashboard (Tech Preview)** — requires the observability
**backend** (Option B), enabled by `ocp4_workload_rhoai3x_maas_observability_deploy: true`.
This both deploys the backend (**Cluster Observability Operator** *and* the
**Red Hat build of OpenTelemetry** operator + the RHOAI monitoring stack in
`redhat-ods-monitoring` + Kuadrant observability + Tenant telemetry) and turns on
the `observabilityDashboard` UI flag. Both operators are required — without the
OpenTelemetry operator the RHOAI `default-monitoring` CR blocks on
`OpenTelemetryCollector operator must be installed` and no Thanos/Prometheus deploys. **Do not** set the UI flag without
the backend — that produces the "Service Unavailable" page (the deploy flag now
gates the UI flag for exactly this reason).

- **Observe & monitor → Dashboard → Usage tab** (admin-only; rendered with Perses,
  queries Thanos Querier).
- Overview: **Total Tokens, Total Requests, Total Errors, Success Rate, Active Users**.
- **Token Consumption by User** table: per User / Subscription / Model — Tokens,
  Requests, and **Rate Limited** (429) counts. Filter by user/subscription/model
  and time range (5m … 14d).
- Per-user attribution requires `ocp4_workload_rhoai3x_maas_telemetry_capture_user: true`
  (it is `false` by default — privacy + Prometheus cardinality).
- Metrics only appear **after** models are accessed; an empty dashboard before any
  inference is expected. It is **showback, not billing-grade** — for precise
  chargeback read the Limitador metrics endpoint directly.

> Heavy, cluster-wide change. COO may be shared with `coo_incident_detection`;
> teardown leaves COO intact unless `..._maas_observability_remove_coo: true`.

**b) Prometheus metrics (User Workload Monitoring)** — scraped from
Limitador/Authorino/gateway. Query in **Observe → Metrics**:

| Metric | Meaning | Labels |
|---|---|---|
| `authorized_hits` | tokens consumed (successful requests) | subscription, model, limitador_namespace |
| `authorized_calls` | API requests that passed auth + rate limiting | subscription, limitador_namespace |
| `limited_calls` | requests rejected by rate limiting (429) | limitador_namespace |
| `istio_request_duration_milliseconds_bucket` | gateway latency | subscription |
| `auth_server_authconfig_duration_seconds` | Authorino auth time | authorization policy |

Example PromQL — tokens per subscription over the last hour:
`sum by (subscription) (increase(authorized_hits[1h]))`

**c) Per-request** — the `usage` field in every inference response.

---

## 5. Quick health/verification (presenter pre-flight)

```bash
# tenant + components healthy
oc get tenant default-tenant -n models-as-a-service
oc get pods -n redhat-ods-applications -l app.kubernetes.io/name=maas-api
# model published & ready
oc get llminferenceservice maas-gpt-oss-20b -n rhoai-shared
oc get maasmodelref,maassubscription -A | grep -i maas
# gateway reachable + auth enforced (expect 401 without a key)
curl -sk -o /dev/null -w "%{http_code}\n" "https://${MAAS_HOST}/maas-api/v1/models"
```

Expected: tenant `Ready=True`, `maas-api` 1/1, LLMInferenceService `Ready`,
and a `401` on the unauthenticated gateway call.

---

## 6. Knobs (role variables)

| Variable | Default | Use in a demo |
|---|---|---|
| `..._maas_enable` | `false` | master switch |
| `..._maas_publish_sample` | `true` | deploy + publish the sample model |
| `..._maas_subscription_group` | `rhoai-users` | group granted access |
| `..._maas_subscription_group_users` | `[admin]` | members (must be OpenShift users) |
| `..._maas_token_limit` | `1000000` | tokens per window (lower to demo 429) |
| `..._maas_token_window` | `1h` | window (`s`/`m`/`h` only, e.g. `24h`) |
| `..._maas_observability_dashboard` | `true` | the Usage dashboard |
| `..._maas_sample_display_name` | `gpt-oss-20b (MaaS)` | name shown in the dashboard |

See `docs/maas-feature-plan.md` for the full architecture and
`distilled/.../Govern_LLM_access_with_Models-as-a-Service-en-US/` for the
upstream docs.
