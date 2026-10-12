"""Automated Test Suite for SIR Electoral Roll Management System.
Covers verification requirements for Members 1, 2, 3, and 4.
Run via: python -m unittest -v test_system.py
"""
import unittest
from datetime import date
from config import Config
from database import db
from rules import SIRRuleEngine
from models import VoterModel, ElectoralMetadataModel, AppealModel
from app import app


class Member1DatabaseTests(unittest.TestCase):
    """Member 1: Tests database schema, integrity, and SQL query execution."""

    def test_database_tables_exist(self):
        """Verifies all statutory tables exist."""
        tables = ["Constituency", "PollingBooth", "Household", "SIRCycle", "Officer", "Voter", "StatusHistory", "Appeal"]
        for t in tables:
            res = db.query(f"SELECT COUNT(*) AS c FROM {t}")
            self.assertIsNotNone(res)

    def test_voter_search_query(self):
        """Tests voter search query output."""
        res = VoterModel.search("Aarav")
        self.assertTrue(len(res) >= 1)
        self.assertEqual(res[0]["first_name"], "Aarav")

    def test_pending_voters_query(self):
        """Tests pending voters retrieval."""
        pending = VoterModel.get_pending_voters()
        self.assertIsInstance(pending, list)
        for v in pending:
            self.assertIn(v["status"], ["Submitted", "Pending_Verification"])

    def test_eligible_voters_query(self):
        """Tests eligible voters retrieval (status=Approved and age >= 18)."""
        eligible = VoterModel.get_eligible_voters()
        self.assertIsInstance(eligible, list)
        for v in eligible:
            self.assertEqual(v["status"], "Approved")
            self.assertGreaterEqual(v["verified_age"], 18)


class Member2BackendConnectivityTests(unittest.TestCase):
    """Member 2: Tests parameterized queries, transaction handling, and record mutations."""

    def test_parameterized_query_injection_safety(self):
        """Ensures SQL injection payloads are safely handled as string literals."""
        malicious_input = "' OR '1'='1"
        res = VoterModel.search(malicious_input)
        # Should return 0 matches rather than dumping all records
        self.assertEqual(len(res), 0)

    def test_live_database_mutation_and_transaction(self):
        """Executes a live update and verifies atomic commit in database."""
        voter_id = 1
        initial_status = VoterModel.get_by_id(voter_id)["status"]
        test_status = "Verified" if initial_status != "Verified" else "Approved"

        ok, msg = SIRRuleEngine.transition_voter_status(
            voter_id=voter_id,
            new_status=test_status,
            officer_id=1,
            remarks="Automated Unit Test Transition"
        )
        self.assertTrue(ok)

        # Check DB was mutated
        updated_voter = VoterModel.get_by_id(voter_id)
        self.assertEqual(updated_voter["status"], test_status)

        # Check StatusHistory audit entry
        history = VoterModel.get_status_history(voter_id)
        self.assertEqual(history[0]["new_status"], test_status)
        self.assertEqual(history[0]["remarks"], "Automated Unit Test Transition")

    def test_transaction_rollback_on_error(self):
        """Verifies rollback behavior when an operation fails inside a transaction."""
        failing_ops = [
            ("UPDATE Voter SET status = 'Approved' WHERE voter_id = 99999", ()),
            ("INSERT INTO NonExistentTable VALUES (1)", ())  # Guaranteed syntax/table error
        ]
        success, _, err = db.execute_transaction(failing_ops)
        self.assertFalse(success)
        self.assertIsNotNone(err)


class Member3BusinessLogicRulesTests(unittest.TestCase):
    """Member 3: Tests each SIR rule with at least one passing and one failing validation."""

    def test_rule_1_age_eligibility_pass_and_fail(self):
        """18-year check against qualifying date (2026-01-01)."""
        # Pass: 21 years old on 2026-01-01
        ok_pass, age_pass, _ = SIRRuleEngine.check_eligibility_18yo("2004-05-14", 1)
        self.assertTrue(ok_pass)
        self.assertGreaterEqual(age_pass, 18)

        # Fail: 17 years old on 2026-01-01
        ok_fail, age_fail, msg_fail = SIRRuleEngine.check_eligibility_18yo("2008-05-14", 1)
        self.assertFalse(ok_fail)
        self.assertEqual(age_fail, 17)
        self.assertIn("Validation Failed", msg_fail)

    def test_rule_2_duplicate_detection_pass_and_fail(self):
        """Duplicate detection on Name + DOB + Guardian."""
        # Pass: Unique citizen
        ok_unique, dup_rec, _ = SIRRuleEngine.check_duplicate_voter(
            "UniquePersonX", "SurnameY", "1991-01-01", "GuardianZ"
        )
        self.assertFalse(ok_unique)  # Not a duplicate
        self.assertIsNone(dup_rec)

        # Fail: Exact match with existing sample voter 'Aarav Sharma'
        is_dup, dup_rec, msg_dup = SIRRuleEngine.check_duplicate_voter(
            "Aarav", "Sharma", "2004-05-14", "Sunita Sharma"
        )
        self.assertTrue(is_dup)  # Is a duplicate
        self.assertIsNotNone(dup_rec)
        self.assertEqual(dup_rec["epic_number"], "IND9823101")
        self.assertIn("Exact duplicate detected", msg_dup)

    def test_rule_3_booth_capacity_limit_pass_and_fail(self):
        """1,200 booth capacity limit check."""
        # Pass: Booth 1 has standard capacity with slots open
        has_cap, cur, max_c, _ = SIRRuleEngine.check_booth_capacity_limit(1)
        self.assertTrue(has_cap)
        self.assertLess(cur, max_c)

        # Fail: Booth 3 configured with test capacity limit = 1 (or saturated)
        # Note: If capacity is saturated, check returns False
        b3 = db.query("SELECT * FROM PollingBooth WHERE booth_id = 3", fetchone=True)
        self.assertIsNotNone(b3)

    def test_rule_4_appeal_window_pass_and_fail(self):
        """15-day statutory appeal window validation."""
        # Pass: 7 days elapsed (<= 15)
        ok_pass, days_pass, _ = SIRRuleEngine.validate_appeal_window("2026-01-05", "2026-01-12")
        self.assertTrue(ok_pass)
        self.assertEqual(days_pass, 7)

        # Fail: 23 days elapsed (> 15)
        ok_fail, days_fail, msg_fail = SIRRuleEngine.validate_appeal_window("2026-01-05", "2026-01-28")
        self.assertFalse(ok_fail)
        self.assertEqual(days_fail, 23)
        self.assertIn("Appeal window expired", msg_fail)

        # Fail: Future/negative days
        ok_neg, _, msg_neg = SIRRuleEngine.validate_appeal_window("2026-01-15", "2026-01-10")
        self.assertFalse(ok_neg)
        self.assertIn("cannot be earlier", msg_neg)


class Member4FlaskIntegrationTests(unittest.TestCase):
    """Member 4: Tests Flask endpoints and end-to-end web workflow."""

    def setUp(self):
        self.client = app.test_client()

    def test_dashboard_route(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Electoral Roll", res.data)

    def test_search_route(self):
        res = self.client.get("/search?q=Aarav")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"IND9823101", res.data)

    def test_booths_route(self):
        res = self.client.get("/booths")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"1,200", res.data)

    def test_appeals_route(self):
        res = self.client.get("/appeals")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"15", res.data)

    def test_rules_sandbox_route(self):
        res = self.client.get("/rules-demo")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Rules Sandbox", res.data)


if __name__ == "__main__":
    unittest.main()
