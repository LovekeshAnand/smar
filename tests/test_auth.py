"""
tests/test_auth.py
==================
Unit tests for multi-user authentication, password verification, registration,
and session management in SMAR v2.
"""

import os
import tempfile
import unittest
from auth import UserManager, hash_password, verify_password


class TestAuth(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.users_file = os.path.join(self.temp_dir, "test_users.json")
        self.mgr = UserManager(users_file=self.users_file)

    def tearDown(self):
        if os.path.exists(self.users_file):
            try:
                os.remove(self.users_file)
            except OSError:
                pass

    def test_default_user_lovekesh(self):
        """Verify lovekesh is pre-seeded as admin with correct password."""
        auth_res = self.mgr.authenticate("lovekesh", "lovekesh123")
        self.assertIsNotNone(auth_res)
        self.assertEqual(auth_res["user"]["username"], "lovekesh")
        self.assertEqual(auth_res["user"]["role"], "admin")
        self.assertTrue("token" in auth_res)

        # Bad password rejected
        bad = self.mgr.authenticate("lovekesh", "wrongpass")
        self.assertIsNone(bad)

    def test_case_insensitivity(self):
        """Username check must be case-insensitive."""
        auth_res = self.mgr.authenticate("LoVeKeSh", "lovekesh123")
        self.assertIsNotNone(auth_res)
        self.assertEqual(auth_res["user"]["username"], "lovekesh")

    def test_register_and_authenticate_new_user(self):
        """Register a new user and authenticate."""
        reg = self.mgr.register_user("sweta", "sweta123", name="Sweta Sharma", role="user")
        self.assertIsNotNone(reg)
        self.assertEqual(reg["user"]["username"], "sweta")

        # Authenticate new user
        auth_res = self.mgr.authenticate("sweta", "sweta123")
        self.assertIsNotNone(auth_res)
        self.assertEqual(auth_res["user"]["name"], "Sweta Sharma")

        # Duplicate registration prevented
        with self.assertRaises(ValueError):
            self.mgr.register_user("sweta", "anotherpass")

    def test_session_token_validation(self):
        """Verify session token generation and verification."""
        auth_res = self.mgr.authenticate("lovekesh", "lovekesh123")
        token = auth_res["token"]
        user = self.mgr.verify_token(token)
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], "lovekesh")

        # Invalid token
        self.assertIsNone(self.mgr.verify_token("invalid_token_123"))

    def test_list_users(self):
        """List registered users."""
        users = self.mgr.list_users()
        usernames = [u["username"] for u in users]
        self.assertIn("lovekesh", usernames)
        self.assertIn("guest", usernames)
        # Verify passwords are never exposed in user listings
        for u in users:
            self.assertNotIn("password_hash", u)


if __name__ == "__main__":
    unittest.main()
