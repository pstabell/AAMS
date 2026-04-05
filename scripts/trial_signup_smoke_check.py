#!/usr/bin/env python3
"""Smoke-check the AMS-APP trial signup stack.

This script is intentionally lightweight so it can run in CI, on Render shells,
or from a local workstation without extra dependencies.

Checks performed:
1. Reachability of the public app URL.
2. Reachability of the public webhook health URL.
3. Multi-endpoint probing of the public webhook service to distinguish
   "wrong path" from "wrong deployment / service misconfiguration".
4. Presence of the key local environment variables needed for a live e2e test.
5. Local Flask route verification for webhook_server /health.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from glob import glob
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_JSON_ARTIFACT = ROOT / "docs" / "smoke-checks" / "latest-trial-signup-smoke-check.json"
DEFAULT_OWNER_READY_DIR = ROOT / "docs" / "smoke-checks" / "owner-ready"
DEFAULT_OWNER_READY_ARCHIVE_DIR = DEFAULT_OWNER_READY_DIR / "archive"
DEFAULT_ESCALATION_PACKET_DIR = ROOT / "docs" / "smoke-checks" / "escalation-packet"
DEFAULT_ESCALATION_PACKET_ARCHIVE_DIR = DEFAULT_ESCALATION_PACKET_DIR / "archive"

APP_URL = os.getenv("RENDER_APP_URL", "https://commission-tracker-app.onrender.com")
WEBHOOK_URL = os.getenv(
    "RENDER_WEBHOOK_URL",
    "https://commission-tracker-webhook.onrender.com/health",
)
WEBHOOK_BASE_URL = os.getenv(
    "RENDER_WEBHOOK_BASE_URL",
    WEBHOOK_URL.rsplit("/health", 1)[0] if WEBHOOK_URL.endswith("/health") else WEBHOOK_URL.rstrip("/"),
)
WEBHOOK_DIAGNOSTIC_PATHS = ["/", "/health", "/test", "/stripe-webhook"]

LIVE_E2E_ENV_VARS = [
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "STRIPE_PRICE_ID",
    "RESEND_API_KEY",
    "SUPABASE_SERVICE_KEY",
]

CHECKOUT_CONTRACT_DEFAULTS = {
    "accepted_at": "2026-04-02T00:00:00+00:00",
    "email": "smoke-check@example.com",
    "app_url": APP_URL.rstrip("/"),
}

OPTIONAL_ENV_VARS = [
    "APP_ENVIRONMENT",
    "PRODUCTION_SUPABASE_URL",
    "PRODUCTION_SUPABASE_ANON_KEY",
    "PRODUCTION_SUPABASE_SERVICE_KEY",
]

RENDER_BLUEPRINT_SERVICES = {
    "commission-tracker-app": {
        "runtime": "python",
        "plan": "starter",
        "autoDeploy": True,
        "buildCommand": "pip install -r requirements.txt",
        "startCommand": "streamlit run commission_app.py --server.port ${PORT} --server.address 0.0.0.0",
        "healthCheckPath": "/",
        "required_env_vars": {
            "APP_ENVIRONMENT",
            "PRODUCTION_SUPABASE_URL",
            "PRODUCTION_SUPABASE_ANON_KEY",
            "PRODUCTION_SUPABASE_SERVICE_KEY",
            "SUPABASE_URL",
            "SUPABASE_ANON_KEY",
            "SUPABASE_SERVICE_KEY",
            "STRIPE_SECRET_KEY",
            "STRIPE_PRICE_ID",
            "RESEND_API_KEY",
            "RENDER_APP_URL",
        },
    },
    "commission-tracker-webhook": {
        "runtime": "python",
        "plan": "starter",
        "autoDeploy": True,
        "buildCommand": "pip install -r requirements.txt",
        "startCommand": "gunicorn webhook_server:app --bind 0.0.0.0:${PORT}",
        "healthCheckPath": "/health",
        "required_env_vars": {
            "APP_ENVIRONMENT",
            "PRODUCTION_SUPABASE_URL",
            "PRODUCTION_SUPABASE_ANON_KEY",
            "PRODUCTION_SUPABASE_SERVICE_KEY",
            "SUPABASE_URL",
            "SUPABASE_ANON_KEY",
            "SUPABASE_SERVICE_KEY",
            "STRIPE_SECRET_KEY",
            "STRIPE_WEBHOOK_SECRET",
            "STRIPE_PRICE_ID",
            "RESEND_API_KEY",
            "SMTP_HOST",
            "SMTP_PORT",
            "SMTP_USER",
            "SMTP_PASS",
            "FROM_EMAIL",
            "RENDER_APP_URL",
        },
    },
}


def _extract_response_headers(response: Any) -> dict[str, str]:
    headers = getattr(response, "headers", {})
    extracted = {}
    for key in (
        "x-render-routing",
        "x-render-origin-server",
        "server",
        "content-type",
        "cf-ray",
        "date",
    ):
        value = headers.get(key)
        if value:
            extracted[key] = value
    return extracted


def fetch_url(url: str, timeout: int = 15) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "AMS-APP Trial Signup Smoke Check/1.0",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(512).decode("utf-8", errors="replace")
            return {
                "ok": 200 <= response.status < 400,
                "status": response.status,
                "reason": getattr(response, "reason", "OK"),
                "body_preview": body,
                "headers": _extract_response_headers(response),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(512).decode("utf-8", errors="replace")
        return {
            "ok": False,
            "status": exc.code,
            "reason": exc.reason,
            "body_preview": body,
            "headers": _extract_response_headers(exc),
        }
    except Exception as exc:  # pragma: no cover - defensive failure reporting
        return {
            "ok": False,
            "status": None,
            "reason": type(exc).__name__,
            "body_preview": str(exc),
            "headers": {},
        }


def inspect_env_var(name: str) -> dict[str, Any]:
    value = os.getenv(name)
    return {
        "present": bool(value),
        "length": len(value) if value else 0,
    }


def build_webhook_diagnostic_urls(base_url: str) -> list[str]:
    normalized = base_url.rstrip("/")
    if not normalized:
        return []
    return [f"{normalized}{path}" if path != "/" else f"{normalized}/" for path in WEBHOOK_DIAGNOSTIC_PATHS]


def diagnose_public_webhook(base_url: str) -> dict[str, Any]:
    endpoints = {url: fetch_url(url) for url in build_webhook_diagnostic_urls(base_url)}
    any_ok = any(result["ok"] for result in endpoints.values())
    statuses = [result["status"] for result in endpoints.values() if result["status"] is not None]
    all_404 = bool(statuses) and all(status == 404 for status in statuses)
    render_routing_modes = sorted(
        {
            result.get("headers", {}).get("x-render-routing")
            for result in endpoints.values()
            if result.get("headers", {}).get("x-render-routing")
        }
    )
    no_server = "no-server" in render_routing_modes

    if any_ok:
        likely_cause = "Webhook service is reachable; the configured health URL may be wrong."
    elif no_server:
        likely_cause = (
            "Render is reporting x-render-routing=no-server for the webhook hostname. "
            "That usually means there is no healthy backend service attached to this route yet "
            "or the service is not deployed behind the expected domain."
        )
    elif all_404:
        likely_cause = (
            "All probed webhook endpoints returned 404. The Render service is likely misrouted, "
            "pointing at the wrong app, or not using webhook_server:app."
        )
    else:
        likely_cause = "Webhook service is unavailable or failing before route handling."

    return {
        "base_url": base_url,
        "probed_endpoints": endpoints,
        "any_ok": any_ok,
        "all_404": all_404,
        "render_routing_modes": render_routing_modes,
        "no_server": no_server,
        "likely_cause": likely_cause,
    }


def check_local_dependencies() -> dict[str, Any]:
    required_modules = ["flask", "stripe", "supabase"]
    missing = []

    for module_name in required_modules:
        try:
            __import__(module_name)
        except Exception:
            missing.append(module_name)

    return {
        "ok": not missing,
        "missing_modules": missing,
    }


def check_local_webhook_route() -> dict[str, Any]:
    dependency_check = check_local_dependencies()
    if not dependency_check["ok"]:
        return {
            "ok": False,
            "status": None,
            "payload": "Local Python dependencies missing for webhook import",
            "dependency_check": dependency_check,
        }

    try:
        from webhook_server import app

        with app.test_client() as client:
            response = client.get("/health")
            payload = response.get_json(silent=True)
            return {
                "ok": response.status_code == 200,
                "status": response.status_code,
                "payload": payload,
                "dependency_check": dependency_check,
            }
    except Exception as exc:  # pragma: no cover - defensive failure reporting
        return {
            "ok": False,
            "status": None,
            "payload": str(exc),
            "dependency_check": dependency_check,
        }


def check_webhook_service_contract() -> dict[str, Any]:
    required_routes = {
        "/": "home",
        "/health": "health_check",
        "/test": "test_endpoint",
        "/stripe-webhook": "stripe_webhook",
    }
    required_packages = {"flask", "stripe", "supabase", "gunicorn"}

    problems: list[str] = []

    try:
        webhook_source = (ROOT / "webhook_server.py").read_text(encoding="utf-8")
    except FileNotFoundError:
        return {
            "ok": False,
            "status": None,
            "payload": "webhook_server.py is missing",
            "routes": {},
            "requirements": {},
        }

    discovered_routes: dict[str, dict[str, Any]] = {}
    for route, handler in required_routes.items():
        route_present = f"@app.route('{route}'" in webhook_source or f'@app.route("{route}"' in webhook_source
        handler_present = f"def {handler}(" in webhook_source
        discovered_routes[route] = {
            "handler": handler,
            "route_present": route_present,
            "handler_present": handler_present,
            "ok": route_present and handler_present,
        }
        if not discovered_routes[route]["ok"]:
            problems.append(f"Missing webhook route contract for {route} -> {handler}")

    try:
        requirements_lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return {
            "ok": False,
            "status": None,
            "payload": "requirements.txt is missing",
            "routes": discovered_routes,
            "requirements": {},
        }

    normalized_requirements = {
        line.strip().split("==", 1)[0].split(">=", 1)[0].strip().lower()
        for line in requirements_lines
        if line.strip() and not line.strip().startswith("#")
    }
    requirements_status = {
        package: package in normalized_requirements for package in sorted(required_packages)
    }
    missing_packages = [package for package, present in requirements_status.items() if not present]
    if missing_packages:
        problems.append("requirements.txt is missing packages: " + ", ".join(missing_packages))

    return {
        "ok": not problems,
        "status": 200 if not problems else 500,
        "payload": "Webhook service contract looks complete" if not problems else "; ".join(problems),
        "routes": discovered_routes,
        "requirements": requirements_status,
        "missing_packages": missing_packages,
    }


def check_render_blueprint() -> dict[str, Any]:
    try:
        render_yaml = (ROOT / "render.yaml").read_text(encoding="utf-8")
    except FileNotFoundError:
        return {
            "ok": False,
            "status": None,
            "payload": "render.yaml is missing",
            "services": {},
        }

    discovered_services: dict[str, dict[str, Any]] = {}
    service_matches = list(
        re.finditer(
            r"- type:\s*web\s+name:\s*(?P<name>[^\n]+)(?P<body>.*?)(?=\n\s*- type:\s*web\s+name:|\Z)",
            render_yaml,
            re.DOTALL,
        )
    )

    for match in service_matches:
        name = match.group("name").strip()
        body = match.group("body")
        runtime_match = re.search(r"runtime:\s*(.+)", body)
        plan_match = re.search(r"plan:\s*(.+)", body)
        auto_deploy_match = re.search(r"autoDeploy:\s*(.+)", body)
        build_command_match = re.search(r"buildCommand:\s*(.+)", body)
        start_command_match = re.search(r"startCommand:\s*(.+)", body)
        health_path_match = re.search(r"healthCheckPath:\s*(.+)", body)
        env_keys = set(re.findall(r"- key:\s*([^\n]+)", body))
        expected = RENDER_BLUEPRINT_SERVICES.get(name)
        missing_env = sorted(expected["required_env_vars"] - env_keys) if expected else []
        runtime = runtime_match.group(1).strip() if runtime_match else None
        plan = plan_match.group(1).strip() if plan_match else None
        auto_deploy = auto_deploy_match.group(1).strip().lower() == "true" if auto_deploy_match else None
        build_command = build_command_match.group(1).strip() if build_command_match else None
        start_command = start_command_match.group(1).strip() if start_command_match else None
        health_check_path = health_path_match.group(1).strip() if health_path_match else None
        discovered_services[name] = {
            "present": True,
            "runtime": runtime,
            "plan": plan,
            "auto_deploy": auto_deploy,
            "build_command": build_command,
            "start_command": start_command,
            "health_check_path": health_check_path,
            "env_vars": sorted(env_keys),
            "missing_required_env_vars": missing_env,
            "runtime_ok": bool(expected and runtime == expected["runtime"]),
            "plan_ok": bool(expected and plan == expected["plan"]),
            "auto_deploy_ok": bool(expected and auto_deploy == expected["autoDeploy"]),
            "build_command_ok": bool(expected and build_command == expected["buildCommand"]),
            "start_command_ok": bool(expected and start_command == expected["startCommand"]),
            "health_check_path_ok": bool(expected and health_check_path == expected["healthCheckPath"]),
        }

    missing_services = sorted(set(RENDER_BLUEPRINT_SERVICES) - set(discovered_services))
    problems: list[str] = []
    for service_name, expected in RENDER_BLUEPRINT_SERVICES.items():
        service = discovered_services.get(service_name)
        if not service:
            problems.append(f"Missing Render service: {service_name}")
            continue
        if not service["runtime_ok"]:
            problems.append(
                f"{service_name} runtime mismatch: expected {expected['runtime']}, found {service['runtime']}"
            )
        if not service["plan_ok"]:
            problems.append(
                f"{service_name} plan mismatch: expected {expected['plan']}, found {service['plan']}"
            )
        if not service["auto_deploy_ok"]:
            problems.append(
                f"{service_name} autoDeploy mismatch: expected {expected['autoDeploy']}, found {service['auto_deploy']}"
            )
        if not service["build_command_ok"]:
            problems.append(
                f"{service_name} buildCommand mismatch: expected {expected['buildCommand']}, found {service['build_command']}"
            )
        if not service["start_command_ok"]:
            problems.append(
                f"{service_name} startCommand mismatch: expected {expected['startCommand']}, found {service['start_command']}"
            )
        if not service["health_check_path_ok"]:
            problems.append(
                f"{service_name} healthCheckPath mismatch: expected {expected['healthCheckPath']}, found {service['health_check_path']}"
            )
        if service["missing_required_env_vars"]:
            problems.append(
                f"{service_name} missing env vars: {', '.join(service['missing_required_env_vars'])}"
            )

    return {
        "ok": not problems,
        "status": 200 if not problems else 500,
        "payload": "Render blueprint looks complete" if not problems else "; ".join(problems),
        "services": discovered_services,
        "missing_services": missing_services,
    }


def check_checkout_contract() -> dict[str, Any]:
    try:
        from config import SUBSCRIPTION_OFFER

        auth_helpers_source = (ROOT / "auth_helpers.py").read_text(encoding="utf-8")
        match = re.search(
            r"def _build_checkout_kwargs\(.*?\n\s*return dict\((.*?)\n\s*\)\n\n",
            auth_helpers_source,
            re.DOTALL,
        )
        if not match:
            raise ValueError("Could not locate _build_checkout_kwargs in auth_helpers.py")

        checkout_block = re.sub(r"\s+", " ", match.group(1)).strip()
        metadata_keys = sorted(
            key
            for key in ("accepted_terms", "accepted_privacy", "accepted_at", "terms_version", "privacy_version")
            if f"'{key}'" in checkout_block or f'"{key}"' in checkout_block
        )
        contract = {
            "mode": "subscription" if "mode='subscription'" in checkout_block or 'mode="subscription"' in checkout_block else None,
            "trial_period_days": SUBSCRIPTION_OFFER["trial_days"] if "subscription_data={'trial_period_days': SUBSCRIPTION_OFFER['trial_days']}" in checkout_block or 'subscription_data={"trial_period_days": SUBSCRIPTION_OFFER["trial_days"]}' in checkout_block else None,
            "payment_method_collection": "if_required" if "payment_method_collection='if_required'" in checkout_block or 'payment_method_collection="if_required"' in checkout_block else None,
            "allow_promotion_codes": "allow_promotion_codes=True" in checkout_block,
            "success_url": CHECKOUT_CONTRACT_DEFAULTS["app_url"] + "/?session_id={CHECKOUT_SESSION_ID}" if "success_url=app_url + '/?session_id={CHECKOUT_SESSION_ID}'" in checkout_block or 'success_url=app_url + "/?session_id={CHECKOUT_SESSION_ID}"' in checkout_block else None,
            "cancel_url": CHECKOUT_CONTRACT_DEFAULTS["app_url"] if "cancel_url=app_url" in checkout_block else None,
            "metadata_keys": metadata_keys,
        }
        expected_trial_days = SUBSCRIPTION_OFFER["trial_days"]
        ok = (
            contract["mode"] == "subscription"
            and contract["trial_period_days"] == expected_trial_days
            and contract["payment_method_collection"] == "if_required"
            and contract["allow_promotion_codes"] is True
            and contract["success_url"] == CHECKOUT_CONTRACT_DEFAULTS["app_url"] + "/?session_id={CHECKOUT_SESSION_ID}"
            and contract["cancel_url"] == CHECKOUT_CONTRACT_DEFAULTS["app_url"]
            and len(contract["metadata_keys"]) == 5
        )
        return {
            "ok": ok,
            "status": 200 if ok else 500,
            "payload": contract,
            "expected_trial_days": expected_trial_days,
            "price_id_source": "env" if os.getenv("STRIPE_PRICE_ID") else "placeholder",
        }
    except Exception as exc:  # pragma: no cover - defensive failure reporting
        return {
            "ok": False,
            "status": None,
            "payload": str(exc),
            "expected_trial_days": None,
            "price_id_source": "env" if os.getenv("STRIPE_PRICE_ID") else "placeholder",
        }


def build_render_restore_checklist(report: dict[str, Any], missing_required: list[str]) -> list[str]:
    diagnostics = report["public_checks"]["webhook_diagnostics"]
    webhook_service = report["local_checks"]["render_blueprint"]["services"].get("commission-tracker-webhook", {})

    checklist = [
        "Open the Render dashboard for service commission-tracker-webhook.",
        f"Confirm the service is attached to {report['webhook_base_url']} and not left on a stale or missing domain binding.",
        f"Confirm the deployed start command is `{webhook_service.get('start_command') or 'gunicorn webhook_server:app'}`.",
        f"Confirm the health check path is `{webhook_service.get('health_check_path') or '/health'}`.",
        "Trigger a manual deploy or blueprint sync if the service is missing, suspended, or attached to the wrong branch.",
        "Watch deploy logs until the service reports a healthy instance and the custom onrender.com hostname is bound.",
        f"Re-run python3 scripts/trial_signup_smoke_check.py against {report['webhook_base_url']} and confirm /health no longer returns x-render-routing=no-server.",
    ]

    if diagnostics["no_server"]:
        checklist.insert(
            2,
            "Render is currently reporting x-render-routing=no-server, so prioritize service/domain attachment before reviewing Flask routes.",
        )

    if missing_required:
        checklist.append(
            "After routing is restored, load the missing live secrets in the verification shell before running a real Stripe test signup: "
            + ", ".join(missing_required)
        )

    checklist.append(
        "When the smoke check turns green, run one real Stripe test-mode signup and capture the session ID, webhook timestamp, and onboarding email evidence."
    )
    return checklist


def build_render_restore_validation_commands(report: dict[str, Any], missing_required: list[str]) -> list[str]:
    commands = [
        f"curl -i {report['webhook_base_url'].rstrip('/')}/health",
        "python3 scripts/trial_signup_smoke_check.py",
    ]

    if missing_required:
        commands.append(
            "export " + " ".join(f"{name}=..." for name in missing_required)
        )

    commands.append(
        "python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md"
    )
    commands.append(
        "python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py test_trial_signup_smoke_check.py"
    )
    return commands


def build_local_webhook_dependency_commands(report: dict[str, Any]) -> list[str]:
    dependency_check = report["local_checks"]["webhook_health_route"].get("dependency_check", {})
    missing_modules = dependency_check.get("missing_modules", [])
    if not missing_modules:
        return []

    install_targets = " ".join(missing_modules)
    return [
        f"python3 -m pip install {install_targets}",
        "python3 -m pip install -r requirements.txt",
        "python3 - <<'PY'\nfrom webhook_server import app\nclient = app.test_client()\nresp = client.get('/health')\nprint(resp.status_code)\nprint(resp.get_json(silent=True))\nPY",
    ]


def build_render_service_env_gap(report: dict[str, Any]) -> dict[str, Any]:
    service_gaps: dict[str, Any] = {}
    required_env = report["env"]["required_for_live_e2e"]
    optional_env = report["env"]["optional_context"]
    blueprint_services = report["local_checks"]["render_blueprint"].get("services", {})

    for service_name, expected in RENDER_BLUEPRINT_SERVICES.items():
        blueprint_service = blueprint_services.get(service_name, {})
        missing_in_shell = []
        present_in_shell = []
        missing_in_blueprint = list(blueprint_service.get("missing_required_env_vars", []))

        for env_name in sorted(expected["required_env_vars"]):
            env_details = required_env.get(env_name) or optional_env.get(env_name) or inspect_env_var(env_name)
            if env_details["present"]:
                present_in_shell.append(env_name)
            else:
                missing_in_shell.append(env_name)

        service_gaps[service_name] = {
            "blueprint_present": blueprint_service.get("present", False),
            "start_command": blueprint_service.get("start_command") or expected["startCommand"],
            "health_check_path": blueprint_service.get("health_check_path") or expected["healthCheckPath"],
            "missing_in_blueprint": missing_in_blueprint,
            "missing_in_shell": missing_in_shell,
            "present_in_shell": present_in_shell,
            "shell_ready": not missing_in_shell,
        }

    return service_gaps


def build_render_service_env_commands(render_service_env_gap: dict[str, Any]) -> dict[str, list[str]]:
    commands_by_service: dict[str, list[str]] = {}

    for service_name, details in render_service_env_gap.items():
        commands: list[str] = []
        missing_shell = details.get("missing_in_shell", [])
        missing_blueprint = details.get("missing_in_blueprint", [])

        if missing_blueprint:
            commands.append(
                "Add the missing env vars to render.yaml for {}: {}".format(
                    service_name, ", ".join(missing_blueprint)
                )
            )

        if missing_shell:
            commands.append(
                "Render dashboard -> {} -> Environment: set {}".format(
                    service_name, ", ".join(f"{name}=..." for name in missing_shell)
                )
            )
            commands.append(
                "After saving env vars for {}, trigger a manual deploy and wait for a healthy instance.".format(service_name)
            )
        else:
            commands.append(
                "{} already has every required runtime variable represented in this verification shell.".format(service_name)
            )

        commands.append(
            "Verify {} serves {} after the deploy.".format(
                service_name, details.get("health_check_path") or "/"
            )
        )
        commands_by_service[service_name] = commands

    return commands_by_service


def build_render_service_contract_commands() -> dict[str, list[str]]:
    commands_by_service: dict[str, list[str]] = {}

    for service_name, expected in RENDER_BLUEPRINT_SERVICES.items():
        commands_by_service[service_name] = [
            "Render dashboard -> {} -> Settings: confirm runtime={} and plan={}".format(
                service_name, expected["runtime"], expected["plan"]
            ),
            "Render dashboard -> {} -> Settings: confirm autoDeploy={}".format(
                service_name, "true" if expected["autoDeploy"] else "false"
            ),
            "Render dashboard -> {} -> Build & Deploy: confirm buildCommand='{}'".format(
                service_name, expected["buildCommand"]
            ),
            "Render dashboard -> {} -> Build & Deploy: confirm startCommand='{}'".format(
                service_name, expected["startCommand"]
            ),
            "Render dashboard -> {} -> Health Check: confirm path='{}'".format(
                service_name, expected["healthCheckPath"]
            ),
            "Render dashboard -> {} -> Environment: confirm keys {}".format(
                service_name, ", ".join(sorted(expected["required_env_vars"]))
            ),
        ]

    return commands_by_service


def build_render_domain_attachment_commands(report: dict[str, Any]) -> dict[str, list[str]]:
    webhook_host = report["webhook_base_url"].replace("https://", "").replace("http://", "").rstrip("/")
    app_host = report["app_url"].replace("https://", "").replace("http://", "").rstrip("/")

    return {
        "commission-tracker-app": [
            f"Render dashboard -> commission-tracker-app -> Settings -> Custom Domains: confirm {app_host} is attached to this service.",
            f"curl -I https://{app_host}/",
            f"If the app hostname is attached elsewhere or missing, reattach {app_host} to commission-tracker-app and redeploy.",
        ],
        "commission-tracker-webhook": [
            f"Render dashboard -> commission-tracker-webhook -> Settings -> Custom Domains: confirm {webhook_host} is attached to this service.",
            f"curl -I https://{webhook_host}/health",
            "If Render still returns x-render-routing=no-server, remove any stale domain attachment and reattach the webhook hostname to commission-tracker-webhook before redeploying.",
        ],
    }


def build_render_hostname_diagnostics(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    app_check = report["public_checks"]["app"]
    app_headers = app_check.get("headers", {})
    webhook_health = report["public_checks"]["webhook_health"]
    webhook_headers = webhook_health.get("headers", {})
    webhook_diagnostics = report["public_checks"].get("webhook_diagnostics", {})

    app_attachment_state = "healthy-attached" if app_check.get("ok") else "unverified"
    if app_headers.get("x-render-routing") == "no-server":
        app_attachment_state = "missing-backend-attachment"

    webhook_attachment_state = "unverified"
    if webhook_headers.get("x-render-routing") == "no-server" or webhook_diagnostics.get("no_server"):
        webhook_attachment_state = "missing-backend-attachment"
    elif webhook_health.get("ok"):
        webhook_attachment_state = "healthy-attached"

    hostname_diagnostics = {
        "commission-tracker-app": {
            "host": report["app_url"].replace("https://", "").replace("http://", "").rstrip("/"),
            "expected_service": "commission-tracker-app",
            "probe_path": "/",
            "status": app_check.get("status"),
            "reason": app_check.get("reason"),
            "server": app_headers.get("server"),
            "x_render_origin_server": app_headers.get("x-render-origin-server"),
            "x_render_routing": app_headers.get("x-render-routing"),
            "attachment_state": app_attachment_state,
            "evidence": (
                f"HTTP {app_check.get('status')} with x-render-origin-server={app_headers.get('x-render-origin-server')}"
                if app_headers.get("x-render-origin-server")
                else f"HTTP {app_check.get('status')} with no Render origin header captured"
            ),
        },
        "commission-tracker-webhook": {
            "host": report["webhook_base_url"].replace("https://", "").replace("http://", "").rstrip("/"),
            "expected_service": "commission-tracker-webhook",
            "probe_path": "/health",
            "status": webhook_health.get("status"),
            "reason": webhook_health.get("reason"),
            "server": webhook_headers.get("server"),
            "x_render_origin_server": webhook_headers.get("x-render-origin-server"),
            "x_render_routing": webhook_headers.get("x-render-routing"),
            "attachment_state": webhook_attachment_state,
            "evidence": (
                f"HTTP {webhook_health.get('status')} with x-render-routing={webhook_headers.get('x-render-routing')}"
                if webhook_headers.get("x-render-routing")
                else f"HTTP {webhook_health.get('status')} with no Render routing header captured"
            ),
        },
    }

    return hostname_diagnostics


def build_public_probe_matrix(report: dict[str, Any]) -> list[dict[str, Any]]:
    diagnostics = report["public_checks"]["webhook_diagnostics"]
    rows: list[dict[str, Any]] = []

    for url, result in diagnostics.get("probed_endpoints", {}).items():
        path = "/"
        if url.startswith(report["webhook_base_url"]):
            path = url[len(report["webhook_base_url"]):] or "/"
        headers = result.get("headers", {})
        rows.append(
            {
                "url": url,
                "path": path,
                "status": result.get("status"),
                "reason": result.get("reason"),
                "ok": result.get("ok", False),
                "x_render_routing": headers.get("x-render-routing"),
                "x_render_origin_server": headers.get("x-render-origin-server"),
                "server": headers.get("server"),
                "content_type": headers.get("content-type"),
                "body_preview": result.get("body_preview"),
            }
        )

    rows.sort(key=lambda row: row["path"])
    return rows


def build_public_probe_commands(report: dict[str, Any]) -> list[str]:
    commands = [
        f"curl -i {report['app_url']}",
    ]
    for probe in build_public_probe_matrix(report):
        commands.append(f"curl -i {probe['url']}")
    return commands


def _parse_generated_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_duration(total_seconds: float) -> str:
    seconds = max(int(total_seconds), 0)
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)

    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def build_incident_history(current_report: dict[str, Any], previous_report: dict[str, Any] | None = None) -> dict[str, Any]:
    artifacts_dir = ROOT / "docs" / "smoke-checks"
    history: list[dict[str, Any]] = []

    for path_str in sorted(glob(str(artifacts_dir / "*.json"))):
        path = Path(path_str)
        if path.name == "latest-trial-signup-smoke-check.json":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        generated_at = payload.get("generated_at")
        generated_at_dt = _parse_generated_at(generated_at)
        if generated_at_dt is None:
            continue

        summary = payload.get("summary", {})
        history.append(
            {
                "artifact": path.name,
                "generated_at": generated_at_dt,
                "ready_for_live_e2e": bool(summary.get("ready_for_live_e2e")),
                "public_webhook_ok": bool(summary.get("public_webhook_ok")),
                "public_webhook_no_server": bool(summary.get("public_webhook_no_server")),
            }
        )

    if previous_report:
        previous_dt = _parse_generated_at(previous_report.get("generated_at"))
        previous_summary = previous_report.get("summary", {})
        if previous_dt is not None:
            history.append(
                {
                    "artifact": "previous-latest-artifact",
                    "generated_at": previous_dt,
                    "ready_for_live_e2e": bool(previous_summary.get("ready_for_live_e2e")),
                    "public_webhook_ok": bool(previous_summary.get("public_webhook_ok")),
                    "public_webhook_no_server": bool(previous_summary.get("public_webhook_no_server")),
                }
            )

    current_dt = _parse_generated_at(current_report.get("generated_at")) or datetime.now(timezone.utc)
    current_summary = current_report.get("summary", {})
    history.append(
        {
            "artifact": "current-run",
            "generated_at": current_dt,
            "ready_for_live_e2e": bool(current_summary.get("ready_for_live_e2e")),
            "public_webhook_ok": bool(current_summary.get("public_webhook_ok")),
            "public_webhook_no_server": bool(current_summary.get("public_webhook_no_server")),
        }
    )
    history.sort(key=lambda item: item["generated_at"])

    blocked_runs = [item for item in history if not item["ready_for_live_e2e"]]
    no_server_runs = [item for item in history if item["public_webhook_no_server"]]
    current_state_started_at = None
    current_signature = (
        bool(current_summary.get("ready_for_live_e2e")),
        bool(current_summary.get("public_webhook_ok")),
        bool(current_summary.get("public_webhook_no_server")),
    )
    for item in reversed(history):
        signature = (
            item["ready_for_live_e2e"],
            item["public_webhook_ok"],
            item["public_webhook_no_server"],
        )
        if signature == current_signature:
            current_state_started_at = item["generated_at"]
        else:
            break

    first_blocked_at = blocked_runs[0]["generated_at"] if blocked_runs else None
    first_no_server_at = no_server_runs[0]["generated_at"] if no_server_runs else None

    return {
        "artifact_count": len(history),
        "blocked_artifact_count": len(blocked_runs),
        "first_blocked_at": first_blocked_at.isoformat() if first_blocked_at else None,
        "first_no_server_at": first_no_server_at.isoformat() if first_no_server_at else None,
        "current_state_started_at": current_state_started_at.isoformat() if current_state_started_at else None,
        "blocked_duration": _format_duration((current_dt - first_blocked_at).total_seconds()) if first_blocked_at else None,
        "no_server_duration": _format_duration((current_dt - first_no_server_at).total_seconds()) if first_no_server_at else None,
        "current_state_duration": _format_duration((current_dt - current_state_started_at).total_seconds()) if current_state_started_at else None,
        "latest_status": "ready" if current_summary.get("ready_for_live_e2e") else "blocked",
    }


def build_change_summary(current_report: dict[str, Any], previous_report: dict[str, Any] | None) -> dict[str, Any]:
    if not previous_report:
        return {
            "has_previous_report": False,
            "status_changed": False,
            "summary_changed": False,
            "unchanged_blocked_streak": 0,
            "changes": ["No previous smoke-check artifact was available for comparison."],
        }

    changes: list[str] = []
    current_summary = current_report.get("summary", {})
    previous_summary = previous_report.get("summary", {})

    for label, current_value, previous_value in [
        ("public app status", current_report.get("public_checks", {}).get("app", {}).get("status"), previous_report.get("public_checks", {}).get("app", {}).get("status")),
        ("public webhook health status", current_report.get("public_checks", {}).get("webhook_health", {}).get("status"), previous_report.get("public_checks", {}).get("webhook_health", {}).get("status")),
        ("ready_for_live_e2e", current_summary.get("ready_for_live_e2e"), previous_summary.get("ready_for_live_e2e")),
        ("public_webhook_no_server", current_summary.get("public_webhook_no_server"), previous_summary.get("public_webhook_no_server")),
        ("repo_contract_ok", current_summary.get("render_incident_signature", {}).get("repo_contract_ok"), previous_summary.get("render_incident_signature", {}).get("repo_contract_ok")),
        ("external_routing_issue", current_summary.get("render_incident_signature", {}).get("external_routing_issue"), previous_summary.get("render_incident_signature", {}).get("external_routing_issue")),
    ]:
        if current_value != previous_value:
            changes.append(f"{label} changed from {previous_value} to {current_value}.")

    current_matrix = {row.get("path"): row for row in current_summary.get("public_probe_matrix", [])}
    previous_matrix = {row.get("path"): row for row in previous_summary.get("public_probe_matrix", [])}
    all_paths = sorted(set(current_matrix) | set(previous_matrix))
    for path in all_paths:
        current_row = current_matrix.get(path, {})
        previous_row = previous_matrix.get(path, {})
        for key, label in [("status", "status"), ("x_render_routing", "x-render-routing"), ("x_render_origin_server", "x-render-origin-server")]:
            if current_row.get(key) != previous_row.get(key):
                changes.append(
                    f"Probe {path} {label} changed from {previous_row.get(key)} to {current_row.get(key)}."
                )

    if not changes:
        changes.append("No material change detected versus the previous smoke-check artifact.")

    no_material_change = changes == ["No material change detected versus the previous smoke-check artifact."]
    current_ready = current_summary.get("ready_for_live_e2e")
    previous_streak = previous_summary.get("change_summary", {}).get("unchanged_blocked_streak", 0)
    unchanged_blocked_streak = 0
    if no_material_change and current_ready is False:
        unchanged_blocked_streak = previous_streak + 1

    return {
        "has_previous_report": True,
        "previous_generated_at": previous_report.get("generated_at"),
        "status_changed": any("status" in change for change in changes),
        "summary_changed": not no_material_change,
        "unchanged_blocked_streak": unchanged_blocked_streak,
        "changes": changes,
    }


def build_render_incident_signature(report: dict[str, Any], render_hostname_diagnostics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    app_host = render_hostname_diagnostics["commission-tracker-app"]
    webhook_host = render_hostname_diagnostics["commission-tracker-webhook"]
    blueprint_ok = report["local_checks"]["render_blueprint"]["ok"]
    webhook_contract_ok = report["local_checks"]["webhook_service_contract"]["ok"]
    checkout_ok = report["local_checks"]["checkout_contract"]["ok"]

    repo_contract_ok = blueprint_ok and webhook_contract_ok and checkout_ok
    external_routing_issue = (
        app_host.get("attachment_state") == "healthy-attached"
        and webhook_host.get("attachment_state") == "missing-backend-attachment"
    )

    if external_routing_issue and repo_contract_ok:
        conclusion = (
            "Repo-side checkout, webhook, and Render blueprint contracts are green while the app hostname is healthy-attached "
            "and the webhook hostname is missing-backend-attachment. This points to an external Render service or domain binding problem, not an app-code route regression."
        )
    elif external_routing_issue:
        conclusion = (
            "The webhook hostname looks detached at Render, but repo-side contract checks are not fully green yet, so confirm both deployment wiring and checked-in config before rerunning the live signup path."
        )
    else:
        conclusion = (
            "The current probe pattern does not isolate the outage to a clean app-host healthy versus webhook-host detached split. Review both repo-side checks and Render runtime state together."
        )

    return {
        "repo_contract_ok": repo_contract_ok,
        "app_host_attachment_state": app_host.get("attachment_state"),
        "webhook_host_attachment_state": webhook_host.get("attachment_state"),
        "external_routing_issue": external_routing_issue,
        "conclusion": conclusion,
    }


def build_escalation_recommendation(
    report: dict[str, Any],
    render_incident_signature: dict[str, Any],
    change_summary: dict[str, Any],
    missing_required: list[str],
) -> dict[str, Any]:
    unchanged_blocked_streak = change_summary.get("unchanged_blocked_streak", 0)
    local_webhook_ok = report["local_checks"]["webhook_health_route"]["ok"]

    if render_incident_signature.get("external_routing_issue"):
        owner = "Traction"
        destination = "Render support"
        if unchanged_blocked_streak >= 3:
            severity = "critical"
            urgency = "Escalate immediately. The outage is externally isolated and has repeated without material recovery."
        elif unchanged_blocked_streak >= 1:
            severity = "high"
            urgency = "Escalate now. The outage repeated with no material recovery since the previous smoke check."
        else:
            severity = "high"
            urgency = "Escalate now. The outage is externally isolated to Render routing or domain attachment."
    elif not local_webhook_ok:
        owner = "Forge"
        destination = "local verification shell"
        severity = "medium"
        urgency = "Fix the local webhook verification environment before trusting parity conclusions."
    else:
        owner = "Forge"
        destination = "working session"
        severity = "low"
        urgency = "No escalation is required yet. Continue verification work in the repo."

    if missing_required:
        prerequisite = (
            "Live E2E shell still needs secrets before the final Stripe confirmation: "
            + ", ".join(missing_required)
        )
    else:
        prerequisite = "Live E2E shell prerequisites are satisfied."

    return {
        "severity": severity,
        "owner": owner,
        "destination": destination,
        "unchanged_blocked_streak": unchanged_blocked_streak,
        "urgency": urgency,
        "prerequisite": prerequisite,
        "recommended_message": (
            f"{owner} should escalate to {destination}. {urgency} {prerequisite}"
            if severity != "low"
            else urgency
        ),
    }


def build_render_support_packet(
    report: dict[str, Any],
    render_hostname_diagnostics: dict[str, dict[str, Any]],
    render_incident_signature: dict[str, Any],
) -> dict[str, Any]:
    app_probe = report["public_checks"]["app"]
    webhook_probe = report["public_checks"]["webhook_health"]
    app_host = render_hostname_diagnostics["commission-tracker-app"]
    webhook_host = render_hostname_diagnostics["commission-tracker-webhook"]

    return {
        "incident_type": "render-webhook-routing-outage",
        "generated_at": report["generated_at"],
        "conclusion": render_incident_signature["conclusion"],
        "repo_contract_ok": render_incident_signature["repo_contract_ok"],
        "external_routing_issue": render_incident_signature["external_routing_issue"],
        "host_comparison": {
            "commission-tracker-app": {
                "host": app_host["host"],
                "probe_path": app_host["probe_path"],
                "status": app_probe.get("status"),
                "reason": app_probe.get("reason"),
                "attachment_state": app_host.get("attachment_state"),
                "x_render_origin_server": app_probe.get("headers", {}).get("x-render-origin-server"),
                "x_render_routing": app_probe.get("headers", {}).get("x-render-routing"),
                "cf_ray": app_probe.get("headers", {}).get("cf-ray"),
                "date": app_probe.get("headers", {}).get("date"),
            },
            "commission-tracker-webhook": {
                "host": webhook_host["host"],
                "probe_path": webhook_host["probe_path"],
                "status": webhook_probe.get("status"),
                "reason": webhook_probe.get("reason"),
                "attachment_state": webhook_host.get("attachment_state"),
                "x_render_origin_server": webhook_probe.get("headers", {}).get("x-render-origin-server"),
                "x_render_routing": webhook_probe.get("headers", {}).get("x-render-routing"),
                "cf_ray": webhook_probe.get("headers", {}).get("cf-ray"),
                "date": webhook_probe.get("headers", {}).get("date"),
            },
        },
        "requested_action": (
            "Confirm the webhook hostname is attached to commission-tracker-webhook, redeploy the service, and recheck /health until x-render-routing=no-server disappears."
        ),
    }


def build_render_escalation_message(
    report: dict[str, Any],
    render_support_packet: dict[str, Any],
    render_recovery_playbook: list[str],
) -> str:
    app_host = render_support_packet["host_comparison"]["commission-tracker-app"]
    webhook_host = render_support_packet["host_comparison"]["commission-tracker-webhook"]

    lines = [
        "Render support request for AMS-APP webhook routing outage.",
        f"Generated at {report['generated_at']}.",
        render_support_packet["conclusion"],
        (
            "Healthy app host evidence: "
            f"{app_host['host']}{app_host['probe_path']} -> HTTP {app_host['status']} {app_host['reason']} "
            f"with attachment_state={app_host['attachment_state']} and "
            f"x-render-origin-server={app_host.get('x_render_origin_server') or 'None'}."
        ),
        (
            "Broken webhook host evidence: "
            f"{webhook_host['host']}{webhook_host['probe_path']} -> HTTP {webhook_host['status']} {webhook_host['reason']} "
            f"with attachment_state={webhook_host['attachment_state']} and "
            f"x-render-routing={webhook_host.get('x_render_routing') or 'None'}."
        ),
        "Requested action: " + render_support_packet["requested_action"],
        "Recommended recovery steps:",
    ]
    lines.extend(f"- {step}" for step in render_recovery_playbook)
    return "\n".join(lines)


def build_render_escalation_payload(
    report: dict[str, Any],
    render_support_packet: dict[str, Any],
    render_incident_signature: dict[str, Any],
    change_summary: dict[str, Any],
    escalation_recommendation: dict[str, Any],
    missing_required: list[str],
) -> dict[str, Any]:
    app_host = render_support_packet["host_comparison"]["commission-tracker-app"]
    webhook_host = render_support_packet["host_comparison"]["commission-tracker-webhook"]

    return {
        "ticket_title": "AMS-APP Render webhook routing outage blocks live Stripe signup path",
        "severity": escalation_recommendation.get("severity"),
        "owner": escalation_recommendation.get("owner"),
        "destination": escalation_recommendation.get("destination"),
        "generated_at": report["generated_at"],
        "incident_type": render_support_packet.get("incident_type"),
        "unchanged_blocked_streak": change_summary.get("unchanged_blocked_streak", 0),
        "repo_contract_ok": render_incident_signature.get("repo_contract_ok"),
        "external_routing_issue": render_incident_signature.get("external_routing_issue"),
        "app_host_evidence": (
            f"{app_host['host']}{app_host['probe_path']} -> HTTP {app_host['status']} {app_host['reason']} "
            f"attachment_state={app_host['attachment_state']} x-render-origin-server={app_host.get('x_render_origin_server') or 'None'}"
        ),
        "webhook_host_evidence": (
            f"{webhook_host['host']}{webhook_host['probe_path']} -> HTTP {webhook_host['status']} {webhook_host['reason']} "
            f"attachment_state={webhook_host['attachment_state']} x-render-routing={webhook_host.get('x_render_routing') or 'None'}"
        ),
        "requested_action": render_support_packet.get("requested_action"),
        "missing_live_e2e_secrets": missing_required,
        "recommended_message": escalation_recommendation.get("recommended_message"),
    }


def build_executive_summary_lines(
    report: dict[str, Any],
    render_incident_signature: dict[str, Any],
    escalation_recommendation: dict[str, Any],
    change_summary: dict[str, Any],
    missing_required: list[str],
    ready_for_live_e2e: bool,
) -> list[str]:
    app_check = report["public_checks"]["app"]
    webhook_check = report["public_checks"]["webhook_health"]
    app_headers = app_check.get("headers", {})
    webhook_headers = webhook_check.get("headers", {})

    lines = [
        (
            "AMS-APP trial signup stack is {}. "
            "App host returned HTTP {} {} while webhook health returned HTTP {} {}."
        ).format(
            "ready for live E2E" if ready_for_live_e2e else "still blocked",
            app_check.get("status"),
            app_check.get("reason"),
            webhook_check.get("status"),
            webhook_check.get("reason"),
        ),
        (
            "Render evidence: app attachment_state={} with x-render-origin-server={}, webhook attachment_state={} with x-render-routing={}."
        ).format(
            render_incident_signature.get("app_host_attachment_state"),
            app_headers.get("x-render-origin-server") or "None",
            render_incident_signature.get("webhook_host_attachment_state"),
            webhook_headers.get("x-render-routing") or "None",
        ),
        render_incident_signature.get("conclusion"),
    ]

    if missing_required:
        lines.append(
            "Live verification shell still needs secrets before the final Stripe run: "
            + ", ".join(missing_required)
        )
    else:
        lines.append("Live verification shell has the required secrets for the final Stripe run.")

    lines.append(
        "Escalation: severity={} owner={} destination={} unchanged_blocked_streak={}.".format(
            escalation_recommendation.get("severity"),
            escalation_recommendation.get("owner"),
            escalation_recommendation.get("destination"),
            change_summary.get("unchanged_blocked_streak", 0),
        )
    )
    lines.append(escalation_recommendation.get("recommended_message"))
    return lines


def build_recovery_exit_criteria(
    report: dict[str, Any],
    render_incident_signature: dict[str, Any],
    missing_required: list[str],
) -> list[str]:
    webhook_host = report["webhook_base_url"].replace("https://", "").replace("http://", "").rstrip("/")
    app_host = report["app_url"].replace("https://", "").replace("http://", "").rstrip("/")

    criteria = [
        f"{app_host}/ returns HTTP 200 from the public app host.",
        f"{webhook_host}/health returns HTTP 200 without x-render-routing=no-server.",
        "The local webhook /health import check returns HTTP 200 from webhook_server.py.",
        "The checked-in checkout, webhook service, and Render blueprint contract checks all remain green.",
    ]

    if render_incident_signature.get("external_routing_issue"):
        criteria.append(
            "The webhook hostname is attached to commission-tracker-webhook in Render and shows a healthy backend instance."
        )

    if missing_required:
        criteria.append(
            "The verification shell has the live Stripe, Resend, and Supabase secrets loaded: "
            + ", ".join(missing_required)
        )
    else:
        criteria.append("The verification shell already has the live Stripe, Resend, and Supabase secrets loaded.")

    criteria.extend(
        [
            "A fresh smoke-check artifact reports ready_for_live_e2e=true.",
            "One real Stripe test-mode signup completes and the follow-up evidence captures the session ID, webhook timestamp, and onboarding email result.",
        ]
    )
    return criteria


def build_owner_action_plan(
    report: dict[str, Any],
    render_support_packet: dict[str, Any],
    render_service_env_gap: dict[str, Any],
    missing_required: list[str],
) -> dict[str, list[str]]:
    webhook_host = render_support_packet["host_comparison"]["commission-tracker-webhook"]["host"]
    app_host = render_support_packet["host_comparison"]["commission-tracker-app"]["host"]
    webhook_probe = render_support_packet["host_comparison"]["commission-tracker-webhook"]
    app_probe = render_support_packet["host_comparison"]["commission-tracker-app"]
    webhook_missing = render_service_env_gap.get("commission-tracker-webhook", {}).get("missing_in_shell", [])
    app_missing = render_service_env_gap.get("commission-tracker-app", {}).get("missing_in_shell", [])

    plans = {
        "traction": [
            "Forward the Render escalation message and support packet without rewriting the evidence.",
            "Attach the latest smoke-check JSON, smoke-check Markdown, trial-signup report, and render.yaml from the artifact inventory.",
            f"Tell Render support the app host {app_host}{app_probe['probe_path']} is healthy while the webhook host {webhook_host}{webhook_probe['probe_path']} is still detached or unrouted.",
            "Ask Render to confirm the webhook hostname is attached to commission-tracker-webhook and redeploy the service.",
        ],
        "render_support": [
            f"Confirm {webhook_host} is attached to commission-tracker-webhook, not a stale or missing backend.",
            "Redeploy commission-tracker-webhook and verify the runtime comes up healthy behind the public hostname.",
            f"Recheck https://{webhook_host}/health until x-render-routing=no-server disappears and the endpoint returns 200.",
        ],
        "verification_shell": [
            "Re-run python3 scripts/trial_signup_smoke_check.py after Render reports the webhook deploy is healthy.",
            "Refresh the JSON and Markdown smoke-check artifacts before attempting any live Stripe path.",
            "Use the artifact inventory to attach the updated evidence files to the handoff after each rerun.",
        ],
    }

    if app_missing:
        plans["traction"].append(
            "Load or coordinate the missing app-shell runtime values before the final live test: " + ", ".join(app_missing)
        )

    if webhook_missing:
        plans["traction"].append(
            "Load or coordinate the missing webhook-shell runtime values before the final live test: " + ", ".join(webhook_missing)
        )

    if missing_required:
        plans["verification_shell"].append(
            "Export the missing live E2E secrets before the final test: " + ", ".join(missing_required)
        )

    plans["verification_shell"].append(
        "Only run a real Stripe test-mode signup after ready_for_live_e2e flips to true."
    )

    return plans


def build_artifact_refresh_commands() -> dict[str, str]:
    return {
        "json": "python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json",
        "markdown": "python3 scripts/trial_signup_smoke_check.py --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md",
        "both": "python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md",
    }


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)) if path.is_absolute() else str(path)
    except ValueError:
        return str(path)


def _artifact_metadata(path: Path) -> dict[str, Any]:
    exists = path.exists()
    return {
        "path": _display_path(path),
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else 0,
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat() if exists else None,
    }


def _generated_at_slug(generated_at: str | None) -> str:
    if not generated_at:
        return "unknown-generated-at"
    return re.sub(r"[^0-9A-Za-z]+", "-", generated_at).strip("-")


def build_owner_ready_archive_file_paths(report: dict[str, Any], archive_dir: str | Path) -> dict[str, Path]:
    base_path = Path(archive_dir)
    slug = _generated_at_slug(report.get("generated_at"))
    return {
        owner: base_path / f"{slug}-{owner}.txt"
        for owner in report.get("summary", {}).get("owner_ready_messages", {})
    }


def build_escalation_packet_archive_file_paths(report: dict[str, Any], archive_dir: str | Path) -> dict[str, Path]:
    base_path = Path(archive_dir)
    slug = _generated_at_slug(report.get("generated_at"))
    return {
        "render-support-message.txt": base_path / f"{slug}-render-support-message.txt",
        "render-support-payload.json": base_path / f"{slug}-render-support-payload.json",
        "evidence-manifest.json": base_path / f"{slug}-evidence-manifest.json",
        "README.txt": base_path / f"{slug}-README.txt",
    }


def build_escalation_packet_readme(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    inventory = summary.get("artifact_inventory", {})
    payload = summary.get("render_escalation_payload", {})
    packet_files = inventory.get("render_support_packet_files", [])
    recommended = inventory.get("recommended_attachments", [])
    missing_secrets = payload.get("missing_live_e2e_secrets", [])

    lines = [
        "AMS-APP Render Escalation Packet",
        f"Generated at: {report.get('generated_at')}",
        f"Severity: {payload.get('severity', 'unknown')}",
        f"Owner: {payload.get('owner', 'unknown')}",
        f"Destination: {payload.get('destination', 'unknown')}",
        "",
        "What this packet is:",
        "A send-ready evidence bundle for the current Render webhook routing outage blocking live Stripe trial signup validation.",
        "",
        "Primary requested action:",
        str(payload.get("requested_action", "Not provided.")),
        "",
        "Recommended packet files:",
    ]

    for item in packet_files:
        lines.append(f"- {item}")

    lines.extend(["", "Broader recommended attachments:"])
    for item in recommended:
        lines.append(f"- {item}")

    if missing_secrets:
        lines.extend([
            "",
            "Live verification shell still needs these secrets before the final Stripe test:",
        ])
        for item in missing_secrets:
            lines.append(f"- {item}")

    lines.extend([
        "",
        "If forwarding to Render support:",
        "1. Send render-support-message.txt as the support message body.",
        "2. Attach render-support-payload.json and evidence-manifest.json.",
        "3. Include the latest smoke-check JSON/Markdown artifacts and render.yaml from the packet file list above.",
    ])

    return "\n".join(lines).rstrip() + "\n"


def build_artifact_inventory() -> dict[str, Any]:
    smoke_dir = ROOT / "docs" / "smoke-checks"
    artifact_paths = {
        "latest_json": smoke_dir / "latest-trial-signup-smoke-check.json",
        "latest_markdown": smoke_dir / "latest-trial-signup-smoke-check.md",
        "trial_signup_report": ROOT / "docs" / "TRIAL_SIGNUP_E2E_REPORT_2026-04-01.md",
        "render_blueprint": ROOT / "render.yaml",
        "smoke_check_script": ROOT / "scripts" / "trial_signup_smoke_check.py",
        "smoke_check_tests": ROOT / "test_trial_signup_smoke_check.py",
        "owner_ready_traction": DEFAULT_OWNER_READY_DIR / "traction.txt",
        "owner_ready_render_support": DEFAULT_OWNER_READY_DIR / "render_support.txt",
        "owner_ready_verification_shell": DEFAULT_OWNER_READY_DIR / "verification_shell.txt",
        "escalation_packet_message": DEFAULT_ESCALATION_PACKET_DIR / "render-support-message.txt",
        "escalation_packet_payload": DEFAULT_ESCALATION_PACKET_DIR / "render-support-payload.json",
        "escalation_packet_manifest": DEFAULT_ESCALATION_PACKET_DIR / "evidence-manifest.json",
        "escalation_packet_readme": DEFAULT_ESCALATION_PACKET_DIR / "README.txt",
    }

    inventory: dict[str, Any] = {}
    for label, path in artifact_paths.items():
        inventory[label] = _artifact_metadata(path)

    archive_files = sorted(DEFAULT_OWNER_READY_ARCHIVE_DIR.glob("*.txt")) if DEFAULT_OWNER_READY_ARCHIVE_DIR.exists() else []
    inventory["owner_ready_archive"] = {
        "path": _display_path(DEFAULT_OWNER_READY_ARCHIVE_DIR),
        "exists": DEFAULT_OWNER_READY_ARCHIVE_DIR.exists(),
        "file_count": len(archive_files),
        "latest_files": [
            _display_path(path)
            for path in sorted(archive_files, key=lambda p: p.stat().st_mtime, reverse=True)[:6]
        ],
    }

    inventory["escalation_packet_dir"] = {
        "path": _display_path(DEFAULT_ESCALATION_PACKET_DIR),
        "exists": DEFAULT_ESCALATION_PACKET_DIR.exists(),
        "files": [
            _display_path(path)
            for path in sorted(DEFAULT_ESCALATION_PACKET_DIR.glob("*"))
            if path.is_file()
        ],
    }

    escalation_archive_files = sorted(DEFAULT_ESCALATION_PACKET_ARCHIVE_DIR.glob("*")) if DEFAULT_ESCALATION_PACKET_ARCHIVE_DIR.exists() else []
    inventory["escalation_packet_archive"] = {
        "path": _display_path(DEFAULT_ESCALATION_PACKET_ARCHIVE_DIR),
        "exists": DEFAULT_ESCALATION_PACKET_ARCHIVE_DIR.exists(),
        "file_count": len(escalation_archive_files),
        "latest_files": [
            _display_path(path)
            for path in sorted(escalation_archive_files, key=lambda p: p.stat().st_mtime, reverse=True)[:6]
        ],
    }

    inventory["recommended_attachments"] = [
        "docs/smoke-checks/latest-trial-signup-smoke-check.json",
        "docs/smoke-checks/latest-trial-signup-smoke-check.md",
        "docs/TRIAL_SIGNUP_E2E_REPORT_2026-04-01.md",
        "render.yaml",
        "docs/smoke-checks/owner-ready/traction.txt",
        "docs/smoke-checks/owner-ready/render_support.txt",
        "docs/smoke-checks/escalation-packet/render-support-message.txt",
        "docs/smoke-checks/escalation-packet/render-support-payload.json",
        "docs/smoke-checks/escalation-packet/evidence-manifest.json",
        "docs/smoke-checks/escalation-packet/README.txt",
    ]
    inventory["render_support_packet_files"] = [
        "docs/smoke-checks/latest-trial-signup-smoke-check.json",
        "docs/smoke-checks/latest-trial-signup-smoke-check.md",
        "render.yaml",
        "docs/smoke-checks/owner-ready/render_support.txt",
        "docs/smoke-checks/escalation-packet/render-support-message.txt",
        "docs/smoke-checks/escalation-packet/render-support-payload.json",
        "docs/smoke-checks/escalation-packet/evidence-manifest.json",
        "docs/smoke-checks/escalation-packet/README.txt",
    ]
    inventory["traction_handoff_files"] = [
        "docs/TRIAL_SIGNUP_E2E_REPORT_2026-04-01.md",
        "docs/smoke-checks/latest-trial-signup-smoke-check.md",
        "docs/smoke-checks/latest-trial-signup-smoke-check.json",
        "docs/smoke-checks/owner-ready/traction.txt",
        "docs/smoke-checks/escalation-packet/render-support-message.txt",
        "docs/smoke-checks/escalation-packet/evidence-manifest.json",
    ]
    return inventory


def build_owner_ready_messages(
    report: dict[str, Any],
    render_support_packet: dict[str, Any],
    owner_action_plan: dict[str, list[str]],
    missing_required: list[str],
) -> dict[str, str]:
    webhook_host = render_support_packet["host_comparison"]["commission-tracker-webhook"]["host"]
    app_host = render_support_packet["host_comparison"]["commission-tracker-app"]["host"]
    webhook_probe = render_support_packet["host_comparison"]["commission-tracker-webhook"]
    app_probe = render_support_packet["host_comparison"]["commission-tracker-app"]
    generated_at = report["generated_at"]

    traction_message = (
        f"Traction handoff at {generated_at}: {app_host}{app_probe['probe_path']} is healthy "
        f"at HTTP {app_probe['status']} while {webhook_host}{webhook_probe['probe_path']} is still "
        f"HTTP {webhook_probe['status']} with x-render-routing={webhook_probe.get('x_render_routing') or 'None'}. "
        "Forward the attached Render escalation packet, ask Render to confirm the webhook hostname is "
        "attached to commission-tracker-webhook, redeploy it, and then have the verification shell rerun the smoke check."
    )

    render_support_message = (
        f"Render support request generated {generated_at}: {app_host}{app_probe['probe_path']} is healthy "
        f"at HTTP {app_probe['status']} with attachment_state={app_probe['attachment_state']}, but "
        f"{webhook_host}{webhook_probe['probe_path']} is HTTP {webhook_probe['status']} with "
        f"attachment_state={webhook_probe['attachment_state']} and x-render-routing={webhook_probe.get('x_render_routing') or 'None'}. "
        "Please confirm commission-tracker-webhook owns the webhook hostname, redeploy the service, and "
        "retest /health until the route returns 200 without x-render-routing=no-server."
    )

    verification_shell_message = (
        "Verification-shell handoff: rerun python3 scripts/trial_signup_smoke_check.py after Render reports the webhook service healthy, "
        "refresh the JSON and Markdown artifacts, and only run the real Stripe test-mode signup after ready_for_live_e2e turns true."
    )
    if missing_required:
        verification_shell_message += " Missing live E2E secrets: " + ", ".join(missing_required) + "."

    messages = {
        "traction": traction_message,
        "render_support": render_support_message,
        "verification_shell": verification_shell_message,
    }

    for owner, actions in owner_action_plan.items():
        if owner in messages and actions:
            messages[owner] += " Next actions: " + " ".join(actions[:2])

    return messages


def build_render_recovery_playbook(
    report: dict[str, Any],
    render_incident_signature: dict[str, Any],
    render_service_env_gap: dict[str, Any],
    missing_required: list[str],
) -> list[str]:
    playbook: list[str] = []
    webhook_host = report["webhook_base_url"].replace("https://", "").replace("http://", "").rstrip("/")
    app_host = report["app_url"].replace("https://", "").replace("http://", "").rstrip("/")

    if render_incident_signature.get("external_routing_issue"):
        playbook.extend(
            [
                "1. Render dashboard: open commission-tracker-webhook first because the smoke check isolated the incident to the webhook hostname, not the main app.",
                f"2. Custom Domains: confirm {webhook_host} is attached to commission-tracker-webhook while {app_host} remains attached to commission-tracker-app.",
                "3. If the webhook hostname is missing or attached to the wrong service, remove the stale attachment, reattach it to commission-tracker-webhook, and save.",
                "4. Build & Deploy: confirm the deployed start command is gunicorn webhook_server:app --bind 0.0.0.0:${PORT} and trigger a manual deploy if Render has stale runtime state.",
                "5. Wait for Render to report a healthy instance, then probe /health again before attempting any Stripe flow.",
            ]
        )
    else:
        playbook.extend(
            [
                "1. Review both Render services together because the current probe pattern does not isolate the outage to the webhook hostname alone.",
                "2. Confirm the checked-in build, start, and health-check contract for both services matches the Render dashboard before redeploying.",
                "3. Probe both public hostnames after deploy and only proceed once the app and webhook checks are both green.",
            ]
        )

    webhook_env_gap = render_service_env_gap.get("commission-tracker-webhook", {})
    missing_webhook_shell = webhook_env_gap.get("missing_in_shell", [])
    if missing_webhook_shell:
        playbook.append(
            "6. Load the missing webhook runtime values in Render or the verification shell: "
            + ", ".join(missing_webhook_shell)
        )

    if missing_required:
        playbook.append(
            "7. Before the real signup test, load the remaining live E2E secrets into the verification shell: "
            + ", ".join(missing_required)
        )

    playbook.append(
        "8. Re-run python3 scripts/trial_signup_smoke_check.py and only run a real Stripe test-mode signup after ready_for_live_e2e flips to true."
    )
    return playbook


def build_blockers_and_actions(report: dict[str, Any], missing_required: list[str]) -> tuple[list[str], list[str], list[str], list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    actions: list[str] = []
    render_service_env_gap = build_render_service_env_gap(report)

    if not report["public_checks"]["app"]["ok"]:
        blockers.append(
            f"Public app URL {report['app_url']} is not healthy: "
            f"{report['public_checks']['app']['status']} {report['public_checks']['app']['reason']}"
        )
        actions.append("Restore the public Streamlit app before attempting a live signup test.")

    if not report["public_checks"]["webhook_health"]["ok"]:
        diagnostics = report["public_checks"]["webhook_diagnostics"]
        blockers.append(
            f"Public webhook health URL {report['webhook_health_url']} is not healthy: "
            f"{report['public_checks']['webhook_health']['status']} {report['public_checks']['webhook_health']['reason']}"
        )
        blockers.append(diagnostics["likely_cause"])
        if diagnostics["no_server"]:
            actions.append(
                "Render is signaling no-server for the webhook hostname; reattach or redeploy the webhook backend behind the expected domain."
            )
        elif diagnostics["all_404"]:
            actions.append(
                "Verify the webhook service routing and startup command so /health is served by webhook_server:app."
            )
        else:
            actions.append("Inspect Render deploy/runtime logs for the webhook service and restore /health.")


    local_webhook_dependency_commands = build_local_webhook_dependency_commands(report)
    if not report["local_checks"]["webhook_health_route"]["ok"]:
        blockers.append("Local webhook /health verification failed in this workspace.")
        missing_modules = report["local_checks"]["webhook_health_route"].get("dependency_check", {}).get("missing_modules", [])
        if missing_modules:
            actions.append(
                "Install the missing local webhook verification dependencies and re-run the /health import check: "
                + ", ".join(missing_modules)
            )
        else:
            actions.append("Fix the local webhook import/runtime issue before trusting deployment parity.")

    if not report["local_checks"]["checkout_contract"]["ok"]:
        blockers.append("Local checkout contract verification failed in this workspace.")
        actions.append("Fix the checkout session contract so trial signup still uses the expected Stripe subscription settings.")

    if not report["local_checks"]["render_blueprint"]["ok"]:
        blockers.append("Checked-in Render blueprint verification failed in this workspace.")
        actions.append("Fix render.yaml so both app and webhook services declare the expected commands, health checks, and env vars.")

    if not report["local_checks"]["webhook_service_contract"]["ok"]:
        blockers.append("Checked-in webhook service contract verification failed in this workspace.")
        actions.append("Fix webhook_server.py routes and requirements.txt so the deployed Render webhook has the expected entrypoints and runtime dependencies.")

    if missing_required:
        blockers.append(
            "Required live E2E secrets are missing from this shell: " + ", ".join(missing_required)
        )
        actions.append(
            "Load the missing Stripe, Resend, and Supabase service secrets into the verification shell before running a real checkout."
        )

    if not blockers:
        actions.append("Run one real Stripe test-mode signup and capture the Stripe session and webhook timestamps.")

    render_restore_checklist = build_render_restore_checklist(report, missing_required)
    render_restore_validation_commands = build_render_restore_validation_commands(report, missing_required)
    return (
        blockers,
        actions,
        render_restore_checklist,
        render_restore_validation_commands,
        local_webhook_dependency_commands,
        render_service_env_gap,
    )


def generate_report(previous_report: dict[str, Any] | None = None) -> dict[str, Any]:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "app_url": APP_URL,
        "webhook_health_url": WEBHOOK_URL,
        "webhook_base_url": WEBHOOK_BASE_URL,
        "public_checks": {
            "app": fetch_url(APP_URL),
            "webhook_health": fetch_url(WEBHOOK_URL),
            "webhook_diagnostics": diagnose_public_webhook(WEBHOOK_BASE_URL),
        },
        "env": {
            "required_for_live_e2e": {name: inspect_env_var(name) for name in LIVE_E2E_ENV_VARS},
            "optional_context": {name: inspect_env_var(name) for name in OPTIONAL_ENV_VARS},
        },
        "local_checks": {
            "webhook_health_route": check_local_webhook_route(),
            "checkout_contract": check_checkout_contract(),
            "render_blueprint": check_render_blueprint(),
            "webhook_service_contract": check_webhook_service_contract(),
        },
    }

    missing_required = [
        name for name, details in report["env"]["required_for_live_e2e"].items() if not details["present"]
    ]
    blockers, next_actions, render_restore_checklist, render_restore_validation_commands, local_webhook_dependency_commands, render_service_env_gap = build_blockers_and_actions(report, missing_required)
    render_service_env_commands = build_render_service_env_commands(render_service_env_gap)
    render_service_contract_commands = build_render_service_contract_commands()
    render_domain_attachment_commands = build_render_domain_attachment_commands(report)
    render_hostname_diagnostics = build_render_hostname_diagnostics(report)
    public_probe_matrix = build_public_probe_matrix(report)
    public_probe_commands = build_public_probe_commands(report)
    render_incident_signature = build_render_incident_signature(report, render_hostname_diagnostics)
    render_support_packet = build_render_support_packet(
        report,
        render_hostname_diagnostics,
        render_incident_signature,
    )
    artifact_refresh_commands = build_artifact_refresh_commands()
    artifact_inventory = build_artifact_inventory()
    owner_action_plan = build_owner_action_plan(
        report,
        render_support_packet,
        render_service_env_gap,
        missing_required,
    )
    owner_ready_messages = build_owner_ready_messages(
        report,
        render_support_packet,
        owner_action_plan,
        missing_required,
    )
    render_recovery_playbook = build_render_recovery_playbook(
        report,
        render_incident_signature,
        render_service_env_gap,
        missing_required,
    )
    recovery_exit_criteria = build_recovery_exit_criteria(
        report,
        render_incident_signature,
        missing_required,
    )
    ready_for_live_e2e = (
        report["public_checks"]["app"]["ok"]
        and report["public_checks"]["webhook_health"]["ok"]
        and report["local_checks"]["webhook_health_route"]["ok"]
        and report["local_checks"]["checkout_contract"]["ok"]
        and report["local_checks"]["render_blueprint"]["ok"]
        and report["local_checks"]["webhook_service_contract"]["ok"]
        and not missing_required
    )
    current_summary = {
        "public_app_ok": report["public_checks"]["app"]["ok"],
        "public_webhook_ok": report["public_checks"]["webhook_health"]["ok"],
        "public_webhook_any_endpoint_ok": report["public_checks"]["webhook_diagnostics"]["any_ok"],
        "public_webhook_all_probed_endpoints_404": report["public_checks"]["webhook_diagnostics"]["all_404"],
        "public_webhook_render_routing_modes": report["public_checks"]["webhook_diagnostics"]["render_routing_modes"],
        "public_webhook_no_server": report["public_checks"]["webhook_diagnostics"]["no_server"],
        "public_webhook_likely_cause": report["public_checks"]["webhook_diagnostics"]["likely_cause"],
        "local_webhook_ok": report["local_checks"]["webhook_health_route"]["ok"],
        "checkout_contract_ok": report["local_checks"]["checkout_contract"]["ok"],
        "render_blueprint_ok": report["local_checks"]["render_blueprint"]["ok"],
        "webhook_service_contract_ok": report["local_checks"]["webhook_service_contract"]["ok"],
        "missing_required_env_vars": missing_required,
        "blocking_reasons": blockers,
        "next_actions": next_actions,
        "render_restore_checklist": render_restore_checklist,
        "render_restore_validation_commands": render_restore_validation_commands,
        "local_webhook_dependency_commands": local_webhook_dependency_commands,
        "render_service_env_gap": render_service_env_gap,
        "render_service_env_commands": render_service_env_commands,
        "render_service_contract_commands": render_service_contract_commands,
        "render_domain_attachment_commands": render_domain_attachment_commands,
        "render_hostname_diagnostics": render_hostname_diagnostics,
        "public_probe_matrix": public_probe_matrix,
        "public_probe_commands": public_probe_commands,
        "render_incident_signature": render_incident_signature,
        "render_support_packet": render_support_packet,
        "artifact_refresh_commands": artifact_refresh_commands,
        "artifact_inventory": artifact_inventory,
        "owner_action_plan": owner_action_plan,
        "owner_ready_messages": owner_ready_messages,
        "render_recovery_playbook": render_recovery_playbook,
        "recovery_exit_criteria": recovery_exit_criteria,
        "ready_for_live_e2e": ready_for_live_e2e,
    }
    report["summary"] = current_summary
    change_summary = build_change_summary(report, previous_report)
    incident_history = build_incident_history(report, previous_report=previous_report)
    escalation_recommendation = build_escalation_recommendation(
        report,
        render_incident_signature,
        change_summary,
        missing_required,
    )
    executive_summary_lines = build_executive_summary_lines(
        report,
        render_incident_signature,
        escalation_recommendation,
        change_summary,
        missing_required,
        ready_for_live_e2e,
    )
    render_escalation_message = build_render_escalation_message(
        report,
        render_support_packet,
        render_recovery_playbook,
    )
    render_escalation_payload = build_render_escalation_payload(
        report,
        render_support_packet,
        render_incident_signature,
        change_summary,
        escalation_recommendation,
        missing_required,
    )

    report["summary"].update(
        {
            "render_escalation_message": render_escalation_message,
            "render_escalation_payload": render_escalation_payload,
            "change_summary": change_summary,
            "incident_history": incident_history,
            "escalation_recommendation": escalation_recommendation,
            "executive_summary_lines": executive_summary_lines,
        }
    )
    return report


def summarize_render_blueprint_services(services: dict[str, Any]) -> str:
    if not services:
        return "No services discovered"

    summaries = []
    for service, details in services.items():
        summaries.append(
            "{}: runtime={}, plan={}, autoDeploy={}, buildCommand={}, startCommand={}, healthCheckPath={}".format(
                service,
                "OK" if details.get("runtime_ok") else "FAIL",
                "OK" if details.get("plan_ok") else "FAIL",
                "OK" if details.get("auto_deploy_ok") else "FAIL",
                "OK" if details.get("build_command_ok") else "FAIL",
                "OK" if details.get("start_command_ok") else "FAIL",
                "OK" if details.get("health_check_path_ok") else "FAIL",
            )
        )
    return "; ".join(summaries)


def render_markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    diagnostics = report["public_checks"]["webhook_diagnostics"]
    root_probe = diagnostics["probed_endpoints"].get(f"{report['webhook_base_url'].rstrip('/')}/", {})
    health_probe = diagnostics["probed_endpoints"].get(report["webhook_health_url"], report["public_checks"]["webhook_health"])
    missing = summary["missing_required_env_vars"] or ["None"]

    lines = [
        "# Trial Signup Smoke Check Snapshot",
        "",
        f"Generated at: {report['generated_at']}",
        f"Ready for live e2e: {'YES' if summary['ready_for_live_e2e'] else 'NO'}",
        "",
        "## Executive summary",
    ]
    lines.extend(f"- {line}" for line in summary["executive_summary_lines"] or ["None"])
    lines.extend([
        "",
        "## Public checks",
        f"- App URL: {report['app_url']} -> {report['public_checks']['app']['status']} {report['public_checks']['app']['reason']}",
        f"- Webhook health: {report['webhook_health_url']} -> {report['public_checks']['webhook_health']['status']} {report['public_checks']['webhook_health']['reason']}",
        f"- Webhook root: {report['webhook_base_url'].rstrip('/') + '/'} -> {root_probe.get('status')} {root_probe.get('reason')}",
        f"- Webhook Render routing modes: {', '.join(summary['public_webhook_render_routing_modes']) if summary['public_webhook_render_routing_modes'] else 'None captured'}",
        f"- Webhook no-server detected: {'YES' if summary['public_webhook_no_server'] else 'NO'}",
        f"- Any webhook endpoint OK: {'YES' if summary['public_webhook_any_endpoint_ok'] else 'NO'}",
        f"- All probed webhook endpoints 404: {'YES' if summary['public_webhook_all_probed_endpoints_404'] else 'NO'}",
        f"- Likely webhook cause: {summary['public_webhook_likely_cause']}",
        "",
        "## Local checks",
        f"- Local webhook route OK: {'YES' if summary['local_webhook_ok'] else 'NO'}",
        f"- Local webhook payload: {report['local_checks']['webhook_health_route']['payload']}",
        f"- Checkout contract OK: {'YES' if summary['checkout_contract_ok'] else 'NO'}",
        f"- Checkout contract payload: {report['local_checks']['checkout_contract']['payload']}",
        f"- Render blueprint OK: {'YES' if summary['render_blueprint_ok'] else 'NO'}",
        f"- Render blueprint payload: {report['local_checks']['render_blueprint']['payload']}",
        f"- Render blueprint service contract summary: {summarize_render_blueprint_services(report['local_checks']['render_blueprint'].get('services', {}))}",
        f"- Webhook service contract OK: {'YES' if summary['webhook_service_contract_ok'] else 'NO'}",
        f"- Webhook service contract payload: {report['local_checks']['webhook_service_contract']['payload']}",
        "",
        "## Missing required env vars",
    ])
    lines.extend(f"- {name}" for name in missing)
    lines.extend(
        [
            "",
            "## Blocking reasons",
        ]
    )
    lines.extend(f"- {reason}" for reason in summary["blocking_reasons"] or ["None"])
    lines.extend(
        [
            "",
            "## Recommended next actions",
        ]
    )
    lines.extend(f"- {action}" for action in summary["next_actions"] or ["None"])
    lines.extend(
        [
            "",
            "## Render restore checklist",
        ]
    )
    lines.extend(f"- {step}" for step in summary["render_restore_checklist"] or ["None"])
    lines.extend(
        [
            "",
            "## Render restore validation commands",
        ]
    )
    lines.extend(f"- {command}" for command in summary["render_restore_validation_commands"] or ["None"])
    lines.extend(
        [
            "",
            "## Local webhook dependency commands",
        ]
    )
    lines.extend(f"- {command}" for command in summary["local_webhook_dependency_commands"] or ["None"])
    lines.extend(
        [
            "",
            "## Render service env gap",
        ]
    )
    for service_name, details in summary["render_service_env_gap"].items():
        lines.append(f"- {service_name}: shell_ready={'YES' if details['shell_ready'] else 'NO'}; missing_in_shell={', '.join(details['missing_in_shell']) if details['missing_in_shell'] else 'None'}; missing_in_blueprint={', '.join(details['missing_in_blueprint']) if details['missing_in_blueprint'] else 'None'}")

    lines.extend(["", "## Render service env commands"])
    for service_name, commands in summary["render_service_env_commands"].items():
        lines.append(f"- {service_name}:")
        for command in commands:
            lines.append(f"  - {command}")

    lines.extend(["", "## Render service contract commands"])
    for service_name, commands in summary["render_service_contract_commands"].items():
        lines.append(f"- {service_name}:")
        for command in commands:
            lines.append(f"  - {command}")

    lines.extend(["", "## Render domain attachment commands"])
    for service_name, commands in summary["render_domain_attachment_commands"].items():
        lines.append(f"- {service_name}:")
        for command in commands:
            lines.append(f"  - {command}")

    lines.extend(["", "## Render hostname diagnostics"])
    for service_name, details in summary["render_hostname_diagnostics"].items():
        lines.append(
            "- {}: host={}; expected_service={}; probe_path={}; attachment_state={}; status={} {}; x-render-origin-server={}; x-render-routing={}; evidence={}".format(
                service_name,
                details.get("host"),
                details.get("expected_service"),
                details.get("probe_path"),
                details.get("attachment_state"),
                details.get("status"),
                details.get("reason"),
                details.get("x_render_origin_server") or "None",
                details.get("x_render_routing") or "None",
                details.get("evidence"),
            )
        )

    lines.extend(["", "## Public webhook probe matrix"])
    for probe in summary["public_probe_matrix"]:
        lines.append(
            "- path={}; status={} {}; ok={}; x-render-routing={}; x-render-origin-server={}; server={}; content-type={}; body-preview={}".format(
                probe.get("path"),
                probe.get("status"),
                probe.get("reason"),
                "YES" if probe.get("ok") else "NO",
                probe.get("x_render_routing") or "None",
                probe.get("x_render_origin_server") or "None",
                probe.get("server") or "None",
                probe.get("content_type") or "None",
                probe.get("body_preview") or "",
            )
        )

    lines.extend(["", "## Public probe commands"])
    lines.extend(f"- {command}" for command in summary["public_probe_commands"] or ["None"])

    change_summary = summary["change_summary"]
    lines.extend(["", "## Change summary versus previous smoke check"])
    if change_summary.get("has_previous_report"):
        lines.append(f"- Previous artifact generated at: {change_summary.get('previous_generated_at')}")
    lines.append(f"- Material change detected: {'YES' if change_summary.get('summary_changed') else 'NO'}")
    lines.append(f"- Unchanged blocked streak: {change_summary.get('unchanged_blocked_streak', 0)}")
    lines.extend(f"- {change}" for change in change_summary.get("changes", []) or ["None"])

    incident_history = summary["incident_history"]
    lines.extend(["", "## Incident history"])
    lines.append(f"- Artifact count considered: {incident_history.get('artifact_count')}")
    lines.append(f"- Blocked artifact count: {incident_history.get('blocked_artifact_count')}")
    lines.append(f"- Latest status: {incident_history.get('latest_status')}")
    lines.append(f"- First blocked at: {incident_history.get('first_blocked_at') or 'None'}")
    lines.append(f"- First no-server at: {incident_history.get('first_no_server_at') or 'None'}")
    lines.append(f"- Current state started at: {incident_history.get('current_state_started_at') or 'None'}")
    lines.append(f"- Blocked duration: {incident_history.get('blocked_duration') or 'None'}")
    lines.append(f"- No-server duration: {incident_history.get('no_server_duration') or 'None'}")
    lines.append(f"- Current state duration: {incident_history.get('current_state_duration') or 'None'}")

    incident = summary["render_incident_signature"]
    lines.extend(
        [
            "",
            "## Render incident signature",
            f"- Repo contract OK: {'YES' if incident['repo_contract_ok'] else 'NO'}",
            f"- App host attachment state: {incident['app_host_attachment_state']}",
            f"- Webhook host attachment state: {incident['webhook_host_attachment_state']}",
            f"- External routing issue isolated: {'YES' if incident['external_routing_issue'] else 'NO'}",
            f"- Conclusion: {incident['conclusion']}",
            "",
            "## Render support packet",
        ]
    )
    support_packet = summary["render_support_packet"]
    lines.append(f"- Incident type: {support_packet['incident_type']}")
    lines.append(f"- Requested action: {support_packet['requested_action']}")
    for service_name, details in support_packet["host_comparison"].items():
        lines.append(
            "- {}: host={}; probe_path={}; status={} {}; attachment_state={}; x-render-origin-server={}; x-render-routing={}; cf-ray={}; date={}".format(
                service_name,
                details.get("host"),
                details.get("probe_path"),
                details.get("status"),
                details.get("reason"),
                details.get("attachment_state"),
                details.get("x_render_origin_server") or "None",
                details.get("x_render_routing") or "None",
                details.get("cf_ray") or "None",
                details.get("date") or "None",
            )
        )

    escalation = summary["escalation_recommendation"]
    lines.extend(
        [
            "",
            "## Escalation recommendation",
            f"- Severity: {escalation['severity']}",
            f"- Owner: {escalation['owner']}",
            f"- Destination: {escalation['destination']}",
            f"- Unchanged blocked streak: {escalation['unchanged_blocked_streak']}",
            f"- Urgency: {escalation['urgency']}",
            f"- Prerequisite: {escalation['prerequisite']}",
            f"- Recommended message: {escalation['recommended_message']}",
            "",
            "## Artifact refresh commands",
        ]
    )
    for label, command in summary["artifact_refresh_commands"].items():
        lines.append(f"- {label}: {command}")

    lines.extend(
        [
            "",
            "## Artifact inventory",
        ]
    )
    inventory = summary["artifact_inventory"]
    for label, details in inventory.items():
        if isinstance(details, dict):
            lines.append(
                "- {}: path={}; exists={}; size_bytes={}; modified_at={}".format(
                    label,
                    details.get("path"),
                    "YES" if details.get("exists") else "NO",
                    details.get("size_bytes"),
                    details.get("modified_at") or "None",
                )
            )
        else:
            lines.append(f"- {label}: {', '.join(details) if details else 'None'}")

    lines.extend(
        [
            "",
            "## Owner action plan",
        ]
    )
    for owner, actions in summary["owner_action_plan"].items():
        lines.append(f"- {owner}:")
        for action in actions:
            lines.append(f"  - {action}")

    lines.extend(
        [
            "",
            "## Owner ready messages",
        ]
    )
    for owner, message in summary["owner_ready_messages"].items():
        lines.append(f"- {owner}: {message}")

    lines.extend(
        [
            "",
            "## Render recovery playbook",
        ]
    )
    lines.extend(f"- {step}" for step in summary["render_recovery_playbook"] or ["None"])

    lines.extend(
        [
            "",
            "## Recovery exit criteria",
        ]
    )
    lines.extend(f"- {step}" for step in summary["recovery_exit_criteria"] or ["None"])

    lines.extend(
        [
            "",
            "## Render escalation message",
            summary["render_escalation_message"] or "None",
            "",
            "## Render escalation payload",
        ]
    )
    payload = summary["render_escalation_payload"]
    for key in [
        "ticket_title",
        "severity",
        "owner",
        "destination",
        "generated_at",
        "incident_type",
        "unchanged_blocked_streak",
        "repo_contract_ok",
        "external_routing_issue",
        "app_host_evidence",
        "webhook_host_evidence",
        "requested_action",
        "recommended_message",
    ]:
        lines.append(f"- {key}: {payload.get(key)}")
    lines.append(
        "- missing_live_e2e_secrets: "
        + (", ".join(payload.get("missing_live_e2e_secrets", [])) or "None")
    )

    lines.extend(
        [
            "",
            "## Probe previews",
            f"- Webhook health preview: {health_probe.get('body_preview', '')}",
            f"- Webhook root preview: {root_probe.get('body_preview', '')}",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-check the AMS-APP trial signup stack.")
    parser.add_argument("--json-out", help="Optional path to write the JSON report.")
    parser.add_argument("--markdown-out", help="Optional path to write a Markdown summary report.")
    parser.add_argument(
        "--owner-messages-dir",
        help="Optional directory to write copy-ready owner handoff text files.",
    )
    parser.add_argument(
        "--owner-messages-archive-dir",
        help="Optional directory to write timestamped owner handoff snapshots for historical escalation evidence.",
    )
    parser.add_argument(
        "--escalation-packet-dir",
        help="Optional directory to write a send-ready Render escalation packet with message, JSON payload, and evidence manifest.",
    )
    parser.add_argument(
        "--escalation-packet-archive-dir",
        help="Optional directory to write timestamped Render escalation packet snapshots for historical support evidence.",
    )
    return parser.parse_args(argv)


def load_previous_report(json_out: str | None = None) -> dict[str, Any] | None:
    candidate_paths: list[Path] = []
    if json_out:
        candidate_paths.append(Path(json_out))
    if DEFAULT_JSON_ARTIFACT not in candidate_paths:
        candidate_paths.append(DEFAULT_JSON_ARTIFACT)

    for path in candidate_paths:
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

    return None


def write_owner_ready_messages(report: dict[str, Any], output_dir: str) -> list[Path]:
    base_path = Path(output_dir)
    base_path.mkdir(parents=True, exist_ok=True)

    written_paths: list[Path] = []
    for owner, message in report.get("summary", {}).get("owner_ready_messages", {}).items():
        target_path = base_path / f"{owner}.txt"
        target_path.write_text(str(message).rstrip() + "\n", encoding="utf-8")
        written_paths.append(target_path)

    return written_paths


def write_owner_ready_archive(report: dict[str, Any], archive_dir: str) -> list[Path]:
    archive_paths = build_owner_ready_archive_file_paths(report, archive_dir)
    if not archive_paths:
        return []

    base_path = Path(archive_dir)
    base_path.mkdir(parents=True, exist_ok=True)

    written_paths: list[Path] = []
    for owner, target_path in archive_paths.items():
        message = report.get("summary", {}).get("owner_ready_messages", {}).get(owner)
        if message is None:
            continue
        target_path.write_text(str(message).rstrip() + "\n", encoding="utf-8")
        written_paths.append(target_path)

    return written_paths


def build_escalation_packet_file_contents(report: dict[str, Any]) -> dict[str, str]:
    summary = report.get("summary", {})
    payload = summary.get("render_escalation_payload", {})
    message = summary.get("render_escalation_message", "")
    inventory = summary.get("artifact_inventory", {})

    return {
        "render-support-message.txt": str(message).rstrip() + "\n",
        "render-support-payload.json": json.dumps(payload, indent=2, sort_keys=True) + "\n",
        "evidence-manifest.json": json.dumps(
            {
                "generated_at": report.get("generated_at"),
                "recommended_attachments": inventory.get("recommended_attachments", []),
                "render_support_packet_files": inventory.get("render_support_packet_files", []),
                "traction_handoff_files": inventory.get("traction_handoff_files", []),
                "artifact_inventory": inventory,
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        "README.txt": build_escalation_packet_readme(report),
    }


def write_escalation_packet(report: dict[str, Any], output_dir: str) -> list[Path]:
    base_path = Path(output_dir)
    base_path.mkdir(parents=True, exist_ok=True)

    files_to_write = build_escalation_packet_file_contents(report)

    written_paths: list[Path] = []
    for filename, content in files_to_write.items():
        target_path = base_path / filename
        target_path.write_text(content, encoding="utf-8")
        written_paths.append(target_path)

    return written_paths


def write_escalation_packet_archive(report: dict[str, Any], archive_dir: str) -> list[Path]:
    archive_paths = build_escalation_packet_archive_file_paths(report, archive_dir)
    if not archive_paths:
        return []

    base_path = Path(archive_dir)
    base_path.mkdir(parents=True, exist_ok=True)
    files_to_write = build_escalation_packet_file_contents(report)

    written_paths: list[Path] = []
    for filename, target_path in archive_paths.items():
        content = files_to_write.get(filename)
        if content is None:
            continue
        target_path.write_text(content, encoding="utf-8")
        written_paths.append(target_path)

    return written_paths


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    previous_report = load_previous_report(args.json_out)
    report = generate_report(previous_report=previous_report)
    payload = json.dumps(report, indent=2, sort_keys=True)
    print(payload)

    if args.json_out:
        Path(args.json_out).write_text(payload + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown_report(report), encoding="utf-8")
    if args.owner_messages_dir:
        write_owner_ready_messages(report, args.owner_messages_dir)
    if args.owner_messages_archive_dir:
        write_owner_ready_archive(report, args.owner_messages_archive_dir)
    if args.escalation_packet_dir:
        write_escalation_packet(report, args.escalation_packet_dir)
    if args.escalation_packet_archive_dir:
        write_escalation_packet_archive(report, args.escalation_packet_archive_dir)

    report["summary"]["artifact_inventory"] = build_artifact_inventory()
    refreshed_payload = json.dumps(report, indent=2, sort_keys=True)
    if args.json_out:
        Path(args.json_out).write_text(refreshed_payload + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown_report(report), encoding="utf-8")

    return 0 if report["summary"]["ready_for_live_e2e"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
