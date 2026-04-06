import importlib.util
import json
import pathlib
import tempfile
import unittest
import zipfile
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

    def test_build_repo_context_reports_clean_git_head(self):
        responses = {
            ("rev-parse", "--abbrev-ref", "HEAD"): "main",
            ("rev-parse", "HEAD"): "abc123def456",
            ("rev-parse", "--short", "HEAD"): "abc123d",
            ("status", "--short"): "",
            ("remote", "get-url", "origin"): "https://github.com/pstabell/AMS-APP.git",
            ("log", "-1", "--pretty=%s"): "feat: sample commit",
            ("log", "-1", "--date=iso-strict", "--pretty=%cI"): "2026-04-05T18:00:00+00:00",
        }

        with mock.patch.object(smoke, "_run_git_command", side_effect=lambda *args: responses.get(args)):
            context = smoke.build_repo_context()

        self.assertTrue(context["available"])
        self.assertEqual(context["branch"], "main")
        self.assertEqual(context["short_head"], "abc123d")
        self.assertEqual(context["status"], "clean")
        self.assertFalse(context["dirty"])
        self.assertEqual(context["tracked_changes"], [])

    def test_build_repo_context_reports_dirty_git_head(self):
        responses = {
            ("rev-parse", "--abbrev-ref", "HEAD"): "main",
            ("rev-parse", "HEAD"): "abc123def456",
            ("rev-parse", "--short", "HEAD"): "abc123d",
            ("status", "--short"): " M scripts/trial_signup_smoke_check.py\n?? docs/smoke-checks/latest-trial-signup-smoke-check.md",
            ("remote", "get-url", "origin"): "https://github.com/pstabell/AMS-APP.git",
            ("log", "-1", "--pretty=%s"): "feat: sample commit",
            ("log", "-1", "--date=iso-strict", "--pretty=%cI"): "2026-04-05T18:00:00+00:00",
        }

        with mock.patch.object(smoke, "_run_git_command", side_effect=lambda *args: responses.get(args)):
            context = smoke.build_repo_context()

        self.assertEqual(context["status"], "dirty")
        self.assertTrue(context["dirty"])
        self.assertEqual(
            context["tracked_changes"],
            [
                "M scripts/trial_signup_smoke_check.py",
                "?? docs/smoke-checks/latest-trial-signup-smoke-check.md",
            ],
        )

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
                            "start_command": "gunicorn webhook_server:app --bind 0.0.0.0:${PORT}",
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

    def test_build_render_service_env_commands_groups_actions_per_service(self):
        service_gap = {
            "commission-tracker-app": {
                "health_check_path": "/",
                "missing_in_shell": ["STRIPE_SECRET_KEY", "RESEND_API_KEY"],
                "missing_in_blueprint": [],
            },
            "commission-tracker-webhook": {
                "health_check_path": "/health",
                "missing_in_shell": ["STRIPE_WEBHOOK_SECRET"],
                "missing_in_blueprint": ["FROM_EMAIL"],
            },
        }

        commands = smoke.build_render_service_env_commands(service_gap)

        self.assertIn("Render dashboard -> commission-tracker-app -> Environment: set STRIPE_SECRET_KEY=..., RESEND_API_KEY=...", commands["commission-tracker-app"])
        self.assertIn("Verify commission-tracker-app serves / after the deploy.", commands["commission-tracker-app"])
        self.assertIn("Add the missing env vars to render.yaml for commission-tracker-webhook: FROM_EMAIL", commands["commission-tracker-webhook"])
        self.assertIn("Render dashboard -> commission-tracker-webhook -> Environment: set STRIPE_WEBHOOK_SECRET=...", commands["commission-tracker-webhook"])
        self.assertIn("Verify commission-tracker-webhook serves /health after the deploy.", commands["commission-tracker-webhook"])

    def test_build_render_service_contract_commands_lists_expected_dashboard_settings(self):
        commands = smoke.build_render_service_contract_commands()

        self.assertIn("Render dashboard -> commission-tracker-app -> Settings: confirm runtime=python and plan=starter", commands["commission-tracker-app"])
        self.assertIn("Render dashboard -> commission-tracker-app -> Build & Deploy: confirm startCommand='streamlit run commission_app.py --server.port ${PORT} --server.address 0.0.0.0'", commands["commission-tracker-app"])
        self.assertIn("Render dashboard -> commission-tracker-webhook -> Health Check: confirm path='/health'", commands["commission-tracker-webhook"])
        self.assertTrue(any("STRIPE_WEBHOOK_SECRET" in command for command in commands["commission-tracker-webhook"]))

    def test_build_render_domain_attachment_commands_target_expected_hosts(self):
        report = {
            "app_url": "https://commission-tracker-app.onrender.com",
            "webhook_base_url": "https://commission-tracker-webhook.onrender.com",
        }

        commands = smoke.build_render_domain_attachment_commands(report)

        self.assertIn(
            "Render dashboard -> commission-tracker-app -> Settings -> Custom Domains: confirm commission-tracker-app.onrender.com is attached to this service.",
            commands["commission-tracker-app"],
        )
        self.assertIn(
            "curl -I https://commission-tracker-webhook.onrender.com/health",
            commands["commission-tracker-webhook"],
        )
        self.assertTrue(any("x-render-routing=no-server" in command for command in commands["commission-tracker-webhook"]))

    def test_build_render_hostname_diagnostics_classifies_app_and_webhook_hosts(self):
        report = {
            "app_url": "https://commission-tracker-app.onrender.com",
            "webhook_base_url": "https://commission-tracker-webhook.onrender.com",
            "public_checks": {
                "app": {
                    "ok": True,
                    "status": 200,
                    "reason": "OK",
                    "headers": {
                        "server": "cloudflare",
                        "x-render-origin-server": "TornadoServer/6.5.5",
                    },
                },
                "webhook_health": {
                    "ok": False,
                    "status": 404,
                    "reason": "Not Found",
                    "headers": {
                        "server": "cloudflare",
                        "x-render-routing": "no-server",
                    },
                },
            },
        }

        details = smoke.build_render_hostname_diagnostics(report)

        self.assertEqual(details["commission-tracker-app"]["attachment_state"], "healthy-attached")
        self.assertEqual(details["commission-tracker-app"]["probe_path"], "/")
        self.assertIn("x-render-origin-server=TornadoServer/6.5.5", details["commission-tracker-app"]["evidence"])
        self.assertEqual(details["commission-tracker-webhook"]["attachment_state"], "missing-backend-attachment")
        self.assertEqual(details["commission-tracker-webhook"]["probe_path"], "/health")
        self.assertEqual(details["commission-tracker-webhook"]["x_render_routing"], "no-server")
        self.assertIn("HTTP 404", details["commission-tracker-webhook"]["evidence"])

    def test_build_artifact_refresh_commands_returns_copy_paste_runs(self):
        commands = smoke.build_artifact_refresh_commands()

        self.assertEqual(
            commands["json"],
            "python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json",
        )
        self.assertEqual(
            commands["markdown"],
            "python3 scripts/trial_signup_smoke_check.py --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md",
        )
        self.assertEqual(
            commands["both"],
            "python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md",
        )

    def test_build_packet_verification_commands_returns_copy_paste_checks(self):
        commands = smoke.build_packet_verification_commands()

        self.assertEqual(
            commands["latest_bundle"],
            [
                "cd . && sha256sum -c docs/smoke-checks/escalation-packet/escalation-packet.zip.sha256",
                "cd . && unzip -l docs/smoke-checks/escalation-packet/escalation-packet.zip",
            ],
        )
        self.assertEqual(
            commands["archived_bundle"],
            [
                "cd . && latest_checksum=$(ls -1t docs/smoke-checks/escalation-packet/archive/*-escalation-packet.zip.sha256 | head -n 1)",
                "cd . && sha256sum -c \"$latest_checksum\"",
                "cd . && latest_bundle=${latest_checksum%.sha256} && unzip -l \"$latest_bundle\"",
            ],
        )

    def test_build_artifact_inventory_reports_expected_handoff_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            (root / "docs" / "smoke-checks").mkdir(parents=True)
            (root / "scripts").mkdir(parents=True)
            (root / "docs" / "smoke-checks" / "latest-trial-signup-smoke-check.json").write_text("{}", encoding="utf-8")
            (root / "docs" / "smoke-checks" / "latest-trial-signup-smoke-check.md").write_text("# report\n", encoding="utf-8")
            (root / "docs" / "TRIAL_SIGNUP_E2E_REPORT_2026-04-01.md").write_text("report\n", encoding="utf-8")
            (root / "render.yaml").write_text("services:\n", encoding="utf-8")
            (root / "scripts" / "trial_signup_smoke_check.py").write_text("print('ok')\n", encoding="utf-8")
            (root / "test_trial_signup_smoke_check.py").write_text("pass\n", encoding="utf-8")

            with mock.patch.object(smoke, "ROOT", root), mock.patch.object(smoke, "DEFAULT_OWNER_READY_DIR", root / "docs" / "smoke-checks" / "owner-ready"), mock.patch.object(smoke, "DEFAULT_OWNER_READY_ARCHIVE_DIR", root / "docs" / "smoke-checks" / "owner-ready" / "archive"), mock.patch.object(smoke, "DEFAULT_ESCALATION_PACKET_DIR", root / "docs" / "smoke-checks" / "escalation-packet"), mock.patch.object(smoke, "DEFAULT_ESCALATION_PACKET_ARCHIVE_DIR", root / "docs" / "smoke-checks" / "escalation-packet" / "archive"):
                inventory = smoke.build_artifact_inventory()

        self.assertEqual(inventory["latest_json"]["path"], "docs/smoke-checks/latest-trial-signup-smoke-check.json")
        self.assertTrue(inventory["latest_json"]["exists"])
        self.assertGreater(inventory["latest_json"]["size_bytes"], 0)
        self.assertEqual(inventory["render_blueprint"]["path"], "render.yaml")
        self.assertEqual(
            inventory["recommended_attachments"],
            [
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
                "docs/smoke-checks/escalation-packet/escalation-packet.zip",
                "docs/smoke-checks/escalation-packet/escalation-packet.zip.sha256",
            ],
        )
        self.assertIn("render.yaml", inventory["render_support_packet_files"])
        self.assertIn("docs/smoke-checks/owner-ready/render_support.txt", inventory["render_support_packet_files"])
        self.assertIn("docs/smoke-checks/escalation-packet/render-support-message.txt", inventory["render_support_packet_files"])
        self.assertIn("docs/smoke-checks/escalation-packet/README.txt", inventory["render_support_packet_files"])
        self.assertIn("docs/smoke-checks/escalation-packet/escalation-packet.zip", inventory["render_support_packet_files"])
        self.assertIn("docs/smoke-checks/escalation-packet/escalation-packet.zip.sha256", inventory["render_support_packet_files"])
        self.assertTrue(inventory["escalation_packet_bundle"]["path"].endswith("docs/smoke-checks/escalation-packet/escalation-packet.zip"))
        self.assertTrue(inventory["escalation_packet_bundle_checksum"]["path"].endswith("docs/smoke-checks/escalation-packet/escalation-packet.zip.sha256"))
        self.assertIn("docs/smoke-checks/escalation-packet/evidence-manifest.json", inventory["traction_handoff_files"])
        self.assertIn("docs/smoke-checks/escalation-packet/escalation-packet.zip.sha256", inventory["traction_handoff_files"])
        self.assertEqual(inventory["owner_ready_archive"]["file_count"], 0)
        self.assertFalse(inventory["escalation_packet_dir"]["exists"])
        self.assertEqual(inventory["escalation_packet_archive"]["file_count"], 0)
        self.assertFalse(inventory["escalation_packet_archive"]["exists"])

    def test_build_owner_ready_messages_generates_forwardable_handoffs(self):
        report = {
            "generated_at": "2026-04-04T19:14:00+00:00",
        }
        render_support_packet = {
            "host_comparison": {
                "commission-tracker-app": {
                    "host": "commission-tracker-app.onrender.com",
                    "probe_path": "/",
                    "status": 200,
                    "attachment_state": "healthy-attached",
                },
                "commission-tracker-webhook": {
                    "host": "commission-tracker-webhook.onrender.com",
                    "probe_path": "/health",
                    "status": 404,
                    "attachment_state": "missing-backend-attachment",
                    "x_render_routing": "no-server",
                },
            }
        }
        owner_action_plan = {
            "traction": ["Forward the Render escalation message.", "Ask Render to redeploy the service."],
            "render_support": ["Confirm hostname attachment.", "Recheck /health until 200."],
            "verification_shell": ["Rerun the smoke check.", "Refresh the artifacts."],
        }

        messages = smoke.build_owner_ready_messages(
            report,
            render_support_packet,
            owner_action_plan,
            ["STRIPE_SECRET_KEY", "RESEND_API_KEY"],
        )

        self.assertIn("Traction handoff", messages["traction"])
        self.assertIn("commission-tracker-webhook.onrender.com/health is still HTTP 404", messages["traction"])
        self.assertIn("Render support request generated 2026-04-04T19:14:00+00:00", messages["render_support"])
        self.assertIn("x-render-routing=no-server", messages["render_support"])
        self.assertIn("Missing live E2E secrets: STRIPE_SECRET_KEY, RESEND_API_KEY.", messages["verification_shell"])
        self.assertIn("Next actions: Rerun the smoke check. Refresh the artifacts.", messages["verification_shell"])

    def test_build_incident_history_tracks_first_blocked_and_no_server_windows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            smoke_dir = root / "docs" / "smoke-checks"
            smoke_dir.mkdir(parents=True)

            (smoke_dir / "trial-signup-smoke-check-1.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2026-04-02T00:00:00+00:00",
                        "summary": {
                            "ready_for_live_e2e": False,
                            "public_webhook_ok": False,
                            "public_webhook_no_server": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (smoke_dir / "trial-signup-smoke-check-2.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2026-04-03T00:00:00+00:00",
                        "summary": {
                            "ready_for_live_e2e": False,
                            "public_webhook_ok": False,
                            "public_webhook_no_server": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (smoke_dir / "latest-trial-signup-smoke-check.json").write_text("{}", encoding="utf-8")

            current_report = {
                "generated_at": "2026-04-04T12:30:00+00:00",
                "summary": {
                    "ready_for_live_e2e": False,
                    "public_webhook_ok": False,
                    "public_webhook_no_server": True,
                },
            }

            with mock.patch.object(smoke, "ROOT", root):
                history = smoke.build_incident_history(current_report)

        self.assertEqual(history["artifact_count"], 3)
        self.assertEqual(history["blocked_artifact_count"], 3)
        self.assertEqual(history["first_blocked_at"], "2026-04-02T00:00:00+00:00")
        self.assertEqual(history["first_no_server_at"], "2026-04-02T00:00:00+00:00")
        self.assertEqual(history["current_state_started_at"], "2026-04-02T00:00:00+00:00")
        self.assertEqual(history["latest_status"], "blocked")
        self.assertEqual(history["blocked_duration"], "2d 12h 30m")
        self.assertEqual(history["current_state_duration"], "2d 12h 30m")

    def test_build_incident_history_resets_current_state_when_signature_changes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            smoke_dir = root / "docs" / "smoke-checks"
            smoke_dir.mkdir(parents=True)

            (smoke_dir / "trial-signup-smoke-check-1.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2026-04-02T00:00:00+00:00",
                        "summary": {
                            "ready_for_live_e2e": False,
                            "public_webhook_ok": False,
                            "public_webhook_no_server": False,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (smoke_dir / "trial-signup-smoke-check-2.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2026-04-03T12:00:00+00:00",
                        "summary": {
                            "ready_for_live_e2e": False,
                            "public_webhook_ok": False,
                            "public_webhook_no_server": True,
                        },
                    }
                ),
                encoding="utf-8",
            )

            current_report = {
                "generated_at": "2026-04-04T12:30:00+00:00",
                "summary": {
                    "ready_for_live_e2e": False,
                    "public_webhook_ok": False,
                    "public_webhook_no_server": True,
                },
            }

            with mock.patch.object(smoke, "ROOT", root):
                history = smoke.build_incident_history(current_report)

        self.assertEqual(history["first_blocked_at"], "2026-04-02T00:00:00+00:00")
        self.assertEqual(history["first_no_server_at"], "2026-04-03T12:00:00+00:00")
        self.assertEqual(history["current_state_started_at"], "2026-04-03T12:00:00+00:00")
        self.assertEqual(history["current_state_duration"], "1d 0h 30m")

    def test_build_change_summary_reports_no_previous_artifact(self):
        current_report = {"summary": {}}

        summary = smoke.build_change_summary(current_report, None)

        self.assertFalse(summary["has_previous_report"])
        self.assertFalse(summary["summary_changed"])
        self.assertEqual(summary["unchanged_blocked_streak"], 0)
        self.assertEqual(summary["changes"], ["No previous smoke-check artifact was available for comparison."])

    def test_build_change_summary_detects_status_and_probe_changes(self):
        previous_report = {
            "generated_at": "2026-04-03T23:16:00+00:00",
            "public_checks": {
                "app": {"status": 200},
                "webhook_health": {"status": 404},
            },
            "summary": {
                "ready_for_live_e2e": False,
                "public_webhook_no_server": True,
                "render_incident_signature": {
                    "repo_contract_ok": True,
                    "external_routing_issue": True,
                },
                "public_probe_matrix": [
                    {"path": "/health", "status": 404, "x_render_routing": "no-server", "x_render_origin_server": None}
                ],
                "change_summary": {
                    "unchanged_blocked_streak": 2,
                },
            },
        }
        current_report = {
            "public_checks": {
                "app": {"status": 200},
                "webhook_health": {"status": 200},
            },
            "summary": {
                "ready_for_live_e2e": True,
                "public_webhook_no_server": False,
                "render_incident_signature": {
                    "repo_contract_ok": True,
                    "external_routing_issue": False,
                },
                "public_probe_matrix": [
                    {"path": "/health", "status": 200, "x_render_routing": None, "x_render_origin_server": "gunicorn"}
                ],
            },
        }

        summary = smoke.build_change_summary(current_report, previous_report)

        self.assertTrue(summary["has_previous_report"])
        self.assertEqual(summary["previous_generated_at"], "2026-04-03T23:16:00+00:00")
        self.assertTrue(summary["summary_changed"])
        self.assertEqual(summary["unchanged_blocked_streak"], 0)
        self.assertTrue(any("public webhook health status changed from 404 to 200" in change for change in summary["changes"]))
        self.assertTrue(any("Probe /health status changed from 404 to 200" in change for change in summary["changes"]))
        self.assertTrue(any("Probe /health x-render-routing changed from no-server to None" in change for change in summary["changes"]))

    def test_build_change_summary_tracks_repeated_unchanged_blocked_runs(self):
        previous_report = {
            "generated_at": "2026-04-03T23:16:00+00:00",
            "public_checks": {
                "app": {"status": 200},
                "webhook_health": {"status": 404},
            },
            "summary": {
                "ready_for_live_e2e": False,
                "public_webhook_no_server": True,
                "render_incident_signature": {
                    "repo_contract_ok": True,
                    "external_routing_issue": True,
                },
                "public_probe_matrix": [
                    {"path": "/health", "status": 404, "x_render_routing": "no-server", "x_render_origin_server": None}
                ],
                "change_summary": {
                    "unchanged_blocked_streak": 3,
                },
            },
        }
        current_report = {
            "public_checks": {
                "app": {"status": 200},
                "webhook_health": {"status": 404},
            },
            "summary": {
                "ready_for_live_e2e": False,
                "public_webhook_no_server": True,
                "render_incident_signature": {
                    "repo_contract_ok": True,
                    "external_routing_issue": True,
                },
                "public_probe_matrix": [
                    {"path": "/health", "status": 404, "x_render_routing": "no-server", "x_render_origin_server": None}
                ],
            },
        }

        summary = smoke.build_change_summary(current_report, previous_report)

        self.assertTrue(summary["has_previous_report"])
        self.assertFalse(summary["summary_changed"])
        self.assertEqual(summary["unchanged_blocked_streak"], 4)
        self.assertEqual(summary["changes"], ["No material change detected versus the previous smoke-check artifact."])

    def test_generate_report_populates_summary_before_change_summary_comparison(self):
        previous_report = {
            "generated_at": "2026-04-04T23:16:28.644845+00:00",
            "public_checks": {
                "app": {"status": 200},
                "webhook_health": {"status": 404},
            },
            "summary": {
                "ready_for_live_e2e": False,
                "public_webhook_no_server": True,
                "render_incident_signature": {
                    "repo_contract_ok": True,
                    "external_routing_issue": True,
                },
                "public_probe_matrix": [
                    {"path": "/", "status": 404, "x_render_routing": "no-server", "x_render_origin_server": None},
                    {"path": "/health", "status": 404, "x_render_routing": "no-server", "x_render_origin_server": None},
                    {"path": "/stripe-webhook", "status": 404, "x_render_routing": "no-server", "x_render_origin_server": None},
                    {"path": "/test", "status": 404, "x_render_routing": "no-server", "x_render_origin_server": None},
                ],
                "change_summary": {
                    "unchanged_blocked_streak": 5,
                },
            },
        }

        with mock.patch.object(smoke, "fetch_url", side_effect=[
            {"ok": True, "status": 200, "reason": "OK", "body_preview": "app", "headers": {}},
            {"ok": False, "status": 404, "reason": "Not Found", "body_preview": "missing", "headers": {"x-render-routing": "no-server"}},
            {"ok": False, "status": 404, "reason": "Not Found", "body_preview": "missing", "headers": {"x-render-routing": "no-server"}},
            {"ok": False, "status": 404, "reason": "Not Found", "body_preview": "missing", "headers": {"x-render-routing": "no-server"}},
            {"ok": False, "status": 404, "reason": "Not Found", "body_preview": "missing", "headers": {"x-render-routing": "no-server"}},
            {"ok": False, "status": 404, "reason": "Not Found", "body_preview": "missing", "headers": {"x-render-routing": "no-server"}},
        ]), mock.patch.object(smoke, "check_local_webhook_route", return_value={"ok": False, "status": None, "payload": "deps missing", "dependency_check": {"ok": False, "missing_modules": ["flask"]}}), mock.patch.object(smoke, "check_checkout_contract", return_value={"ok": True, "status": 200, "payload": {}}), mock.patch.object(smoke, "check_render_blueprint", return_value={"ok": True, "status": 200, "payload": "ok", "services": {}}), mock.patch.object(smoke, "check_webhook_service_contract", return_value={"ok": True, "status": 200, "payload": "ok", "routes": {}, "requirements": {}, "missing_packages": []}), mock.patch.object(smoke, "inspect_env_var", return_value={"present": False, "length": 0}), mock.patch.object(smoke, "build_artifact_inventory", return_value={}), mock.patch.object(smoke, "build_incident_history", return_value={"artifact_count": 1, "blocked_artifact_count": 1}):
            report = smoke.generate_report(previous_report=previous_report)

        change_summary = report["summary"]["change_summary"]
        self.assertTrue(change_summary["has_previous_report"])
        self.assertFalse(change_summary["summary_changed"])
        self.assertEqual(change_summary["changes"], ["No material change detected versus the previous smoke-check artifact."])
        self.assertEqual(change_summary["unchanged_blocked_streak"], 6)
        self.assertFalse(report["summary"]["ready_for_live_e2e"])

    def test_build_public_probe_matrix_rolls_up_each_webhook_probe(self):
        report = {
            "webhook_base_url": "https://commission-tracker-webhook.onrender.com",
            "public_checks": {
                "webhook_diagnostics": {
                    "probed_endpoints": {
                        "https://commission-tracker-webhook.onrender.com/": {
                            "ok": False,
                            "status": 404,
                            "reason": "Not Found",
                            "body_preview": "missing root",
                            "headers": {
                                "x-render-routing": "no-server",
                                "server": "cloudflare",
                                "content-type": "text/plain",
                            },
                        },
                        "https://commission-tracker-webhook.onrender.com/health": {
                            "ok": False,
                            "status": 404,
                            "reason": "Not Found",
                            "body_preview": "missing health",
                            "headers": {
                                "x-render-routing": "no-server",
                                "server": "cloudflare",
                                "content-type": "text/plain",
                            },
                        },
                    }
                }
            },
        }

        matrix = smoke.build_public_probe_matrix(report)

        self.assertEqual(matrix[0]["path"], "/")
        self.assertEqual(matrix[1]["path"], "/health")
        self.assertEqual(matrix[1]["x_render_routing"], "no-server")
        self.assertEqual(matrix[1]["server"], "cloudflare")
        self.assertEqual(matrix[1]["body_preview"], "missing health")

    def test_build_public_probe_commands_lists_app_then_each_webhook_probe(self):
        report = {
            "app_url": "https://commission-tracker-app.onrender.com",
            "webhook_base_url": "https://commission-tracker-webhook.onrender.com",
            "public_checks": {
                "webhook_diagnostics": {
                    "probed_endpoints": {
                        "https://commission-tracker-webhook.onrender.com/health": {
                            "ok": False,
                            "status": 404,
                            "reason": "Not Found",
                            "body_preview": "missing health",
                            "headers": {},
                        },
                        "https://commission-tracker-webhook.onrender.com/": {
                            "ok": False,
                            "status": 404,
                            "reason": "Not Found",
                            "body_preview": "missing root",
                            "headers": {},
                        },
                    }
                }
            },
        }

        commands = smoke.build_public_probe_commands(report)

        self.assertEqual(commands[0], "curl -i https://commission-tracker-app.onrender.com")
        self.assertEqual(commands[1], "curl -i https://commission-tracker-webhook.onrender.com/")
        self.assertEqual(commands[2], "curl -i https://commission-tracker-webhook.onrender.com/health")

    def test_build_render_incident_signature_isolates_external_routing_issue(self):
        report = {
            "local_checks": {
                "render_blueprint": {"ok": True},
                "webhook_service_contract": {"ok": True},
                "checkout_contract": {"ok": True},
            }
        }
        hostname_diagnostics = {
            "commission-tracker-app": {"attachment_state": "healthy-attached"},
            "commission-tracker-webhook": {"attachment_state": "missing-backend-attachment"},
        }

        details = smoke.build_render_incident_signature(report, hostname_diagnostics)

        self.assertTrue(details["repo_contract_ok"])
        self.assertTrue(details["external_routing_issue"])
        self.assertEqual(details["app_host_attachment_state"], "healthy-attached")
        self.assertEqual(details["webhook_host_attachment_state"], "missing-backend-attachment")
        self.assertIn("external Render service or domain binding problem", details["conclusion"])

    def test_build_escalation_recommendation_marks_repeated_external_outage_high_or_critical(self):
        report = {
            "local_checks": {
                "webhook_health_route": {"ok": False},
            },
            "summary": {
                "missing_required_env_vars": ["STRIPE_SECRET_KEY", "RESEND_API_KEY"],
            },
        }
        incident_signature = {
            "external_routing_issue": True,
        }
        change_summary = {
            "unchanged_blocked_streak": 3,
        }

        recommendation = smoke.build_escalation_recommendation(
            report,
            incident_signature,
            change_summary,
            ["STRIPE_SECRET_KEY", "RESEND_API_KEY"],
        )

        self.assertEqual(recommendation["severity"], "critical")
        self.assertEqual(recommendation["owner"], "Traction")
        self.assertEqual(recommendation["destination"], "Render support")
        self.assertEqual(recommendation["unchanged_blocked_streak"], 3)
        self.assertIn("Escalate immediately", recommendation["urgency"])
        self.assertIn("STRIPE_SECRET_KEY", recommendation["prerequisite"])
        self.assertIn("Traction should escalate to Render support", recommendation["recommended_message"])

    def test_build_escalation_recommendation_prefers_local_fix_when_not_externally_isolated(self):
        report = {
            "local_checks": {
                "webhook_health_route": {"ok": False},
            },
            "summary": {
                "missing_required_env_vars": [],
            },
        }
        incident_signature = {
            "external_routing_issue": False,
        }
        change_summary = {
            "unchanged_blocked_streak": 0,
        }

        recommendation = smoke.build_escalation_recommendation(
            report,
            incident_signature,
            change_summary,
            [],
        )

        self.assertEqual(recommendation["severity"], "medium")
        self.assertEqual(recommendation["owner"], "Forge")
        self.assertEqual(recommendation["destination"], "local verification shell")
        self.assertIn("Fix the local webhook verification environment", recommendation["urgency"])

    def test_build_render_support_packet_captures_host_asymmetry_and_probe_headers(self):
        report = {
            "generated_at": "2026-04-03T17:14:00+00:00",
            "public_checks": {
                "app": {
                    "status": 200,
                    "reason": "OK",
                    "headers": {
                        "x-render-origin-server": "TornadoServer/6.5.5",
                        "cf-ray": "app-ray",
                        "date": "Fri, 03 Apr 2026 17:14:00 GMT",
                    },
                },
                "webhook_health": {
                    "status": 404,
                    "reason": "Not Found",
                    "headers": {
                        "x-render-routing": "no-server",
                        "cf-ray": "webhook-ray",
                        "date": "Fri, 03 Apr 2026 17:14:01 GMT",
                    },
                },
            },
        }
        hostname_diagnostics = {
            "commission-tracker-app": {
                "host": "commission-tracker-app.onrender.com",
                "probe_path": "/",
                "attachment_state": "healthy-attached",
            },
            "commission-tracker-webhook": {
                "host": "commission-tracker-webhook.onrender.com",
                "probe_path": "/health",
                "attachment_state": "missing-backend-attachment",
            },
        }
        incident_signature = {
            "conclusion": "External Render service or domain binding problem.",
            "repo_contract_ok": True,
            "external_routing_issue": True,
        }

        packet = smoke.build_render_support_packet(report, hostname_diagnostics, incident_signature)

        self.assertEqual(packet["incident_type"], "render-webhook-routing-outage")
        self.assertTrue(packet["repo_contract_ok"])
        self.assertTrue(packet["external_routing_issue"])
        self.assertEqual(packet["host_comparison"]["commission-tracker-app"]["x_render_origin_server"], "TornadoServer/6.5.5")
        self.assertEqual(packet["host_comparison"]["commission-tracker-app"]["cf_ray"], "app-ray")
        self.assertEqual(packet["host_comparison"]["commission-tracker-webhook"]["x_render_routing"], "no-server")
        self.assertEqual(packet["host_comparison"]["commission-tracker-webhook"]["cf_ray"], "webhook-ray")
        self.assertIn("Confirm the webhook hostname is attached", packet["requested_action"])

    def test_build_render_escalation_message_rolls_up_support_packet_and_playbook(self):
        report = {
            "generated_at": "2026-04-03T17:14:00+00:00",
        }
        support_packet = {
            "conclusion": "External Render service or domain binding problem.",
            "requested_action": "Confirm the webhook hostname is attached to commission-tracker-webhook.",
            "host_comparison": {
                "commission-tracker-app": {
                    "host": "commission-tracker-app.onrender.com",
                    "probe_path": "/",
                    "status": 200,
                    "reason": "OK",
                    "attachment_state": "healthy-attached",
                    "x_render_origin_server": "TornadoServer/6.5.5",
                },
                "commission-tracker-webhook": {
                    "host": "commission-tracker-webhook.onrender.com",
                    "probe_path": "/health",
                    "status": 404,
                    "reason": "Not Found",
                    "attachment_state": "missing-backend-attachment",
                    "x_render_routing": "no-server",
                },
            },
        }
        playbook = [
            "1. Open commission-tracker-webhook in Render.",
            "2. Reattach the webhook hostname and redeploy.",
        ]

        message = smoke.build_render_escalation_message(report, support_packet, playbook)

        self.assertIn("Render support request for AMS-APP webhook routing outage.", message)
        self.assertIn("Generated at 2026-04-03T17:14:00+00:00.", message)
        self.assertIn("commission-tracker-app.onrender.com/ -> HTTP 200 OK", message)
        self.assertIn("commission-tracker-webhook.onrender.com/health -> HTTP 404 Not Found", message)
        self.assertIn("x-render-routing=no-server", message)
        self.assertIn("Requested action: Confirm the webhook hostname is attached to commission-tracker-webhook.", message)
        self.assertIn("- 1. Open commission-tracker-webhook in Render.", message)

    def test_build_render_escalation_payload_rolls_up_ticket_ready_fields(self):
        report = {
            "generated_at": "2026-04-04T09:14:45+00:00",
            "summary": {
                "missing_required_env_vars": ["STRIPE_SECRET_KEY", "RESEND_API_KEY"],
            },
        }
        support_packet = {
            "incident_type": "render-webhook-routing-outage",
            "requested_action": "Confirm the webhook hostname is attached to commission-tracker-webhook.",
            "host_comparison": {
                "commission-tracker-app": {
                    "host": "commission-tracker-app.onrender.com",
                    "probe_path": "/",
                    "status": 200,
                    "reason": "OK",
                    "attachment_state": "healthy-attached",
                    "x_render_origin_server": "TornadoServer/6.5.5",
                },
                "commission-tracker-webhook": {
                    "host": "commission-tracker-webhook.onrender.com",
                    "probe_path": "/health",
                    "status": 404,
                    "reason": "Not Found",
                    "attachment_state": "missing-backend-attachment",
                    "x_render_routing": "no-server",
                },
            },
        }
        incident_signature = {
            "repo_contract_ok": True,
            "external_routing_issue": True,
        }
        change_summary = {
            "unchanged_blocked_streak": 4,
        }
        escalation_recommendation = {
            "severity": "critical",
            "owner": "Traction",
            "destination": "Render support",
            "recommended_message": "Traction should escalate to Render support immediately.",
        }

        payload = smoke.build_render_escalation_payload(
            report,
            support_packet,
            incident_signature,
            change_summary,
            escalation_recommendation,
            ["STRIPE_SECRET_KEY", "RESEND_API_KEY"],
        )

        self.assertEqual(payload["ticket_title"], "AMS-APP Render webhook routing outage blocks live Stripe signup path")
        self.assertEqual(payload["severity"], "critical")
        self.assertEqual(payload["owner"], "Traction")
        self.assertEqual(payload["destination"], "Render support")
        self.assertEqual(payload["unchanged_blocked_streak"], 4)
        self.assertTrue(payload["repo_contract_ok"])
        self.assertTrue(payload["external_routing_issue"])
        self.assertIn("commission-tracker-app.onrender.com/ -> HTTP 200 OK", payload["app_host_evidence"])
        self.assertIn("commission-tracker-webhook.onrender.com/health -> HTTP 404 Not Found", payload["webhook_host_evidence"])
        self.assertEqual(payload["missing_live_e2e_secrets"], ["STRIPE_SECRET_KEY", "RESEND_API_KEY"])
        self.assertEqual(payload["recommended_message"], "Traction should escalate to Render support immediately.")

    def test_build_owner_action_plan_splits_next_steps_by_owner(self):
        report = {
            "app_url": "https://commission-tracker-app.onrender.com",
            "webhook_base_url": "https://commission-tracker-webhook.onrender.com",
        }
        support_packet = {
            "host_comparison": {
                "commission-tracker-app": {
                    "host": "commission-tracker-app.onrender.com",
                    "probe_path": "/",
                },
                "commission-tracker-webhook": {
                    "host": "commission-tracker-webhook.onrender.com",
                    "probe_path": "/health",
                },
            }
        }
        render_service_env_gap = {
            "commission-tracker-app": {
                "missing_in_shell": ["RESEND_API_KEY"],
            },
            "commission-tracker-webhook": {
                "missing_in_shell": ["STRIPE_WEBHOOK_SECRET", "SMTP_HOST"],
            },
        }

        plan = smoke.build_owner_action_plan(
            report,
            support_packet,
            render_service_env_gap,
            ["STRIPE_SECRET_KEY", "RESEND_API_KEY"],
        )

        self.assertIn("Forward the Render escalation message", plan["traction"][0])
        self.assertTrue(any("commission-tracker-webhook.onrender.com/health" in step for step in plan["traction"]))
        self.assertTrue(any("STRIPE_WEBHOOK_SECRET" in step for step in plan["traction"]))
        self.assertTrue(any("x-render-routing=no-server" in step for step in plan["render_support"]))
        self.assertTrue(any("python3 scripts/trial_signup_smoke_check.py" in step for step in plan["verification_shell"]))
        self.assertTrue(any("ready_for_live_e2e flips to true" in step for step in plan["verification_shell"]))

    def test_build_render_recovery_playbook_prioritizes_webhook_attachment_when_incident_is_isolated(self):
        report = {
            "app_url": "https://commission-tracker-app.onrender.com",
            "webhook_base_url": "https://commission-tracker-webhook.onrender.com",
        }
        incident_signature = {
            "external_routing_issue": True,
        }
        render_service_env_gap = {
            "commission-tracker-webhook": {
                "missing_in_shell": ["STRIPE_WEBHOOK_SECRET", "SMTP_HOST"],
            }
        }

        playbook = smoke.build_render_recovery_playbook(
            report,
            incident_signature,
            render_service_env_gap,
            ["STRIPE_SECRET_KEY", "RESEND_API_KEY"],
        )

        self.assertIn("commission-tracker-webhook first", playbook[0])
        self.assertIn("commission-tracker-webhook.onrender.com", playbook[1])
        self.assertTrue(any("STRIPE_WEBHOOK_SECRET" in step for step in playbook))
        self.assertTrue(any("STRIPE_SECRET_KEY, RESEND_API_KEY" in step for step in playbook))
        self.assertTrue(playbook[-1].endswith("ready_for_live_e2e flips to true."))

    def test_build_render_recovery_playbook_falls_back_to_dual_service_review_when_not_isolated(self):
        report = {
            "app_url": "https://commission-tracker-app.onrender.com",
            "webhook_base_url": "https://commission-tracker-webhook.onrender.com",
        }
        incident_signature = {
            "external_routing_issue": False,
        }

        playbook = smoke.build_render_recovery_playbook(
            report,
            incident_signature,
            {"commission-tracker-webhook": {"missing_in_shell": []}},
            [],
        )

        self.assertIn("Review both Render services together", playbook[0])
        self.assertIn("Probe both public hostnames after deploy", playbook[2])
        self.assertTrue(playbook[-1].endswith("ready_for_live_e2e flips to true."))

    def test_build_executive_summary_lines_rolls_up_status_headers_and_escalation(self):
        report = {
            "public_checks": {
                "app": {
                    "status": 200,
                    "reason": "OK",
                    "headers": {"x-render-origin-server": "TornadoServer/6.5.5"},
                },
                "webhook_health": {
                    "status": 404,
                    "reason": "Not Found",
                    "headers": {"x-render-routing": "no-server"},
                },
            },
            "summary": {
                "ready_for_live_e2e": False,
            },
        }
        incident_signature = {
            "app_host_attachment_state": "healthy-attached",
            "webhook_host_attachment_state": "missing-backend-attachment",
            "conclusion": "External Render service or domain binding problem.",
        }
        escalation_recommendation = {
            "severity": "critical",
            "owner": "Traction",
            "destination": "Render support",
            "recommended_message": "Traction should escalate to Render support immediately.",
        }
        change_summary = {
            "unchanged_blocked_streak": 4,
        }

        lines = smoke.build_executive_summary_lines(
            report,
            incident_signature,
            escalation_recommendation,
            change_summary,
            ["STRIPE_SECRET_KEY", "RESEND_API_KEY"],
            False,
        )

        self.assertIn("still blocked", lines[0])
        self.assertIn("HTTP 200 OK", lines[0])
        self.assertIn("HTTP 404 Not Found", lines[0])
        self.assertIn("x-render-origin-server=TornadoServer/6.5.5", lines[1])
        self.assertIn("x-render-routing=no-server", lines[1])
        self.assertEqual(lines[2], "External Render service or domain binding problem.")
        self.assertIn("STRIPE_SECRET_KEY, RESEND_API_KEY", lines[3])
        self.assertIn("severity=critical owner=Traction destination=Render support unchanged_blocked_streak=4", lines[4])
        self.assertEqual(lines[5], "Traction should escalate to Render support immediately.")

    def test_build_recovery_exit_criteria_lists_resolution_gate_for_external_render_outage(self):
        report = {
            "app_url": "https://commission-tracker-app.onrender.com",
            "webhook_base_url": "https://commission-tracker-webhook.onrender.com",
        }
        incident_signature = {
            "external_routing_issue": True,
        }

        criteria = smoke.build_recovery_exit_criteria(
            report,
            incident_signature,
            ["STRIPE_SECRET_KEY", "RESEND_API_KEY"],
        )

        self.assertIn("commission-tracker-app.onrender.com/ returns HTTP 200", criteria[0])
        self.assertTrue(any("commission-tracker-webhook.onrender.com/health returns HTTP 200 without x-render-routing=no-server" in step for step in criteria))
        self.assertTrue(any("attached to commission-tracker-webhook in Render" in step for step in criteria))
        self.assertTrue(any("STRIPE_SECRET_KEY, RESEND_API_KEY" in step for step in criteria))
        self.assertTrue(criteria[-1].startswith("One real Stripe test-mode signup completes"))

    def test_check_render_blueprint_reports_expected_services(self):
        render_yaml = """
services:
  - type: web
    name: commission-tracker-app
    runtime: python
    plan: starter
    autoDeploy: true
    buildCommand: pip install -r requirements.txt
    startCommand: streamlit run commission_app.py --server.port ${PORT} --server.address 0.0.0.0
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
    plan: starter
    autoDeploy: true
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn webhook_server:app --bind 0.0.0.0:${PORT}
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
        self.assertTrue(details["services"]["commission-tracker-app"]["runtime_ok"])
        self.assertTrue(details["services"]["commission-tracker-app"]["plan_ok"])
        self.assertTrue(details["services"]["commission-tracker-app"]["auto_deploy_ok"])
        self.assertTrue(details["services"]["commission-tracker-app"]["build_command_ok"])
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
    runtime: node
    plan: free
    autoDeploy: false
    buildCommand: npm install
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
        self.assertIn("runtime mismatch", details["payload"])
        self.assertIn("plan mismatch", details["payload"])
        self.assertIn("autoDeploy mismatch", details["payload"])
        self.assertIn("buildCommand mismatch", details["payload"])
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
                "services": {
                    "commission-tracker-app": {
                        "runtime_ok": True,
                        "plan_ok": True,
                        "auto_deploy_ok": True,
                        "build_command_ok": True,
                        "start_command_ok": True,
                        "health_check_path_ok": True,
                    },
                    "commission-tracker-webhook": {
                        "runtime_ok": True,
                        "plan_ok": True,
                        "auto_deploy_ok": True,
                        "build_command_ok": True,
                        "start_command_ok": True,
                        "health_check_path_ok": True,
                    },
                },
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
        ), mock.patch.object(
            smoke,
            "build_repo_context",
            return_value={
                "branch": "main",
                "head": "abc123def456",
                "short_head": "abc123d",
                "head_subject": "feat: sample commit",
                "head_committed_at": "2026-04-05T18:00:00+00:00",
                "remote_origin": "https://github.com/pstabell/AMS-APP.git",
                "dirty": False,
                "tracked_changes": [],
                "status": "clean",
                "available": True,
            },
        ):
            return smoke.generate_report()

    def test_summarize_render_blueprint_services_reports_full_contract_status(self):
        summary = smoke.summarize_render_blueprint_services(
            {
                "commission-tracker-app": {
                    "runtime_ok": True,
                    "plan_ok": True,
                    "auto_deploy_ok": True,
                    "build_command_ok": True,
                    "start_command_ok": True,
                    "health_check_path_ok": False,
                }
            }
        )

        self.assertIn("commission-tracker-app: runtime=OK", summary)
        self.assertIn("plan=OK", summary)
        self.assertIn("autoDeploy=OK", summary)
        self.assertIn("buildCommand=OK", summary)
        self.assertIn("startCommand=OK", summary)
        self.assertIn("healthCheckPath=FAIL", summary)

    def test_render_markdown_report_includes_readiness_summary(self):
        report = self._build_ready_report()

        markdown = smoke.render_markdown_report(report)

        self.assertIn("# Trial Signup Smoke Check Snapshot", markdown)
        self.assertIn("Ready for live e2e: YES", markdown)
        self.assertIn("## Executive summary", markdown)
        self.assertIn("- AMS-APP trial signup stack is ready for live E2E.", markdown)
        self.assertIn("- Escalation: severity=low owner=Forge destination=working session unchanged_blocked_streak=0.", markdown)
        self.assertIn("Webhook no-server detected: NO", markdown)
        self.assertIn("Any webhook endpoint OK: YES", markdown)
        self.assertIn("Checkout contract OK: YES", markdown)
        self.assertIn("Render blueprint OK: YES", markdown)
        self.assertIn("Render blueprint service contract summary:", markdown)
        self.assertIn("runtime=", markdown)
        self.assertIn("buildCommand=", markdown)
        self.assertIn("Webhook service contract OK: YES", markdown)
        self.assertIn("## Repo context", markdown)
        self.assertIn("- Git status: clean", markdown)
        self.assertIn("- Branch: main", markdown)
        self.assertIn("- HEAD: abc123d", markdown)
        self.assertIn("## Blocking reasons", markdown)
        self.assertIn("## Recommended next actions", markdown)
        self.assertIn("## Render restore checklist", markdown)
        self.assertIn("## Render restore validation commands", markdown)
        self.assertIn("## Local webhook dependency commands", markdown)
        self.assertIn("## Render service env gap", markdown)
        self.assertIn("## Render service contract commands", markdown)
        self.assertIn("## Render domain attachment commands", markdown)
        self.assertIn("## Render hostname diagnostics", markdown)
        self.assertIn("## Public webhook probe matrix", markdown)
        self.assertIn("## Public probe commands", markdown)
        self.assertIn("## Change summary versus previous smoke check", markdown)
        self.assertIn("- Unchanged blocked streak: 0", markdown)
        self.assertIn("## Render incident signature", markdown)
        self.assertIn("## Render support packet", markdown)
        self.assertIn("## Escalation recommendation", markdown)
        self.assertIn("## Artifact refresh commands", markdown)
        self.assertIn("- both: python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md", markdown)
        self.assertIn("## Packet verification commands", markdown)
        self.assertIn("sha256sum -c docs/smoke-checks/escalation-packet/escalation-packet.zip.sha256", markdown)
        self.assertIn("unzip -l docs/smoke-checks/escalation-packet/escalation-packet.zip", markdown)
        self.assertIn("## Artifact inventory", markdown)
        self.assertIn("- recommended_attachments: docs/smoke-checks/latest-trial-signup-smoke-check.json, docs/smoke-checks/latest-trial-signup-smoke-check.md, docs/TRIAL_SIGNUP_E2E_REPORT_2026-04-01.md, render.yaml, docs/smoke-checks/owner-ready/traction.txt, docs/smoke-checks/owner-ready/render_support.txt", markdown)
        self.assertIn("## Escalation packet hashes", markdown)
        self.assertIn("## Owner action plan", markdown)
        self.assertIn("## Render recovery playbook", markdown)
        self.assertIn("## Recovery exit criteria", markdown)
        self.assertIn("## Render escalation message", markdown)
        self.assertIn("## Render escalation payload", markdown)
        self.assertIn("Render support request for AMS-APP webhook routing outage.", markdown)
        self.assertIn("- Severity:", markdown)
        self.assertIn("- Recommended message:", markdown)
        self.assertIn("- traction:", markdown)
        self.assertIn("- render_support:", markdown)
        self.assertIn("- verification_shell:", markdown)
        self.assertIn("External routing issue isolated: NO", markdown)
        self.assertIn("Open the Render dashboard for service commission-tracker-webhook.", markdown)
        self.assertIn("curl -i https://commission-tracker-webhook.onrender.com/health", markdown)
        self.assertIn("Run one real Stripe test-mode signup", markdown)
        self.assertIn("Render dashboard -> commission-tracker-webhook -> Build & Deploy: confirm startCommand='gunicorn webhook_server:app --bind 0.0.0.0:${PORT}'", markdown)
        self.assertIn("Render dashboard -> commission-tracker-webhook -> Settings -> Custom Domains: confirm commission-tracker-webhook.onrender.com is attached to this service.", markdown)
        self.assertIn("Incident type: render-webhook-routing-outage", markdown)
        self.assertIn("attachment_state=healthy-attached", markdown)
        self.assertIn("path=/health; status=200 OK; ok=YES", markdown)
        self.assertIn("- curl -i https://commission-tracker-app.onrender.com", markdown)
        self.assertIn("- curl -i https://commission-tracker-webhook.onrender.com/health", markdown)
        self.assertIn("- commission-tracker-webhook: shell_ready=YES; missing_in_shell=None; missing_in_blueprint=None", markdown)
        self.assertIn("- None", markdown)

    def test_load_previous_report_prefers_json_out_when_available(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            json_out = temp_path / "explicit.json"
            default_json = temp_path / "latest.json"
            json_out.write_text(json.dumps({"generated_at": "2026-04-04T10:00:00+00:00", "summary": {"source": "explicit"}}), encoding="utf-8")
            default_json.write_text(json.dumps({"generated_at": "2026-04-04T09:00:00+00:00", "summary": {"source": "default"}}), encoding="utf-8")

            with mock.patch.object(smoke, "DEFAULT_JSON_ARTIFACT", default_json):
                report = smoke.load_previous_report(str(json_out))

        self.assertEqual(report["summary"]["source"], "explicit")

    def test_load_previous_report_falls_back_to_default_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            default_json = temp_path / "latest.json"
            default_json.write_text(json.dumps({"generated_at": "2026-04-04T09:00:00+00:00", "summary": {"source": "default"}}), encoding="utf-8")

            with mock.patch.object(smoke, "DEFAULT_JSON_ARTIFACT", default_json):
                report = smoke.load_previous_report()

        self.assertEqual(report["summary"]["source"], "default")

    def test_load_previous_report_skips_invalid_json_and_uses_next_candidate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            json_out = temp_path / "explicit.json"
            default_json = temp_path / "latest.json"
            json_out.write_text("{not-json", encoding="utf-8")
            default_json.write_text(json.dumps({"generated_at": "2026-04-04T09:00:00+00:00", "summary": {"source": "default"}}), encoding="utf-8")

            with mock.patch.object(smoke, "DEFAULT_JSON_ARTIFACT", default_json):
                report = smoke.load_previous_report(str(json_out))

        self.assertEqual(report["summary"]["source"], "default")

    def test_main_returns_zero_when_stack_is_ready(self):
        report = self._build_ready_report()

        with mock.patch.object(smoke, "generate_report", return_value=report), mock.patch.object(smoke, "load_previous_report", return_value=None), mock.patch("sys.stdout") as stdout:
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
        self.assertIn(
            "Render dashboard -> commission-tracker-webhook -> Settings -> Custom Domains: confirm commission-tracker-webhook.onrender.com is attached to this service.",
            payload["summary"]["render_domain_attachment_commands"]["commission-tracker-webhook"],
        )
        self.assertEqual(payload["summary"]["public_probe_commands"][0], "curl -i https://commission-tracker-app.onrender.com")
        self.assertIn("curl -i https://commission-tracker-webhook.onrender.com/health", payload["summary"]["public_probe_commands"])
        self.assertEqual(payload["summary"]["render_hostname_diagnostics"]["commission-tracker-app"]["attachment_state"], "healthy-attached")
        self.assertEqual(payload["summary"]["render_support_packet"]["incident_type"], "render-webhook-routing-outage")
        self.assertEqual(payload["summary"]["escalation_recommendation"]["severity"], "low")
        self.assertEqual(payload["summary"]["escalation_recommendation"]["owner"], "Forge")
        self.assertEqual(
            payload["summary"]["artifact_refresh_commands"]["both"],
            "python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md",
        )
        self.assertEqual(
            payload["summary"]["packet_verification_commands"]["latest_bundle"][0],
            "cd . && sha256sum -c docs/smoke-checks/escalation-packet/escalation-packet.zip.sha256",
        )
        self.assertTrue(
            payload["summary"]["packet_verification_commands"]["archived_bundle"][2].endswith('unzip -l "$latest_bundle"')
        )
        self.assertIn("traction", payload["summary"]["owner_action_plan"])
        self.assertIn("render_support", payload["summary"]["owner_action_plan"])
        self.assertIn("verification_shell", payload["summary"]["owner_action_plan"])
        self.assertIn("Render support request for AMS-APP webhook routing outage.", payload["summary"]["render_escalation_message"])
        self.assertTrue(any("ready_for_live_e2e=true" in step or "ready_for_live_e2e flips to true" in step or "ready_for_live_e2e=true." in step for step in payload["summary"]["recovery_exit_criteria"]))
        self.assertEqual(
            payload["summary"]["render_escalation_payload"]["ticket_title"],
            "AMS-APP Render webhook routing outage blocks live Stripe signup path",
        )
        self.assertTrue(payload["summary"]["render_incident_signature"]["repo_contract_ok"])
        self.assertFalse(payload["summary"]["render_incident_signature"]["external_routing_issue"])
        self.assertIn("Review both Render services together", payload["summary"]["render_recovery_playbook"][0])

    def test_write_owner_ready_messages_writes_copy_ready_text_files(self):
        report = self._build_ready_report()

        with tempfile.TemporaryDirectory() as temp_dir:
            written_paths = smoke.write_owner_ready_messages(report, temp_dir)
            written_names = sorted(path.name for path in written_paths)

            self.assertEqual(
                written_names,
                ["render_support.txt", "traction.txt", "verification_shell.txt"],
            )
            self.assertIn(
                "Traction handoff",
                (pathlib.Path(temp_dir) / "traction.txt").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "Render support request",
                (pathlib.Path(temp_dir) / "render_support.txt").read_text(encoding="utf-8"),
            )

    def test_build_owner_ready_archive_file_paths_uses_generated_at_slug(self):
        report = self._build_ready_report()
        report["generated_at"] = "2026-04-05T05:14:58.289624+00:00"

        archive_paths = smoke.build_owner_ready_archive_file_paths(report, "docs/smoke-checks/owner-ready/archive")

        self.assertEqual(
            archive_paths["traction"].as_posix(),
            "docs/smoke-checks/owner-ready/archive/2026-04-05T05-14-58-289624-00-00-traction.txt",
        )
        self.assertTrue(all(path.name.endswith('.txt') for path in archive_paths.values()))

    def test_write_owner_ready_archive_writes_timestamped_snapshots(self):
        report = self._build_ready_report()
        report["generated_at"] = "2026-04-05T05:14:58.289624+00:00"

        with tempfile.TemporaryDirectory() as temp_dir:
            written_paths = smoke.write_owner_ready_archive(report, temp_dir)
            written_names = sorted(path.name for path in written_paths)

            self.assertEqual(
                written_names,
                [
                    "2026-04-05T05-14-58-289624-00-00-render_support.txt",
                    "2026-04-05T05-14-58-289624-00-00-traction.txt",
                    "2026-04-05T05-14-58-289624-00-00-verification_shell.txt",
                ],
            )
            self.assertIn(
                "Traction handoff",
                (pathlib.Path(temp_dir) / "2026-04-05T05-14-58-289624-00-00-traction.txt").read_text(encoding="utf-8"),
            )

    def test_build_escalation_packet_hashes_captures_packet_and_artifact_digests(self):
        report = self._build_ready_report()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            latest_json = root / "docs" / "smoke-checks" / "latest-trial-signup-smoke-check.json"
            latest_markdown = root / "docs" / "smoke-checks" / "latest-trial-signup-smoke-check.md"
            latest_json.parent.mkdir(parents=True)
            latest_json.write_text('{"ok": true}\n', encoding="utf-8")
            latest_markdown.write_text('# snapshot\n', encoding="utf-8")
            report["summary"]["artifact_inventory"] = {
                "latest_json": {"path": "docs/smoke-checks/latest-trial-signup-smoke-check.json"},
                "latest_markdown": {"path": "docs/smoke-checks/latest-trial-signup-smoke-check.md"},
            }

            with mock.patch.object(smoke, "ROOT", root):
                hashes = smoke.build_escalation_packet_hashes(
                    report,
                    {"render-support-message.txt": "hello\n", "render-support-payload.json": '{"a":1}\n'},
                )

        self.assertIn("render-support-message.txt", hashes)
        self.assertEqual(hashes["render-support-message.txt"]["size_bytes"], len("hello\n".encode("utf-8")))
        self.assertEqual(hashes["latest-trial-signup-smoke-check.json"]["path"], "docs/smoke-checks/latest-trial-signup-smoke-check.json")
        self.assertEqual(len(hashes["latest-trial-signup-smoke-check.json"]["sha256"]), 64)

    def test_build_escalation_packet_readme_summarizes_packet_contents(self):
        report = self._build_ready_report()
        report["generated_at"] = "2026-04-05T05:14:58.289624+00:00"
        report["summary"]["artifact_inventory"] = {
            "recommended_attachments": ["docs/smoke-checks/latest-trial-signup-smoke-check.json"],
            "render_support_packet_files": ["render.yaml", "docs/smoke-checks/escalation-packet/render-support-message.txt"],
            "traction_handoff_files": ["docs/TRIAL_SIGNUP_E2E_REPORT_2026-04-01.md"],
        }
        report["summary"]["render_escalation_payload"] = {
            "ticket_title": "Webhook routing outage",
            "severity": "critical",
            "owner": "Traction",
            "destination": "Render support",
            "requested_action": "Reattach the webhook hostname and redeploy.",
            "missing_live_e2e_secrets": ["STRIPE_SECRET_KEY", "RESEND_API_KEY"],
        }
        report["summary"]["escalation_packet_hashes"] = {
            "render-support-message.txt": {"sha256": "abc123", "size_bytes": 12},
        }

        readme = smoke.build_escalation_packet_readme(report)

        self.assertIn("AMS-APP Render Escalation Packet", readme)
        self.assertIn("Severity: critical", readme)
        self.assertIn("- render.yaml", readme)
        self.assertIn("- docs/smoke-checks/latest-trial-signup-smoke-check.json", readme)
        self.assertIn("- STRIPE_SECRET_KEY", readme)
        self.assertIn("Integrity hashes:", readme)
        self.assertIn("render-support-message.txt: sha256=abc123 size_bytes=12", readme)
        self.assertIn("compare the attached files against the sha256 hashes", readme)
        self.assertIn("Use escalation-packet.zip if the support channel accepts a single attachment", readme)
        self.assertIn("Send render-support-message.txt as the support message body.", readme)

    def test_write_bundle_checksum_file_writes_detached_sha256(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_path = pathlib.Path(temp_dir) / "escalation-packet.zip"
            bundle_path.write_bytes(b"packet-bytes")

            checksum_path = smoke.write_bundle_checksum_file(bundle_path)

            self.assertEqual(checksum_path.name, "escalation-packet.zip.sha256")
            checksum_text = checksum_path.read_text(encoding="utf-8")
            self.assertTrue(checksum_text.endswith("  escalation-packet.zip\n"))
            self.assertEqual(len(checksum_text.split()[0]), 64)

    def test_write_escalation_packet_writes_send_ready_files(self):
        report = self._build_ready_report()
        report["generated_at"] = "2026-04-05T05:14:58.289624+00:00"
        report["summary"]["artifact_inventory"] = {
            "recommended_attachments": ["docs/smoke-checks/latest-trial-signup-smoke-check.json"],
            "render_support_packet_files": ["render.yaml"],
            "traction_handoff_files": ["docs/TRIAL_SIGNUP_E2E_REPORT_2026-04-01.md"],
        }
        report["summary"]["render_escalation_message"] = "Render support request body"
        report["summary"]["render_escalation_payload"] = {"ticket_title": "Webhook routing outage", "severity": "critical"}

        with tempfile.TemporaryDirectory() as temp_dir:
            written_paths = smoke.write_escalation_packet(report, temp_dir)
            written_names = sorted(path.name for path in written_paths)
            self.assertEqual(
                written_names,
                [
                    "README.txt",
                    "escalation-packet.zip",
                    "escalation-packet.zip.sha256",
                    "evidence-manifest.json",
                    "render-support-message.txt",
                    "render-support-payload.json",
                ],
            )
            self.assertEqual(
                (pathlib.Path(temp_dir) / "render-support-message.txt").read_text(encoding="utf-8"),
                "Render support request body\n",
            )
            payload = json.loads((pathlib.Path(temp_dir) / "render-support-payload.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["ticket_title"], "Webhook routing outage")
            manifest = json.loads((pathlib.Path(temp_dir) / "evidence-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["generated_at"], "2026-04-05T05:14:58.289624+00:00")
            self.assertIn("render.yaml", manifest["render_support_packet_files"])
            self.assertIn("packet_hashes", manifest)
            self.assertIn("render-support-message.txt", manifest["packet_hashes"])
            self.assertIn("evidence-manifest.json", manifest["packet_hashes"])
            self.assertEqual(len(manifest["packet_hashes"]["render-support-message.txt"]["sha256"]), 64)
            self.assertIn("AMS-APP Render Escalation Packet", (pathlib.Path(temp_dir) / "README.txt").read_text(encoding="utf-8"))
            checksum_text = (pathlib.Path(temp_dir) / "escalation-packet.zip.sha256").read_text(encoding="utf-8")
            self.assertTrue(checksum_text.endswith("  escalation-packet.zip\n"))
            with zipfile.ZipFile(pathlib.Path(temp_dir) / "escalation-packet.zip") as bundle:
                self.assertEqual(
                    sorted(bundle.namelist()),
                    [
                        "README.txt",
                        "evidence-manifest.json",
                        "render-support-message.txt",
                        "render-support-payload.json",
                    ],
                )

    def test_verify_latest_escalation_packet_reports_ready_bundle_state(self):
        report = self._build_ready_report()
        report["generated_at"] = "2026-04-05T05:14:58.289624+00:00"
        report["summary"]["artifact_inventory"] = {
            "recommended_attachments": ["docs/smoke-checks/latest-trial-signup-smoke-check.json"],
            "render_support_packet_files": ["render.yaml"],
            "traction_handoff_files": ["docs/TRIAL_SIGNUP_E2E_REPORT_2026-04-01.md"],
        }
        report["summary"]["render_escalation_message"] = "Render support request body"
        report["summary"]["render_escalation_payload"] = {"ticket_title": "Webhook routing outage", "severity": "critical"}

        with tempfile.TemporaryDirectory() as temp_dir:
            smoke.write_escalation_packet(report, temp_dir)
            verification = smoke.verify_latest_escalation_packet(temp_dir)

        self.assertTrue(verification["ok"])
        self.assertTrue(verification["checksum_matches"])
        self.assertEqual(
            verification["bundle_members"],
            [
                "README.txt",
                "evidence-manifest.json",
                "render-support-message.txt",
                "render-support-payload.json",
            ],
        )
        self.assertEqual(verification["missing_bundle_members"], [])
        self.assertGreaterEqual(verification["manifest_packet_hash_count"], 1)
        self.assertIn(verification["manifest_lists_bundle_checksum"], [True, False])
        self.assertTrue(verification["manifest_hashes_match_files"])
        self.assertEqual(verification["manifest_missing_hash_files"], [])
        self.assertEqual(verification["manifest_mismatched_hash_files"], [])

    def test_verify_latest_escalation_packet_detects_manifest_hash_drift(self):
        report = self._build_ready_report()
        report["generated_at"] = "2026-04-05T05:14:58.289624+00:00"
        report["summary"]["artifact_inventory"] = {
            "recommended_attachments": ["docs/smoke-checks/latest-trial-signup-smoke-check.json"],
            "render_support_packet_files": ["render.yaml"],
            "traction_handoff_files": ["docs/TRIAL_SIGNUP_E2E_REPORT_2026-04-01.md"],
        }
        report["summary"]["render_escalation_message"] = "Render support request body"
        report["summary"]["render_escalation_payload"] = {"ticket_title": "Webhook routing outage", "severity": "critical"}

        with tempfile.TemporaryDirectory() as temp_dir:
            packet_dir = pathlib.Path(temp_dir)
            smoke.write_escalation_packet(report, temp_dir)
            (packet_dir / "render-support-message.txt").write_text("tampered message", encoding="utf-8")

            verification = smoke.verify_latest_escalation_packet(temp_dir)

        self.assertFalse(verification["ok"])
        self.assertFalse(verification["manifest_hashes_match_files"])
        self.assertEqual(verification["manifest_missing_hash_files"], [])
        self.assertEqual(verification["manifest_mismatched_hash_files"], ["render-support-message.txt"])

    def test_build_escalation_packet_archive_file_paths_uses_generated_at_slug(self):
        report = self._build_ready_report()
        report["generated_at"] = "2026-04-05T05:14:58.289624+00:00"

        archive_paths = smoke.build_escalation_packet_archive_file_paths(report, "docs/smoke-checks/escalation-packet/archive")

        self.assertEqual(
            archive_paths["render-support-message.txt"].as_posix(),
            "docs/smoke-checks/escalation-packet/archive/2026-04-05T05-14-58-289624-00-00-render-support-message.txt",
        )
        self.assertEqual(
            archive_paths["render-support-payload.json"].as_posix(),
            "docs/smoke-checks/escalation-packet/archive/2026-04-05T05-14-58-289624-00-00-render-support-payload.json",
        )
        self.assertEqual(
            archive_paths["evidence-manifest.json"].as_posix(),
            "docs/smoke-checks/escalation-packet/archive/2026-04-05T05-14-58-289624-00-00-evidence-manifest.json",
        )
        self.assertEqual(
            archive_paths["README.txt"].as_posix(),
            "docs/smoke-checks/escalation-packet/archive/2026-04-05T05-14-58-289624-00-00-README.txt",
        )
        self.assertEqual(
            archive_paths["escalation-packet.zip"].as_posix(),
            "docs/smoke-checks/escalation-packet/archive/2026-04-05T05-14-58-289624-00-00-escalation-packet.zip",
        )
        self.assertEqual(
            archive_paths["escalation-packet.zip.sha256"].as_posix(),
            "docs/smoke-checks/escalation-packet/archive/2026-04-05T05-14-58-289624-00-00-escalation-packet.zip.sha256",
        )

    def test_write_escalation_packet_archive_writes_timestamped_snapshots(self):
        report = self._build_ready_report()
        report["generated_at"] = "2026-04-05T05:14:58.289624+00:00"
        report["summary"]["artifact_inventory"] = {
            "recommended_attachments": ["docs/smoke-checks/latest-trial-signup-smoke-check.json"],
            "render_support_packet_files": ["render.yaml"],
            "traction_handoff_files": ["docs/TRIAL_SIGNUP_E2E_REPORT_2026-04-01.md"],
        }
        report["summary"]["render_escalation_message"] = "Render support request body"
        report["summary"]["render_escalation_payload"] = {"ticket_title": "Webhook routing outage", "severity": "critical"}

        with tempfile.TemporaryDirectory() as temp_dir:
            written_paths = smoke.write_escalation_packet_archive(report, temp_dir)
            written_names = sorted(path.name for path in written_paths)
            self.assertEqual(
                written_names,
                [
                    "2026-04-05T05-14-58-289624-00-00-README.txt",
                    "2026-04-05T05-14-58-289624-00-00-escalation-packet.zip",
                    "2026-04-05T05-14-58-289624-00-00-escalation-packet.zip.sha256",
                    "2026-04-05T05-14-58-289624-00-00-evidence-manifest.json",
                    "2026-04-05T05-14-58-289624-00-00-render-support-message.txt",
                    "2026-04-05T05-14-58-289624-00-00-render-support-payload.json",
                ],
            )
            self.assertEqual(
                (pathlib.Path(temp_dir) / "2026-04-05T05-14-58-289624-00-00-render-support-message.txt").read_text(encoding="utf-8"),
                "Render support request body\n",
            )
            self.assertIn(
                "AMS-APP Render Escalation Packet",
                (pathlib.Path(temp_dir) / "2026-04-05T05-14-58-289624-00-00-README.txt").read_text(encoding="utf-8"),
            )
            checksum_text = (pathlib.Path(temp_dir) / "2026-04-05T05-14-58-289624-00-00-escalation-packet.zip.sha256").read_text(encoding="utf-8")
            self.assertTrue(checksum_text.endswith("  2026-04-05T05-14-58-289624-00-00-escalation-packet.zip\n"))
            with zipfile.ZipFile(pathlib.Path(temp_dir) / "2026-04-05T05-14-58-289624-00-00-escalation-packet.zip") as bundle:
                self.assertIn("render-support-message.txt", bundle.namelist())

    def test_main_can_write_json_markdown_and_owner_message_outputs(self):
        report = self._build_ready_report()
        report["generated_at"] = "2026-04-05T05:14:58.289624+00:00"

        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = pathlib.Path(temp_dir) / "report.json"
            markdown_path = pathlib.Path(temp_dir) / "report.md"
            owner_dir = pathlib.Path(temp_dir) / "owner-messages"
            archive_dir = pathlib.Path(temp_dir) / "owner-messages-archive"
            escalation_dir = pathlib.Path(temp_dir) / "escalation-packet"
            escalation_archive_dir = pathlib.Path(temp_dir) / "escalation-packet-archive"

            with mock.patch.object(smoke, "generate_report", return_value=report), mock.patch.object(smoke, "load_previous_report", return_value=None), mock.patch("sys.stdout") as stdout:
                exit_code = smoke.main([
                    "--json-out",
                    str(json_path),
                    "--markdown-out",
                    str(markdown_path),
                    "--owner-messages-dir",
                    str(owner_dir),
                    "--owner-messages-archive-dir",
                    str(archive_dir),
                    "--escalation-packet-dir",
                    str(escalation_dir),
                    "--escalation-packet-archive-dir",
                    str(escalation_archive_dir),
                ])

            self.assertEqual(exit_code, 0)
            self.assertTrue(json_path.exists())
            self.assertTrue(markdown_path.exists())
            self.assertTrue((owner_dir / "traction.txt").exists())
            self.assertTrue((owner_dir / "render_support.txt").exists())
            self.assertTrue((owner_dir / "verification_shell.txt").exists())
            self.assertTrue((archive_dir / "2026-04-05T05-14-58-289624-00-00-traction.txt").exists())
            self.assertTrue((escalation_dir / "render-support-message.txt").exists())
            self.assertTrue((escalation_dir / "render-support-payload.json").exists())
            self.assertTrue((escalation_dir / "evidence-manifest.json").exists())
            self.assertTrue((escalation_dir / "README.txt").exists())
            self.assertTrue((escalation_dir / "escalation-packet.zip").exists())
            self.assertTrue((escalation_dir / "escalation-packet.zip.sha256").exists())
            self.assertTrue((escalation_archive_dir / "2026-04-05T05-14-58-289624-00-00-render-support-message.txt").exists())
            self.assertTrue((escalation_archive_dir / "2026-04-05T05-14-58-289624-00-00-render-support-payload.json").exists())
            self.assertTrue((escalation_archive_dir / "2026-04-05T05-14-58-289624-00-00-evidence-manifest.json").exists())
            self.assertTrue((escalation_archive_dir / "2026-04-05T05-14-58-289624-00-00-README.txt").exists())
            self.assertTrue((escalation_archive_dir / "2026-04-05T05-14-58-289624-00-00-escalation-packet.zip").exists())
            self.assertTrue((escalation_archive_dir / "2026-04-05T05-14-58-289624-00-00-escalation-packet.zip.sha256").exists())
            saved_payload = json.loads(json_path.read_text())
            stdout_payload = json.loads("".join(call.args[0] for call in stdout.write.call_args_list))
            self.assertTrue(saved_payload["summary"]["ready_for_live_e2e"])
            self.assertEqual(stdout_payload, saved_payload)
            self.assertIn("owner_ready_traction", saved_payload["summary"]["artifact_inventory"])
            self.assertIn("escalation_packet_bundle", saved_payload["summary"]["artifact_inventory"])
            self.assertTrue(saved_payload["summary"]["latest_escalation_packet_verification"]["ok"])
            self.assertIn("Trial Signup Smoke Check Snapshot", markdown_path.read_text())
            self.assertIn("Latest escalation packet verification", markdown_path.read_text())

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
        ), mock.patch.object(smoke, "load_previous_report", return_value=None), mock.patch("sys.stdout") as stdout:
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
        self.assertEqual(payload["summary"]["render_hostname_diagnostics"]["commission-tracker-webhook"]["attachment_state"], "missing-backend-attachment")
        self.assertTrue(payload["summary"]["render_incident_signature"]["external_routing_issue"])
        self.assertIn("domain binding problem", payload["summary"]["render_incident_signature"]["conclusion"])
        self.assertIn("commission-tracker-webhook first", payload["summary"]["render_recovery_playbook"][0])
        self.assertEqual(payload["summary"]["local_webhook_dependency_commands"], [])
        self.assertFalse(payload["summary"]["ready_for_live_e2e"])


    def test_build_artifact_freshness_flags_current_and_stale_outputs(self):
        report = {
            "generated_at": "2026-04-06T05:14:00+00:00",
            "summary": {
                "artifact_inventory": {
                    "latest_json": {"path": "docs/smoke-checks/latest-trial-signup-smoke-check.json", "exists": True, "modified_at": "2026-04-06T05:14:01+00:00"},
                    "latest_markdown": {"path": "docs/smoke-checks/latest-trial-signup-smoke-check.md", "exists": True, "modified_at": "2026-04-06T05:14:02+00:00"},
                    "owner_ready_traction": {"path": "docs/smoke-checks/owner-ready/traction.txt", "exists": True, "modified_at": "2026-04-06T05:13:59+00:00"},
                    "owner_ready_render_support": {"path": "docs/smoke-checks/owner-ready/render_support.txt", "exists": False, "modified_at": None},
                    "owner_ready_verification_shell": {"path": "docs/smoke-checks/owner-ready/verification_shell.txt", "exists": True, "modified_at": "2026-04-06T05:14:03+00:00"},
                    "escalation_packet_message": {"path": "docs/smoke-checks/escalation-packet/render-support-message.txt", "exists": True, "modified_at": "2026-04-06T05:14:04+00:00"},
                    "escalation_packet_payload": {"path": "docs/smoke-checks/escalation-packet/render-support-payload.json", "exists": True, "modified_at": "2026-04-06T05:14:05+00:00"},
                    "escalation_packet_manifest": {"path": "docs/smoke-checks/escalation-packet/evidence-manifest.json", "exists": True, "modified_at": "2026-04-06T05:14:06+00:00"},
                    "escalation_packet_readme": {"path": "docs/smoke-checks/escalation-packet/README.txt", "exists": True, "modified_at": "2026-04-06T05:14:07+00:00"},
                    "escalation_packet_bundle": {"path": "docs/smoke-checks/escalation-packet/escalation-packet.zip", "exists": True, "modified_at": "2026-04-06T05:14:08+00:00"},
                    "escalation_packet_bundle_checksum": {"path": "docs/smoke-checks/escalation-packet/escalation-packet.zip.sha256", "exists": True, "modified_at": "2026-04-06T05:14:09+00:00"},
                }
            },
        }

        freshness = smoke.build_artifact_freshness(report)

        self.assertFalse(freshness["all_fresh"])
        self.assertEqual(freshness["tracked_file_count"], 11)
        self.assertEqual(freshness["fresh_file_count"], 9)
        self.assertIn("owner_ready_traction", freshness["stale_labels"])
        self.assertIn("owner_ready_render_support", freshness["missing_labels"])
        self.assertTrue(freshness["files"]["latest_json"]["fresh_for_run"])
        self.assertFalse(freshness["files"]["owner_ready_traction"]["fresh_for_run"])

    def test_build_archive_snapshot_verification_reports_current_run_archives(self):
        report = self._build_ready_report()
        report["generated_at"] = "2026-04-06T09:17:00+00:00"

        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            owner_archive_dir = root / "docs" / "smoke-checks" / "owner-ready" / "archive"
            packet_archive_dir = root / "docs" / "smoke-checks" / "escalation-packet" / "archive"
            owner_archive_dir.mkdir(parents=True)
            packet_archive_dir.mkdir(parents=True)

            owner_paths = smoke.build_owner_ready_archive_file_paths(report, owner_archive_dir)
            for path in owner_paths.values():
                path.write_text("ok\n", encoding="utf-8")

            packet_paths = smoke.build_escalation_packet_archive_file_paths(report, packet_archive_dir)
            for name, path in packet_paths.items():
                if name == "escalation-packet.zip":
                    path.write_bytes(b"archive-bundle")
                elif name == "escalation-packet.zip.sha256":
                    digest = smoke.hashlib.sha256((packet_archive_dir / path.name.replace('.sha256', '')).read_bytes()).hexdigest()
                    path.write_text(f"{digest}  {(packet_archive_dir / path.name.replace('.sha256', '')).name}\n", encoding="utf-8")
                else:
                    path.write_text("ok\n", encoding="utf-8")

            with mock.patch.object(smoke, "DEFAULT_OWNER_READY_ARCHIVE_DIR", owner_archive_dir), mock.patch.object(smoke, "DEFAULT_ESCALATION_PACKET_ARCHIVE_DIR", packet_archive_dir):
                verification = smoke.build_archive_snapshot_verification(report)

        self.assertTrue(verification["ok"])
        self.assertEqual(verification["owner_ready_archive_present_count"], 3)
        self.assertEqual(verification["escalation_packet_archive_present_count"], 6)
        self.assertEqual(verification["missing_files"], [])
        self.assertTrue(verification["packet_bundle_verification"]["checksum_matches"])

    def test_build_archive_snapshot_verification_flags_missing_archives(self):
        report = self._build_ready_report()
        report["generated_at"] = "2026-04-06T09:17:00+00:00"

        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            owner_archive_dir = root / "docs" / "smoke-checks" / "owner-ready" / "archive"
            packet_archive_dir = root / "docs" / "smoke-checks" / "escalation-packet" / "archive"
            owner_archive_dir.mkdir(parents=True)
            packet_archive_dir.mkdir(parents=True)

            with mock.patch.object(smoke, "DEFAULT_OWNER_READY_ARCHIVE_DIR", owner_archive_dir), mock.patch.object(smoke, "DEFAULT_ESCALATION_PACKET_ARCHIVE_DIR", packet_archive_dir):
                verification = smoke.build_archive_snapshot_verification(report)

        self.assertFalse(verification["ok"])
        self.assertGreaterEqual(len(verification["missing_files"]), 1)
        self.assertFalse(verification["packet_bundle_verification"]["checksum_matches"])

    def test_main_reports_artifact_freshness_surfaces_nondefault_output_paths_as_stale(self):
        report = self._build_ready_report()

        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = pathlib.Path(temp_dir) / "report.json"
            markdown_path = pathlib.Path(temp_dir) / "report.md"
            owner_dir = pathlib.Path(temp_dir) / "owner-messages"
            archive_dir = pathlib.Path(temp_dir) / "owner-messages-archive"
            escalation_dir = pathlib.Path(temp_dir) / "escalation-packet"
            escalation_archive_dir = pathlib.Path(temp_dir) / "escalation-packet-archive"

            with mock.patch.object(smoke, "generate_report", return_value=report), mock.patch.object(smoke, "load_previous_report", return_value=None), mock.patch("sys.stdout"):
                exit_code = smoke.main([
                    "--json-out", str(json_path),
                    "--markdown-out", str(markdown_path),
                    "--owner-messages-dir", str(owner_dir),
                    "--owner-messages-archive-dir", str(archive_dir),
                    "--escalation-packet-dir", str(escalation_dir),
                    "--escalation-packet-archive-dir", str(escalation_archive_dir),
                ])

            self.assertEqual(exit_code, 0)
            saved_payload = json.loads(json_path.read_text())
            self.assertIn("artifact_freshness", saved_payload["summary"])
            self.assertIn("archive_snapshot_verification", saved_payload["summary"])
            self.assertFalse(saved_payload["summary"]["artifact_freshness"]["all_fresh"])
            self.assertEqual(saved_payload["summary"]["artifact_freshness"]["tracked_file_count"], 11)
            self.assertGreaterEqual(len(saved_payload["summary"]["artifact_freshness"]["stale_labels"]), 1)
            self.assertIn("latest_json", saved_payload["summary"]["artifact_freshness"]["stale_labels"])
            self.assertIn("## Artifact freshness", markdown_path.read_text())
            self.assertIn("## Archive snapshot verification", markdown_path.read_text())


if __name__ == "__main__":
    unittest.main()
