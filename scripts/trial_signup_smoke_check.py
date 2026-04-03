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
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
    for key in ("x-render-routing", "x-render-origin-server", "server", "content-type"):
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


def generate_report() -> dict[str, Any]:
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
    report["summary"] = {
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
        "ready_for_live_e2e": (
            report["public_checks"]["app"]["ok"]
            and report["public_checks"]["webhook_health"]["ok"]
            and report["local_checks"]["webhook_health_route"]["ok"]
            and report["local_checks"]["checkout_contract"]["ok"]
            and report["local_checks"]["render_blueprint"]["ok"]
            and report["local_checks"]["webhook_service_contract"]["ok"]
            and not missing_required
        ),
    }
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
    ]
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = generate_report()
    payload = json.dumps(report, indent=2, sort_keys=True)
    print(payload)

    if args.json_out:
        Path(args.json_out).write_text(payload + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown_report(report), encoding="utf-8")

    return 0 if report["summary"]["ready_for_live_e2e"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
