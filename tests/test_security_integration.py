"""
MAYA Security Integration Test Suite
Validates:
- Strict constant-time HMAC token authentication on state-changing endpoints
- Untrusted origin rejection (CORS enforcement)
- Trusted origin allowance
- Loopback-restricted token bootstrap
- Plan suspension, single-use token binding, tamper resistance, replay prevention, and invalid resume rejection
"""
import unittest
import json
import time
import hmac
from pathlib import Path

from maya_server import app, AUTH_TOKEN, permissions, planner, ledger
from security.permissions.tier import PermissionLevel, PermissionManager, hash_arguments

class TestSecurityIntegration(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.auth_headers = {
            "X-Maya-Token": AUTH_TOKEN,
            "Content-Type": "application/json"
        }

    # 1. State-changing endpoints require token
    def test_auth_missing_token(self):
        res = self.client.post("/api/chat", json={"message": "Hello"})
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertIn("error", data)
        self.assertIn("Missing X-Maya-Token", data["error"])

    # 2. State-changing endpoints reject invalid token
    def test_auth_invalid_token(self):
        bad_headers = {
            "X-Maya-Token": "completely_fake_token_value_9999",
            "Content-Type": "application/json"
        }
        res = self.client.post("/api/chat", headers=bad_headers, json={"message": "Hello"})
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertIn("error", data)
        self.assertIn("Invalid session token", data["error"])

    # 3. State-changing endpoints allow valid token
    def test_auth_valid_token(self):
        res = self.client.post("/api/chat", headers=self.auth_headers, json={"message": "Hello Maya"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue("reply" in data or "response" in data)

    # 4. Untrusted Origin header is rejected with 403
    def test_untrusted_origin_rejection(self):
        headers = {
            "X-Maya-Token": AUTH_TOKEN,
            "Origin": "https://malicious-website.attacker.com",
            "Content-Type": "application/json"
        }
        res = self.client.post("/api/chat", headers=headers, json={"message": "Hello"})
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertIn("Untrusted origin", data.get("error", ""))

    # 5. Trusted Origin headers are allowed
    def test_trusted_origin_allowed(self):
        for origin in [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "app://maya",
            "chrome-extension://cbffklcgjeagclgldpkiflcbgbmjgohh"
        ]:
            headers = {
                "X-Maya-Token": AUTH_TOKEN,
                "Origin": origin,
                "Content-Type": "application/json"
            }
            res = self.client.post("/api/chat", headers=headers, json={"message": "Ping"})
            self.assertEqual(res.status_code, 200)

    # 6. Loopback token bootstrap endpoint
    def test_loopback_bootstrap_security(self):
        # Localhost request allowed
        res = self.client.get("/api/auth/token", environ_base={"REMOTE_ADDR": "127.0.0.1"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("token"), AUTH_TOKEN)

        # Remote / non-loopback address strictly blocked
        res_remote = self.client.get("/api/auth/token", environ_base={"REMOTE_ADDR": "192.168.1.55"})
        self.assertEqual(res_remote.status_code, 403)
        self.assertIn("Forbidden", res_remote.get_json().get("error", ""))

    # 7. Plan Resume Security: Wrong Plan ID
    def test_plan_resume_wrong_plan_id(self):
        res = self.client.post(
            "/api/plans/nonexistent_plan_999/resume",
            headers=self.auth_headers,
            json={"confirmation_id": "conf-123", "permission_token": "token-123"}
        )
        data = res.get_json()
        self.assertFalse(data.get("success", True))
        self.assertIn("not found", data.get("error", "").lower())

    # 8. Plan Resume Security: Wrong Confirmation ID
    def test_plan_resume_wrong_confirmation_id(self):
        # Create a real suspended plan requiring confirmation
        intent = {
            "intent": "TERMINATE_PROCESS",
            "tool": "terminate_process",
            "arguments": {"pid": 99999}
        }
        plan = planner.create_plan("Kill process", intent_info=intent)
        exec_res = planner.execute_plan(plan)
        self.assertEqual(exec_res.get("state"), "WAITING_FOR_PERMISSION")
        real_conf_id = exec_res.get("confirmation_id")
        self.assertIsNotNone(real_conf_id)

        # Attempt to resume with wrong confirmation ID
        res = self.client.post(
            f"/api/plans/{plan.plan_id}/resume",
            headers=self.auth_headers,
            json={"confirmation_id": "fake_wrong_conf_id", "permission_token": "any_token"}
        )
        data = res.get_json()
        self.assertFalse(data.get("success", True))
        err_msg = data.get("error", "").lower()
        self.assertTrue("mismatch" in err_msg or "invalid" in err_msg or "not found" in err_msg)

    # 9. Plan Resume Security: Single-Use Token and Replay Prevention
    def test_single_use_token_replay_prevention(self):
        # Create confirmation
        test_pm = PermissionManager()
        dec = test_pm.check_permission("delete_file", {"filepath": "dummy.txt"})
        self.assertTrue(dec.requires_confirmation)
        conf_id = dec.confirmation_id

        # Approve and issue token
        token = test_pm.resolve_confirmation(conf_id, approved=True)
        self.assertIsNotNone(token)

        # First use: must be granted
        first_dec = test_pm.check_permission("delete_file", {"filepath": "dummy.txt"}, token=token)
        self.assertTrue(first_dec.granted)

        # Replay attack (second use of same token): must be denied!
        replay_dec = test_pm.check_permission("delete_file", {"filepath": "dummy.txt"}, token=token)
        self.assertFalse(replay_dec.granted)
        self.assertTrue(replay_dec.requires_confirmation)

    # 10. Plan Resume Security: Argument Tampering Prevention
    def test_argument_tampering_prevention(self):
        test_pm = PermissionManager()
        original_args = {"filepath": "D:/MAYA/safe_file.txt"}
        dec = test_pm.check_permission("delete_file", original_args)
        conf_id = dec.confirmation_id

        # Approve original action
        token = test_pm.resolve_confirmation(conf_id, approved=True)

        # Attack: Attacker attempts to use token for different/tampered arguments!
        tampered_args = {"filepath": "C:/Windows/System32/critical.dll"}
        tampered_dec = test_pm.check_permission("delete_file", tampered_args, token=token)

        # Must be rejected because args_hash does not match!
        self.assertFalse(tampered_dec.granted)
        self.assertTrue(tampered_dec.requires_confirmation)

    def test_send_communication_requires_exact_confirmation(self):
        test_pm = PermissionManager(PermissionLevel.LEVEL_2_SAFE_ACTION)
        original_args = {
            "service": "gmail",
            "recipient": "friend@example.com",
            "message": "Original message",
            "profile": "main"
        }

        decision = test_pm.check_permission("send_communication", original_args)
        self.assertFalse(decision.granted)
        self.assertTrue(decision.requires_confirmation)

        token = test_pm.resolve_confirmation(decision.confirmation_id, approved=True)
        self.assertIsNotNone(token)

        tampered_args = dict(original_args)
        tampered_args["recipient"] = "different@example.com"
        tampered = test_pm.check_permission("send_communication", tampered_args, token=token)

        self.assertFalse(tampered.granted)
        self.assertTrue(tampered.requires_confirmation)

    # 11. Plan Resume Security: Expired Token Rejection
    def test_expired_token_rejection(self):
        test_pm = PermissionManager()
        dec = test_pm.check_permission("delete_file", {"filepath": "dummy.txt"})
        token = test_pm.resolve_confirmation(dec.confirmation_id, approved=True)

        # Manually backdate expiration to simulate expired token
        test_pm.issued_tokens[token]["expires_at"] = time.time() - 100.0

        expired_dec = test_pm.check_permission("delete_file", {"filepath": "dummy.txt"}, token=token)
        self.assertFalse(expired_dec.granted)
        self.assertTrue(expired_dec.requires_confirmation)

if __name__ == "__main__":
    unittest.main()
