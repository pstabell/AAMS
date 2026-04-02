import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest import mock

MODULE_PATH = pathlib.Path(__file__).resolve().parent / "scripts" / "trial_signup_smoke_check.py"
spec = importlib.util.spec_from_file_location("trial_signup_smoke_check", MODULE_PATH)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class TrialSignupSmokeCheckTests(unittest.TestCase):
    def test_build_webhook_diagnostic_urls_expands_expected_paths(self):
        urls = smoke.build_webhook_diagnostic_urls("https://commission-tracker-webhook.onrender.com")

        self.assertEqual(
            urls,
            [
                "https://commission-tracker-webhook.onrender.com/",
                "https://commission-tracker-webhook.onrender.com/health",
                "https://commission-tracker-webhook.onrender.com/test",
                "https://commission-tracker-webhook.onrender.com/stripe-webhook",
            ],
        )

    def test_diagnose_public_webhook_flags_all_404_as_misconfiguration_signal(self):
        with mock.patch.object(
            smoke,
            "fetch_url",
            side_effect=[
                {"ok": False, "status": 404, "reason": "Not Found", "body_preview": "missing", "headers": {}},
                {"ok": False, "status": 404, "reason": "Not Found", "body_preview": "missing", "headers": {}},
                {"ok": False, "status": 404, "reason": "Not Found", "body_preview": "missing", "headers": {}},
                {"ok": False, "status": 404, "reason": "Not Found", "body_preview": "missing", "headers": {}},
            ],
        ):
            details = smoke.diagnose_public_webhook("https://commission-tracker-webhook.onrender.com")

        self.assertFalse(details["any_ok"])
        self.assertTrue(details["all_404"])
        self.assertFalse(details["no_server"])
        self.assertIn("wrong app", details["likely_cause"].lower())

    def test_diagnose_public_webhook_flags_render_no_server_as_primary_cause(self):
        with mock.patch.object(
            smoke,
            "fetch_url",
            side_effect=[
                {"ok": False, "status": 404, "reason": "Not Found", "body_preview": "missing", "headers": {"x-render-routing": "no-server"}},
                {"ok": False, "status": 404, "reason": "Not Found", "body_preview": "missing", "headers": {"x-render-routing": "no-server"}},
                {"ok": False, "status": 404, "reason": "Not Found", "body_preview": "missing", "headers": {"x-render-routing": "no-server"}},
                {"ok": False, "status": 404, "reason": "Not Found", "body_preview": "missing", "headers": {"x-render-routing": "no-server"}},
            ],
        ):
            details = smoke.diagnose_public_webhook("https://commission-tracker-webhook.onrender.com")

        self.assertTrue(details["all_404"])
        self.assertTrue(details["no_server"])
        self.assertEqual(details["render_routing_modes"], ["no-server"])
        self.assertIn("no healthy backend service", details["likely_cause"].lower())

    def test_inspect_env_var_reports_presence_and_length(self):
        with mock.patch.dict(smoke.os.environ, {"STRIPE_SECRET_KEY": "secret-value"}, clear=True):
            details = smoke.inspect_env_var("STRIPE_SECRET_KEY")

        self.assertTrue(details["present"])
        self.assertEqual(details["length"], len("secret-value"))

    def test_check_local_dependencies_reports_missing_modules(self):
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name in {"flask", "stripe"}:
                raise ModuleNotFoundError(name)
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=fake_import):
            details = smoke.check_local_dependencies()

        self.assertFalse(details["ok"])
        self.assertEqual(details["missing_modules"], ["flask", "stripe"])

    def test_check_local_webhook_route_short_circuits_when_dependencies_missing(self):
        with mock.patch.object(
            smoke,
            "check_local_dependencies",
            return_value={"ok": False, "missing_modules": ["stripe"]},
        ):
            details = smoke.check_local_webhook_route()

        self.assertFalse(details["ok"])
        self.assertIn("dependencies missing", details["payload"].lower())
        self.assertEqual(details["dependency_check"]["missing_modules"], ["stripe"])

    def test_build_local_webhook_dependency_commands_uses_missing_modules(self):
        report = {
            "local_checks": {
                "webhook_health_route": {
                    "dependency_check": {
                        "missing_modules": ["flask", "stripe"],
                    }
                }
            }
        }

        commands = smoke.build_local_webhook_dependency_commands(report)

        self.assertEqual(commands[0], "python3 -m pip install flask stripe")
        self.assertEqual(commands[1], "python3 -m pip install -r requirements.txt")
        self.assertIn("from webhook_server import app", commands[2])
        self.assertIn("client.get('/health')", commands[2])

    def test_build_render_service_env_gap_groups_missing_env_by_service(self):
        report = {
            "env": {
                "required_for_live_e2e": {
                    "STRIPE_SECRET_KEY": {"present": True, "length": 10},
                    "STRIPE_WEBHOOK_SECRET": {"present": False, "length": 0},
                    "STRIPE_PRICE_ID": {"present": True, "length": 10},
                    "RESEND_API_KEY": {"present": False, "length": 0},
                    "SUPABASE_SERVICE_KEY": {"present": True, "length": 10},
                },
                "optional_context": {
                    "APP_ENVIRONMENT": {"present": True, "length": 10},
                    "PRODUCTION_SUPABASE_URL": {"present": False, "length": 0},
                    "PRODUCTION_SUPABASE_ANON_KEY": {"present": False, "length": 0},
                    "PRODUCTION_SUPABASE_SERVICE_KEY": {"present": False, "length": 0},
                },
            },
            "local_checks": {
                "render_blueprint": {
                    "services": {
                        "commission-tracker-app": {
                            "present": True,
                            "start_command": "streamlit run commission_app.py --server.port $PORT --server.address 0.0.0.0",
                            "health_check_path": "/",
                            "missing_required_env_vars": [],
                        },
                        "commission-tracker-webhook": {
                            "present": True,
                            "start_command": "gunicorn webhook_server:app",
                            "health_check_path": "/health",
                            "missing_required_env_vars": [],
                        },
                    }
                }
            },
        }

        with mock.patch.object(
            smoke,
            "inspect_env_var",
            side_effect=lambda name: {
                "SUPABASE_URL": {"present": True, "length": 10},
                "SUPABASE_ANON_KEY": {"present": True, "length": 10},
                "RENDER_APP_URL": {"present": True, "length": 10},
                "SMTP_HOST": {"present": False, "length": 0},
                "SMTP_PORT": {"present": False, "length": 0},
                "SMTP_USER": {"present": False, "length": 0},
                "SMTP_PASS": {"present": False, "length": 0},
                "FROM_EMAIL": {"present": False, "length": 0},
            }.get(name, {"present": False, "length": 0}),
        ):
            details = smoke.build_render_service_env_gap(report)

        self.assertFalse(details["commission-tracker-app"]["shell_ready"])
        self.assertIn("RESEND_API_KEY", details["commission-tracker-app"]["missing_in_shell"])
        self.assertIn("STRIPE_WEBHOOK_SECRET", details["commission-tracker-webhook"]["missing_in_shell"])
        self.assertIn("SMTP_HOST", details["commission-tracker-webhook"]["missing_in_shell"])
        self.assertEqual(details["commission-tracker-webhook"]["missing_in_blueprint"], [])

    def test_check_render_blueprint_reports_expected_services(self):
        render_yaml = """
services:
  - type: web
    name: commission-tracker-app
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: streamlit run commission_app.py --server.port $PORT --server.address 0.0.0.0
    healthCheckPath: /
    envVars:
      - key: APP_ENVIRONMENT
      - key: PRODUCTION_SUPABASE_URL
      - key: PRODUCTION_SUPABASE_ANON_KEY
      - key: PRODUCTION_SUPABASE_SERVICE_KEY
      - key: SUPABASE_URL
      - key: SUPABASE_ANON_KEY
      - key: SUPABASE_SERVICE_KEY
      - key: STRIPE_SECRET_KEY
      - key: STRIPE_PRICE_ID
      - key: RESEND_API_KEY
      - key: RENDER_APP_URL

  - type: web
    name: commission-tracker-webhook
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn webhook_server:app
    healthCheckPath: /health
    envVars:
      - key: APP_ENVIRONMENT
      - key: PRODUCTION_SUPABASE_URL
      - key: PRODUCTION_SUPABASE_ANON_KEY
      - key: PRODUCTION_SUPABASE_SERVICE_KEY
      - key: SUPABASE_URL
      - key: SUPABASE_ANON_KEY
      - key: SUPABASE_SERVICE_KEY
      - key: STRIPE_SECRET_KEY
      - key: STRIPE_WEBHOOK_SECRET
      - key: STRIPE_PRICE_ID
      - key: RESEND_API_KEY
      - key: SMTP_HOST
      - key: SMTP_PORT
      - key: SMTP_USER
      - key: SMTP_PASS
      - key: FROM_EMAIL
      - key: RENDER_APP_URL
"""
        with mock.patch.object(pathlib.Path, "read_text", return_value=render_yaml):
            details = smoke.check_render_blueprint()

        self.assertTrue(details["ok"])
        self.assertEqual(details["status"], 200)
        self.assertEqual(details["payload"], "Render blueprint looks complete")
        self.assertEqual(details["missing_services"], [])
        self.assertTrue(details["services"]["commission-tracker-app"]["start_command_ok"])
        self.assertTrue(details["services"]["commission-tracker-webhook"]["health_check_path_ok"])

    def test_check_webhook_service_contract_reports_expected_routes_and_packages(self):
        webhook_source = """
@app.route('/')
def home():
    return 'ok'

@app.route('/health', methods=['GET'])
def health_check():
    return 'ok'

@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    return 'ok'

@app.route('/test', methods=['GET', 'POST'])
def test_endpoint():
    return 'ok'
"""
        requirements = "Flask\nstripe\nsupabase\ngunicorn\n"
        with mock.patch.object(
            pathlib.Path,
            "read_text",
            side_effect=[webhook_source, requirements],
        ):
            details = smoke.check_webhook_service_contract()

        self.assertTrue(details["ok"])
        self.assertEqual(details["status"], 200)
        self.assertEqual(details["payload"], "Webhook service contract looks complete")
        self.assertTrue(details["routes"]["/health"]["ok"])
        self.assertTrue(details["requirements"]["flask"])
        self.assertEqual(details["missing_packages"], [])

    def test_check_webhook_service_contract_reports_missing_routes_and_packages(self):
        webhook_source = """
@app.route('/')
def home():
    return 'ok'
"""
        requirements = "Flask\n"
        with mock.patch.object(
            pathlib.Path,
            "read_text",
            side_effect=[webhook_source, requirements],
        ):
            details = smoke.check_webhook_service_contract()

        self.assertFalse(details["ok"])
        self.assertEqual(details["status"], 500)
        self.assertIn("Missing webhook route contract for /health", details["payload"])
        self.assertIn("requirements.txt is missing packages", details["payload"])
        self.assertIn("stripe", details["missing_packages"])
        self.assertFalse(details["routes"]["/health"]["ok"])

    def test_check_render_blueprint_reports_missing_requirements_cleanly(self):
        render_yaml = """
services:
  - type: web
    name: commission-tracker-webhook
    startCommand: python webhook_server.py
    healthCheckPath: /
    envVars:
      - key: STRIPE_SECRET_KEY
"""
        with mock.patch.object(pathlib.Path, "read_text", return_value=render_yaml):
            details = smoke.check_render_blueprint()

        self.assertFalse(details["ok"])
        self.assertEqual(details["status"], 500)
        self.assertIn("Missing Render service: commission-tracker-app", details["payload"])
        self.assertIn("startCommand mismatch", details["payload"])
        self.assertIn("healthCheckPath mismatch", details["payload"])
        self.assertIn("missing env vars", details["payload"])

    def test_check_checkout_contract_reports_expected_stripe_contract(self):
        auth_helpers_source = """
def _build_checkout_kwargs(email: str, accepted_at: str, price_id: str, app_url: str) -> dict:
    return dict(
        line_items=[{'price': price_id, 'quantity': 1}],
        mode='subscription',
        customer_email=email,
        subscription_data={'trial_period_days': SUBSCRIPTION_OFFER['trial_days']},
        metadata={
            'accepted_terms': 'true',
            'accepted_privacy': 'true',
            'accepted_at': accepted_at,
            'terms_version': SUBSCRIPTION_OFFER.get('terms_version', '2024-12-06'),
            'privacy_version': SUBSCRIPTION_OFFER.get('privacy_version', '2024-12-06'),
        },
        payment_method_collection='if_required',
        success_url=app_url + '/?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=app_url,
        allow_promotion_codes=True,
    )

"""
        with mock.patch.object(pathlib.Path, "read_text", return_value=auth_helpers_source):
            details = smoke.check_checkout_contract()

        self.assertTrue(details["ok"])
        self.assertEqual(details["status"], 200)
        self.assertEqual(details["payload"]["mode"], "subscription")
        self.assertEqual(details["payload"]["trial_period_days"], 14)
        self.assertEqual(details["payload"]["payment_method_collection"], "if_required")
        self.assertTrue(details["payload"]["allow_promotion_codes"])
        self.assertIn("accepted_terms", details["payload"]["metadata_keys"])

    def test_check_checkout_contract_reports_parse_failure_cleanly(self):
        with mock.patch.object(pathlib.Path, "read_text", return_value="def nope():\n    return None\n"):
            details = smoke.check_checkout_contract()

        self.assertFalse(details["ok"])
        self.assertIsNone(details["status"])
        self.assertIn("Could not locate _build_checkout_kwargs", details["payload"])

    def _build_ready_report(self):
        env_values = {name: {"present": True, "length": 10} for name in smoke.LIVE_E2E_ENV_VARS}
        optional_values = {name: {"present": True, "length": 10} for name in smoke.OPTIONAL_ENV_VARS}

        with mock.patch.object(smoke, "fetch_url", side_effect=[
            {"ok": True, "status": 200, "reason": "OK", "body_preview": "app ok"},
            {"ok": True, "status": 200, "reason": "OK", "body_preview": "webhook ok"},
        ]), mock.patch.object(
            smoke,
            "diagnose_public_webhook",
            return_value={
                "base_url": "https://commission-tracker-webhook.onrender.com",
                "probed_endpoints": {
                    "https://commission-tracker-webhook.onrender.com/": {"ok": True, "status": 200, "reason": "OK", "body_preview": "root ok", "headers": {"x-render-origin-server": "gunicorn"}},
                    "https://commission-tracker-webhook.onrender.com/health": {"ok": True, "status": 200, "reason": "OK", "body_preview": "healthy", "headers": {"x-render-origin-server": "gunicorn"}},
                },
                "any_ok": True,
                "all_404": False,
                "render_routing_modes": [],
                "no_server": False,
                "likely_cause": "Webhook service is reachable; the configured health URL may be wrong.",
            },
        ), mock.patch.object(
            smoke,
            "inspect_env_var",
            side_effect=lambda name: env_values[name] if name in env_values else optional_values.get(name, {"present": True, "length": 10}),
        ), mock.patch.object(
            smoke,
            "check_local_webhook_route",
            return_value={"ok": True, "status": 200, "payload": {"status": "ok"}, "dependency_check": {"ok": True, "missing_modules": []}},
        ), mock.patch.object(
            smoke,
            "check_checkout_contract",
            return_value={
                "ok": True,
                "status": 200,
                "payload": {
                    "mode": "subscription",
                    "trial_period_days": 14,
                    "payment_method_collection": "if_required",
                    "allow_promotion_codes": True,
                    "success_url": "https://commission-tracker-app.onrender.com/?session_id={CHECKOUT_SESSION_ID}",
                    "cancel_url": "https://commission-tracker-app.onrender.com",
                    "metadata_keys": ["accepted_at", "accepted_privacy", "accepted_terms", "privacy_version", "terms_version"],
                },
                "expected_trial_days": 14,
                "price_id_source": "placeholder",
            },
        ), mock.patch.object(
            smoke,
            "check_render_blueprint",
            return_value={
                "ok": True,
                "status": 200,
                "payload": "Render blueprint looks complete",
                "services": {},
                "missing_services": [],
            },
        ), mock.patch.object(
            smoke,
            "check_webhook_service_contract",
            return_value={
                "ok": True,
                "status": 200,
                "payload": "Webhook service contract looks complete",
                "routes": {},
                "requirements": {},
                "missing_packages": [],
            },
        ):
            return smoke.generate_report()

    def test_render_markdown_report_includes_readiness_summary(self):
        report = self._build_ready_report()

        markdown = smoke.render_markdown_report(report)

        self.assertIn("# Trial Signup Smoke Check Snapshot", markdown)
        self.assertIn("Ready for live e2e: YES", markdown)
        self.assertIn("Webhook no-server detected: NO", markdown)
        self.assertIn("Any webhook endpoint OK: YES", markdown)
        self.assertIn("Checkout contract OK: YES", markdown)
        self.assertIn("Render blueprint OK: YES", markdown)
        self.assertIn("Webhook service contract OK: YES", markdown)
        self.assertIn("## Blocking reasons", markdown)
        self.assertIn("## Recommended next actions", markdown)
        self.assertIn("## Render restore checklist", markdown)
        self.assertIn("## Render restore validation commands", markdown)
        self.assertIn("## Local webhook dependency commands", markdown)
        self.assertIn("## Render service env gap", markdown)
        self.assertIn("Open the Render dashboard for service commission-tracker-webhook.", markdown)
        self.assertIn("curl -i https://commission-tracker-webhook.onrender.com/health", markdown)
        self.assertIn("Run one real Stripe test-mode signup", markdown)
        self.assertIn("- commission-tracker-webhook: shell_ready=YES; missing_in_shell=None; missing_in_blueprint=None", markdown)
        self.assertIn("- None", markdown)

    def test_main_returns_zero_when_stack_is_ready(self):
        report = self._build_ready_report()

        with mock.patch.object(smoke, "generate_report", return_value=report), mock.patch("sys.stdout") as stdout:
            exit_code = smoke.main([])

        self.assertEqual(exit_code, 0)
        written = "".join(call.args[0] for call in stdout.write.call_args_list)
        payload = json.loads(written)
        self.assertTrue(payload["summary"]["ready_for_live_e2e"])
        self.assertTrue(payload["summary"]["public_webhook_any_endpoint_ok"])
        self.assertFalse(payload["summary"]["public_webhook_all_probed_endpoints_404"])
        self.assertFalse(payload["summary"]["public_webhook_no_server"])
        self.assertTrue(payload["summary"]["checkout_contract_ok"])
        self.assertTrue(payload["summary"]["render_blueprint_ok"])
        self.assertTrue(payload["summary"]["webhook_service_contract_ok"])
        self.assertEqual(payload["summary"]["missing_required_env_vars"], [])
        self.assertGreaterEqual(len(payload["summary"]["render_restore_checklist"]), 1)
        self.assertGreaterEqual(len(payload["summary"]["render_restore_validation_commands"]), 3)
        self.assertIn("commission-tracker-webhook", payload["summary"]["render_restore_checklist"][0])
        self.assertEqual(payload["summary"]["render_restore_validation_commands"][0], "curl -i https://commission-tracker-webhook.onrender.com/health")
        self.assertEqual(payload["summary"]["render_service_env_gap"]["commission-tracker-app"]["missing_in_shell"], [])
        self.assertTrue(payload["summary"]["render_service_env_gap"]["commission-tracker-webhook"]["shell_ready"])

    def test_main_can_write_json_and_markdown_outputs(self):
        report = self._build_ready_report()

        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = pathlib.Path(temp_dir) / "report.json"
            markdown_path = pathlib.Path(temp_dir) / "report.md"

            with mock.patch.object(smoke, "generate_report", return_value=report), mock.patch("sys.stdout"):
                exit_code = smoke.main(["--json-out", str(json_path), "--markdown-out", str(markdown_path)])

            self.assertEqual(exit_code, 0)
            self.assertTrue(json_path.exists())
            self.assertTrue(markdown_path.exists())
            self.assertTrue(json.loads(json_path.read_text())["summary"]["ready_for_live_e2e"])
            self.assertIn("Trial Signup Smoke Check Snapshot", markdown_path.read_text())

    def test_main_returns_one_when_public_webhook_or_env_is_missing(self):
        required = {
            smoke.LIVE_E2E_ENV_VARS[0]: {"present": True, "length": 8},
            smoke.LIVE_E2E_ENV_VARS[1]: {"present": False, "length": 0},
            smoke.LIVE_E2E_ENV_VARS[2]: {"present": True, "length": 8},
            smoke.LIVE_E2E_ENV_VARS[3]: {"present": True, "length": 8},
            smoke.LIVE_E2E_ENV_VARS[4]: {"present": True, "length": 8},
        }
        optional_values = {name: {"present": False, "length": 0} for name in smoke.OPTIONAL_ENV_VARS}

        with mock.patch.object(smoke, "fetch_url", side_effect=[
            {"ok": True, "status": 200, "reason": "OK", "body_preview": "app ok"},
            {"ok": False, "status": 404, "reason": "Not Found", "body_preview": "missing"},
        ]), mock.patch.object(
            smoke,
            "diagnose_public_webhook",
            return_value={
                "base_url": "https://commission-tracker-webhook.onrender.com",
                "probed_endpoints": {
                    "https://commission-tracker-webhook.onrender.com/": {"ok": False, "status": 404, "reason": "Not Found", "body_preview": "missing", "headers": {"x-render-routing": "no-server"}},
                    "https://commission-tracker-webhook.onrender.com/health": {"ok": False, "status": 404, "reason": "Not Found", "body_preview": "missing", "headers": {"x-render-routing": "no-server"}},
                },
                "any_ok": False,
                "all_404": True,
                "render_routing_modes": ["no-server"],
                "no_server": True,
                "likely_cause": "Render is reporting x-render-routing=no-server for the webhook hostname. That usually means there is no healthy backend service attached to this route yet or the service is not deployed behind the expected domain.",
            },
        ), mock.patch.object(
            smoke,
            "inspect_env_var",
            side_effect=lambda name: required[name] if name in required else optional_values.get(name, {"present": False, "length": 0}),
        ), mock.patch.object(
            smoke,
            "check_local_webhook_route",
            return_value={"ok": True, "status": 200, "payload": {"status": "ok"}, "dependency_check": {"ok": True, "missing_modules": []}},
        ), mock.patch.object(
            smoke,
            "check_checkout_contract",
            return_value={
                "ok": True,
                "status": 200,
                "payload": {
                    "mode": "subscription",
                    "trial_period_days": 14,
                    "payment_method_collection": "if_required",
                    "allow_promotion_codes": True,
                    "success_url": "https://commission-tracker-app.onrender.com/?session_id={CHECKOUT_SESSION_ID}",
                    "cancel_url": "https://commission-tracker-app.onrender.com",
                    "metadata_keys": ["accepted_at", "accepted_privacy", "accepted_terms", "privacy_version", "terms_version"],
                },
                "expected_trial_days": 14,
                "price_id_source": "placeholder",
            },
        ), mock.patch.object(
            smoke,
            "check_render_blueprint",
            return_value={
                "ok": True,
                "status": 200,
                "payload": "Render blueprint looks complete",
                "services": {},
                "missing_services": [],
            },
        ), mock.patch.object(
            smoke,
            "check_webhook_service_contract",
            return_value={
                "ok": True,
                "status": 200,
                "payload": "Webhook service contract looks complete",
                "routes": {},
                "requirements": {},
                "missing_packages": [],
            },
        ), mock.patch("sys.stdout") as stdout:
            exit_code = smoke.main([])

        self.assertEqual(exit_code, 1)
        written = "".join(call.args[0] for call in stdout.write.call_args_list)
        payload = json.loads(written)
        self.assertFalse(payload["summary"]["public_webhook_ok"])
        self.assertFalse(payload["summary"]["public_webhook_any_endpoint_ok"])
        self.assertTrue(payload["summary"]["public_webhook_all_probed_endpoints_404"])
        self.assertTrue(payload["summary"]["public_webhook_no_server"])
        self.assertEqual(payload["summary"]["public_webhook_render_routing_modes"], ["no-server"])
        self.assertIn("no healthy backend service", payload["summary"]["public_webhook_likely_cause"].lower())
        self.assertTrue(payload["summary"]["checkout_contract_ok"])
        self.assertEqual(payload["summary"]["missing_required_env_vars"], ["STRIPE_WEBHOOK_SECRET"])
        self.assertGreaterEqual(len(payload["summary"]["blocking_reasons"]), 2)
        self.assertTrue(any("no-server" in reason.lower() for reason in payload["summary"]["blocking_reasons"]))
        self.assertTrue(any("missing stripe" in action.lower() or "missing stripe, resend, and supabase" in action.lower() for action in payload["summary"]["next_actions"]))
        self.assertTrue(any("x-render-routing=no-server" in step for step in payload["summary"]["render_restore_checklist"]))
        self.assertTrue(any(command.startswith("export STRIPE_WEBHOOK_SECRET=...") for command in payload["summary"]["render_restore_validation_commands"]))
        self.assertIn("STRIPE_WEBHOOK_SECRET", payload["summary"]["render_service_env_gap"]["commission-tracker-webhook"]["missing_in_shell"])
        self.assertEqual(payload["summary"]["local_webhook_dependency_commands"], [])
        self.assertFalse(payload["summary"]["ready_for_live_e2e"])


if __name__ == "__main__":
    unittest.main()
