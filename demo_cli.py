"""Command-Line Terminal Demonstration Script for SIR Electoral Roll Management System.
Demonstrates:
- Member 1: Database queries (Voter search, pending voters, eligible voters, booth limit)
- Member 2: Live parameterized request mutating a database record and logging audit history
- Member 3: SIR Business logic validations showing both PASSED and FAILED outputs
"""
import sys
from datetime import datetime, date
from database import db
from rules import SIRRuleEngine
from models import VoterModel, ElectoralMetadataModel


def print_header(title: str):
    print("\n" + "=" * 80)
    print(f"  {title.upper()}")
    print("=" * 80)


def print_table(headers: list, rows: list):
    if not rows:
        print("  [No records returned]")
        return
    col_widths = [len(h) for h in headers]
    for r in rows:
        for idx, val in enumerate(r):
            col_widths[idx] = max(col_widths[idx], len(str(val)))
    
    header_str = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    sep_str = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
    print("  " + header_str)
    print("  " + sep_str)
    for r in rows:
        row_str = " | ".join(str(val).ljust(col_widths[i]) for i, val in enumerate(r))
        print("  " + row_str)


def demo_member_1():
    print_header("Member 1 — Database & SQL Implementation Demonstration")
    print(f"[*] Connected Engine: {db.driver.upper()}")
    
    # Query 1: Voter Search
    print("\n>>> [1] SQL Query: Voter Search (EPIC 'IND9823101' or Name 'Aarav')")
    sql_search = """
        SELECT v.epic_number, CONCAT(v.first_name, ' ', v.last_name) AS full_name,
               v.dob, v.gender, pb.booth_name, v.status
        FROM Voter v
        JOIN PollingBooth pb ON v.booth_id = pb.booth_id
        WHERE v.epic_number = 'IND9823101' OR v.first_name LIKE '%Aarav%'
    """
    rows = db.query(sql_search)
    data = [[r["epic_number"], r["full_name"], r["dob"], r["gender"], r["booth_name"][:25], r["status"]] for r in rows]
    print_table(["EPIC", "Full Name", "DOB", "Gender", "Polling Booth", "Status"], data)

    # Query 2: Pending Voters
    print("\n>>> [2] SQL Query: Pending Voters Awaiting Field Verification")
    sql_pending = """
        SELECT v.epic_number, CONCAT(v.first_name, ' ', v.last_name) AS applicant,
               v.dob, pb.booth_name, v.status, v.created_at
        FROM Voter v
        JOIN PollingBooth pb ON v.booth_id = pb.booth_id
        WHERE v.status IN ('Submitted', 'Pending_Verification')
    """
    rows = db.query(sql_pending)
    data = [[r["epic_number"], r["applicant"], r["dob"], r["booth_name"][:25], r["status"], str(r["created_at"])[:19]] for r in rows]
    print_table(["EPIC", "Applicant", "DOB", "Polling Booth", "Status", "Submitted At"], data)

    # Query 3: Eligible Voters
    print("\n>>> [3] SQL Query: Verified & Eligible Voters (Status='Approved')")
    sql_eligible = """
        SELECT v.epic_number, CONCAT(v.first_name, ' ', v.last_name) AS voter_name,
               v.dob, sc.qualifying_date, pb.booth_name, v.status
        FROM Voter v
        JOIN PollingBooth pb ON v.booth_id = pb.booth_id
        JOIN SIRCycle sc ON v.cycle_id = sc.cycle_id
        WHERE v.status = 'Approved'
    """
    rows = db.query(sql_eligible)
    data = [[r["epic_number"], r["voter_name"], r["dob"], str(r["qualifying_date"])[:10], r["booth_name"][:25], r["status"]] for r in rows]
    print_table(["EPIC", "Voter Name", "DOB", "Qualifying Date", "Polling Booth", "Status"], data)


def demo_member_2():
    print_header("Member 2 — Flask Backend & Connectivity Demonstration")
    print("[*] Demonstration: Live parameterized request modifying a database record inside a transaction.")
    
    # Inspect Voter #5 before update
    target_id = 5
    voter_before = VoterModel.get_by_id(target_id)
    print(f"[*] Target Voter #{target_id}: '{voter_before['first_name']} {voter_before['last_name']}'")
    print(f"    Current Status: '{voter_before['status']}'")

    # Transition status: Pending_Verification -> Verified
    next_status = "Verified" if voter_before["status"] != "Verified" else "Approved"
    print(f"\n>>> Executing Live Parameterized Status Transition to '{next_status}'...")
    
    ok, msg = SIRRuleEngine.transition_voter_status(
        voter_id=target_id,
        new_status=next_status,
        officer_id=1,
        remarks=f"Live terminal verification executed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print(f"    Transition Result: {msg}")

    # Inspect Voter after update
    voter_after = VoterModel.get_by_id(target_id)
    print(f"    Updated Database Status: '{voter_after['status']}'")

    # Verify audit trail insertion
    print("\n>>> Verifying StatusHistory Audit Log Insertion:")
    history = VoterModel.get_status_history(target_id)
    if history:
        latest = history[0]
        print(f"    Log Entry #{latest['history_id']}: {latest['previous_status']} -> {latest['new_status']} | Officer: {latest['officer_name']} | Remarks: {latest['remarks']}")


def demo_member_3():
    print_header("Member 3 — Business Logic & DBMS Algorithms Demonstration")

    # Rule 1: 18-Year Eligibility Check
    print("\n>>> Rule 1: 18-Year Eligibility Check (SIR Qualifying Date: 2026-01-01)")
    print("  Case 1A (PASS): DOB 2004-05-14 (Age: 21)")
    ok_1a, age_1a, msg_1a = SIRRuleEngine.check_eligibility_18yo("2004-05-14", 1)
    print(f"    Result: {'[PASS]' if ok_1a else '[FAIL]'} -> {msg_1a}")

    print("  Case 1B (FAIL): DOB 2008-05-14 (Age: 17 on 2026-01-01)")
    ok_1b, age_1b, msg_1b = SIRRuleEngine.check_eligibility_18yo("2008-05-14", 1)
    print(f"    Result: {'[PASS]' if ok_1b else '[FAIL]'} -> {msg_1b}")

    # Rule 2: Exact Duplicate Detection
    print("\n>>> Rule 2: Exact-Match Duplicate Detection (Name + DOB + Guardian)")
    print("  Case 2A (PASS): Unique applicant 'Harish Bansal', DOB 1996-03-15, Guardian 'Kishore Bansal'")
    ok_2a, _, msg_2a = SIRRuleEngine.check_duplicate_voter("Harish", "Bansal", "1996-03-15", "Kishore Bansal")
    print(f"    Result: {'[FAIL DUPLICATE]' if ok_2a else '[PASS UNIQUE]'} -> {msg_2a}")

    print("  Case 2B (FAIL): Duplicate applicant 'Aarav Sharma', DOB 2004-05-14, Guardian 'Sunita Sharma'")
    ok_2b, _, msg_2b = SIRRuleEngine.check_duplicate_voter("Aarav", "Sharma", "2004-05-14", "Sunita Sharma")
    print(f"    Result: {'[FAIL DUPLICATE]' if ok_2b else '[PASS UNIQUE]'} -> {msg_2b}")

    # Rule 3: 1,200 Polling Booth Limit
    print("\n>>> Rule 3: 1,200-Voter Polling Booth Capacity Limit")
    print("  Case 3A (PASS): Polling Booth #1 (Standard booth with open slots)")
    ok_3a, cur_3a, max_3a, msg_3a = SIRRuleEngine.check_booth_capacity_limit(1)
    print(f"    Result: {'[PASS]' if ok_3a else '[FAIL]'} -> {msg_3a}")

    print("  Case 3B (FAIL): Polling Booth at Statutory Capacity Limit (Enrolled >= Max Capacity)")
    # Temporarily set max_capacity = 1 for booth 3 (which already has 1 enrolled voter) to demonstrate failure
    db.execute_transaction([("UPDATE PollingBooth SET max_capacity = 1 WHERE booth_id = 3", ())])
    ok_3b, cur_3b, max_3b, msg_3b = SIRRuleEngine.check_booth_capacity_limit(3)
    db.execute_transaction([("UPDATE PollingBooth SET max_capacity = 5 WHERE booth_id = 3", ())])
    print(f"    Result: {'[PASS]' if ok_3b else '[FAIL (CAPACITY REACHED)]'} -> {msg_3b}")

    # Rule 4: 15-Day Appeal Window
    print("\n>>> Rule 4: 15-Day Statutory Appeal Window Validation")
    print("  Case 4A (PASS): Rejection Date 2026-01-05, Appeal Date 2026-01-12 (7 days elapsed)")
    ok_4a, days_4a, msg_4a = SIRRuleEngine.validate_appeal_window("2026-01-05", "2026-01-12")
    print(f"    Result: {'[PASS]' if ok_4a else '[FAIL]'} -> {msg_4a}")

    print("  Case 4B (FAIL): Rejection Date 2026-01-05, Appeal Date 2026-01-28 (23 days elapsed > 15 days)")
    ok_4b, days_4b, msg_4b = SIRRuleEngine.validate_appeal_window("2026-01-05", "2026-01-28")
    print(f"    Result: {'[PASS]' if ok_4b else '[FAIL]'} -> {msg_4b}")


def main():
    print("=" * 80)
    print("  SPECIAL INTENSIVE REVISION (SIR) ELECTORAL ROLL MANAGEMENT SYSTEM")
    print("  TERMINAL DEMONSTRATION SUITE")
    print("=" * 80)
    
    demo_member_1()
    demo_member_2()
    demo_member_3()
    
    print("\n" + "=" * 80)
    print("  ALL DEMONSTRATION PHASES COMPLETED SUCCESSFULLY.")
    print("=" * 80)


if __name__ == "__main__":
    main()
