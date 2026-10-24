#!/usr/bin/env python3
"""Tenant-scope the role's packaged deployment resources."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

REQUIRED_IMAGES = {"frontend", "bff", "proxy", "orders-api", "inventory-api", "notifications-api"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--source-namespace", required=True)
    parser.add_argument("--attendee-id", required=True)
    parser.add_argument("--keycloak-origin", required=True)
    parser.add_argument("--realm", required=True)
    parser.add_argument("--route-domain", required=True)
    parser.add_argument("--reserved-namespaces-json", required=True)
    parser.add_argument("--images-json", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def rewrite_service_names(value: object, source_namespace: str) -> object:
    if isinstance(value, str):
        # All app-to-app calls are namespace-local after tenantization. Short
        # service names avoid assuming a cluster DNS suffix.
        return re.sub(rf"\.{re.escape(source_namespace)}\.svc(?=[:/]|$)", "", value)
    if isinstance(value, list):
        return [rewrite_service_names(item, source_namespace) for item in value]
    if isinstance(value, dict):
        return {key: rewrite_service_names(item, source_namespace) for key, item in value.items()}
    return value


def main() -> None:
    args = parse_args()
    reserved_namespaces = json.loads(args.reserved_namespaces_json)
    if not isinstance(reserved_namespaces, list) or any(not isinstance(value, str) for value in reserved_namespaces):
        raise SystemExit("reserved namespaces must be a JSON array of strings")
    if args.namespace in {"default", "openshift"} or args.namespace.startswith("openshift-") or args.namespace in reserved_namespaces:
        raise SystemExit("Refusing a system or configured shared namespace")
    if not re.fullmatch(r"[a-z0-9]([-a-z0-9]*[a-z0-9])?", args.namespace) or len(args.namespace) > 63:
        raise SystemExit("namespace must be a DNS label no longer than 63 characters")
    if not re.fullmatch(r"[a-z0-9]([-a-z0-9]*[a-z0-9])?", args.attendee_id) or len(args.attendee_id) > 43:
        raise SystemExit("attendee ID must be a DNS label no longer than 43 characters")
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+(?::[0-9]+)?", args.keycloak_origin):
        raise SystemExit("Keycloak origin must be an HTTPS origin")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.realm) or len(args.realm) > 63:
        raise SystemExit("realm name must contain only letters, digits, dots, underscores, or hyphens")
    if not re.fullmatch(r"[A-Za-z0-9.-]+", args.route_domain) or len(args.route_domain) > 198:
        raise SystemExit("route domain must be a DNS name")

    images = json.loads(args.images_json.read_text(encoding="utf-8"))
    if set(images) != REQUIRED_IMAGES or any(
        not re.fullmatch(r"[A-Za-z0-9._/:+-]+@sha256:[a-f0-9]{64}", str(image)) for image in images.values()
    ):
        raise SystemExit("all six image references must be immutable SHA-256 digests")

    issuer = f"{args.keycloak_origin}/realms/{args.realm}"
    hosts = {
        "frontend": f"spa-{args.attendee_id}.{args.route_domain}",
        "bff": f"bff-{args.attendee_id}.{args.route_domain}",
        "proxy": f"proxy-{args.attendee_id}.{args.route_domain}",
        "orders-api": f"orders-api-{args.attendee_id}.{args.route_domain}",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    objects: list[dict] = []
    used_images: set[str] = set()
    for item in yaml.safe_load_all(Path(__file__).with_name("workload-resources.yaml").read_text(encoding="utf-8")):
        if not item:
            continue
        meta = item.setdefault("metadata", {})
        meta["namespace"] = args.namespace
        meta.setdefault("labels", {}).update(
            {
                "app.kubernetes.io/part-of": "rhbk-workshop",
                "app.kubernetes.io/managed-by": "ansible",
                "rhbk-workshop/managed": "true",
                "rhbk-workshop/attendee": args.attendee_id,
            }
        )
        kind, name = item.get("kind"), meta.get("name")
        # The role renders this ConfigMap as a location-only snippet for
        # the image's include context. Do not apply the base server block
        # here and overwrite it on every subsequent reconciliation.
        if kind == "ConfigMap" and name == "frontend-nginx-config":
            continue
        if kind == "Deployment":
            pod_spec = item.get("spec", {}).get("template", {}).get("spec", {})
            for container in pod_spec.get("containers", []):
                container_name = container.get("name")
                if container_name in images:
                    container["image"] = images[container_name]
                    used_images.add(container_name)
                elif container_name == "nginx":
                    container["image"] = images["proxy"]
                    used_images.add("proxy")
            if name == "proxy-redis":
                pod_spec["containers"][0]["image"] = (
                    "docker.io/library/redis@sha256:f773b35a95e170d92dd4214a3ec4859b1b7960bf56896ae687646d695f311187"
                )
        if kind == "Route" and name in hosts:
            item.setdefault("spec", {})["host"] = hosts[name]
        if kind == "ConfigMap":
            data = item.setdefault("data", {})
            if name == "frontend-runtime-config" and "config.json" in data:
                config = json.loads(data["config.json"])
                config.update(
                    {
                        "issuer": issuer,
                        "spaClientId": "spa",
                        "ordersBaseUrl": f"https://{hosts['orders-api']}",
                        "legacyBaseUrl": "",
                        "legacyEnabled": False,
                    }
                )
                data["config.json"] = json.dumps(config, separators=(",", ":"))
            if "default.conf" in data:
                data["default.conf"] = data["default.conf"].replace(
                    "https://issuer.invalid", args.keycloak_origin
                ).replace("https://orders.apps.invalid", f"https://{hosts['orders-api']}")
            for key in ("ISSUER", "WORKSHOP_ISSUER"):
                if key in data:
                    data[key] = issuer
            for key, service in (
                ("INVENTORY_API_URL", "inventory-api"),
                ("NOTIFICATIONS_API_URL", "notifications-api"),
            ):
                if key in data:
                    data[key] = f"http://{service}:8080"
            if "SPA_ORIGIN" in data:
                data["SPA_ORIGIN"] = f"https://{hosts['frontend']}"
        objects.append(rewrite_service_names(item, args.source_namespace))

    if used_images != REQUIRED_IMAGES:
        missing = ", ".join(sorted(REQUIRED_IMAGES - used_images))
        raise SystemExit(f"rendered application bases did not contain image targets: {missing}")

    output = args.output_dir / "workloads.yaml"
    output.write_text(
        "---\n".join(yaml.safe_dump(item, sort_keys=False) for item in objects),
        encoding="utf-8",
    )
    output.chmod(0o600)


if __name__ == "__main__":
    main()
