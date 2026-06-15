# Showcasing MLflow

How to demo the MLflow feature deployed by this role (RHOAI 3.4+). MLflow adds
**experiment tracking**, a **model registry**, and **MLflow Workspaces** to
OpenShift AI — so a data scientist can log runs (params, metrics, artifacts),
compare experiments, and register models, all governed by OpenShift RBAC.

This feature is **opt-in**. Enable it with:

```yaml
ocp4_workload_rhoai3x_mlflow_deploy: true
```

When enabled, the role:
- Sets the DSC `mlflowoperator` component to `Managed`.
- Creates an `MLflow` CR (`mlflow.opendatahub.io/v1`) named `mlflow` in
  `redhat-ods-applications` (the operator's fixed `targetNamespace`).
- Backs metadata with **SQLite on a PVC** (`10Gi` by default) and artifacts with
  the **MinIO** bucket from Stage 1 (`rhoai-models`).

Auth is **OpenShift RBAC**: every MLflow API call does a `SelfSubjectAccessReview`
with the caller's bearer token against the target project namespace. A
**Workspace** maps 1:1 to an OpenShift **project** — users with `admin`/`edit`/
`view` on a project get the matching MLflow permissions automatically.

---

## 1. The dashboard story (no CLI)

1. **OpenShift AI dashboard → Experiments / MLflow** (or the OCP console
   **Application Menu → OpenShift Self Managed Services → MLflow**) opens the
   MLflow UI under the data science gateway.
2. Show the **Experiments** list, drill into a **run** — parameters, metrics,
   and logged **artifacts** (served from MinIO through the artifact proxy).
3. Show the **Models** tab — a registered model with versions and stage
   transitions (None → Staging → Production).

---

## 2. The CLI / SDK story (log a run end-to-end)

MLflow on RHOAI uses OpenShift OAuth token auth; the token must be refreshed per
session. The tracking URI is path-routed under the data science gateway.

```bash
# --- a) Point the SDK at the in-cluster MLflow + authenticate ---
export MLFLOW_TRACKING_URI="https://data-science-gateway.$(oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}')/mlflow"
export MLFLOW_TRACKING_TOKEN="$(oc whoami --show-token)"
# Workspace == an OpenShift project you have at least edit on:
export MLFLOW_WORKSPACE="rhoai-shared"
```

```python
# --- b) Log a sample run (pip install mlflow) ---
import mlflow

mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
mlflow.set_experiment("phase2-demo")

with mlflow.start_run(run_name="hello-mlflow"):
    mlflow.log_param("alpha", 0.5)
    mlflow.log_metric("rmse", 0.27)
    mlflow.log_metric("rmse", 0.21, step=1)          # a second point on the curve
    with open("notes.txt", "w") as f:
        f.write("logged from the rhoai3x MLflow showcase")
    mlflow.log_artifact("notes.txt")                  # -> MinIO via the artifact proxy
    print("run:", mlflow.active_run().info.run_id)
```

```python
# --- c) Register the model in the MLflow Model Registry ---
import mlflow.sklearn
from sklearn.linear_model import LinearRegression

model = LinearRegression().fit([[0], [1], [2]], [0, 1, 2])
with mlflow.start_run(run_name="register-demo"):
    mlflow.sklearn.log_model(
        model, artifact_path="model",
        registered_model_name="demo-linreg",
    )
```

Refresh the **Experiments** and **Models** tabs in the dashboard to see the run,
the metric curve, the `notes.txt` artifact, and the registered `demo-linreg`
model appear live.

---

## 3. Talking points

- **Governed by OpenShift RBAC** — no separate MLflow user store; project roles
  *are* the MLflow permissions. Demo this by switching to a user with only `view`
  on `rhoai-shared` — they can read runs but not write.
- **Workspaces == projects** — `MLFLOW_WORKSPACE` selects the namespace whose
  RBAC governs the call; switch it to show per-project isolation.
- **Artifacts via MinIO** — logged artifacts land in the `rhoai-models` bucket
  through MLflow's artifact proxy (the SDK never talks to MinIO directly).
- **Pairs with the pipeline + model features** — log training runs from an
  AI Pipeline, then deploy the registered model via KServe (the role's
  `model_deployment.yml`).

---

## 4. Teardown

`remove_workload.yml` deletes the `MLflow` CR (gated on
`ocp4_workload_rhoai3x_mlflow_deploy`). The operator is disabled by setting the
DSC `mlflowoperator` component back to `Removed` when the flag is false. The
backing PVC in `redhat-ods-applications` is removed with the namespace during the
RHOAI teardown.
