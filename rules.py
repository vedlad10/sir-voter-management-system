"""Business logic and DBMS algorithms for the SIR Electoral Roll Management System.
Member 3: Core SIR Rules and DBMS Algorithms.

Implements:
1. Exact-match duplicate detection using Name, DOB, and Guardian Name.
2. 18-year eligibility check using the active SIR qualifying date.
3. Status changes audit trail tracking in StatusHistory.
4. 1,200-voter polling booth limit enforcement.
5. 15-day appeal-window validation against rejection/deletion date.
6. Rule placement decision engine (Python vs MySQL constraints).
"""
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple
from config import Config
from database import db


def calculate_age_on_date(dob: date, reference_date: date) -> int:
    """Calculates exact completed years between DOB and reference qualifying date."""
    if dob > reference_date:
        return -1
    age = reference_date.year - dob.year
    if (reference_date.month, reference_date.day) < (dob.month, dob.day):
        age -= 1
    return age


class SIRRuleEngine:
    """Encapsulates business rules, algorithmic validations, and audit recording."""

    @staticmethod
    def check_eligibility_18yo(dob_str: str, cycle_id: int) -> Tuple[bool, int, str]:
        """Rule 1: 18-Year Eligibility Check using the SIR Cycle Qualifying Date.
        Returns: (is_eligible, calculated_age, message)
        """
        # Fetch active cycle qualifying date
        cycle = db.query(
            "SELECT cycle_name, qualifying_date FROM SIRCycle WHERE cycle_id = %s",
            (cycle_id,),
            fetchone=True
        )
        if not cycle:
            return False, 0, f"Error: SIR Cycle ID {cycle_id} not found."

        try:
            dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
        except ValueError:
            return False, 0, "Error: Invalid Date of Birth format. Expected YYYY-MM-DD."

        qualifying_date_str = str(cycle["qualifying_date"]).split(" ")[0]
        qualifying_date = datetime.strptime(qualifying_date_str, "%Y-%m-%d").date()

        age = calculate_age_on_date(dob, qualifying_date)

        if age < 0:
            return False, age, f"Validation Failed: Date of Birth ({dob}) is after qualifying date ({qualifying_date})."

        if age < Config.MINIMUM_VOTER_AGE:
            return False, age, (
                f"Validation Failed: Applicant is {age} years old on qualifying date {qualifying_date}. "
                f"Minimum required age is {Config.MINIMUM_VOTER_AGE} years under Section 19 of RPA 1950."
            )

        return True, age, (
            f"Validation Passed: Age on qualifying date ({qualifying_date}) is {age} years (>= 18)."
        )

    @staticmethod
    def check_duplicate_voter(first_name: str, last_name: str, dob_str: str, 
                              guardian_name: str, exclude_voter_id: Optional[int] = None) -> Tuple[bool, Optional[Dict], str]:
        """Rule 2: Exact-match duplicate detection using Name, DOB, and Guardian Name.
        Normalizes names and performs case-insensitive exact matching.
        Returns: (is_duplicate, matched_record, message)
        """
        norm_first = first_name.strip().lower()
        norm_last = last_name.strip().lower()
        norm_guardian = guardian_name.strip().lower()

        sql = """
            SELECT voter_id, epic_number, first_name, last_name, dob, guardian_name, status, booth_id
            FROM Voter
            WHERE LOWER(TRIM(first_name)) = %s
              AND LOWER(TRIM(last_name)) = %s
              AND dob = %s
              AND LOWER(TRIM(guardian_name)) = %s
        """
        params = [norm_first, norm_last, dob_str, norm_guardian]

        if exclude_voter_id:
            sql += " AND voter_id <> %s"
            params.append(exclude_voter_id)

        matches = db.query(sql, tuple(params))

        if matches:
            dup = matches[0]
            # Log duplicate attempt in DuplicateAudit table
            db.execute_transaction([
                ("""
                INSERT INTO DuplicateAudit (attempted_epic, matched_voter_id, matched_epic, 
                                            first_name, last_name, dob, guardian_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, ("PENDING_REG", dup["voter_id"], dup["epic_number"], 
                      first_name, last_name, dob_str, guardian_name))
            ])
            return True, dup, (
                f"Validation Failed: Exact duplicate detected! Matches existing Voter "
                f"EPIC '{dup['epic_number']}' ({dup['first_name']} {dup['last_name']}, "
                f"DOB: {dup['dob']}, Guardian: {dup['guardian_name']})."
            )

        return False, None, "Validation Passed: No duplicate voter found with identical Name, DOB, and Guardian."

    @staticmethod
    def check_booth_capacity_limit(booth_id: int) -> Tuple[bool, int, int, str]:
        """Rule 3: 1,200-Voter Polling Booth Limit Enforcement.
        Checks if booth has capacity for additional voter enrollment.
        Returns: (has_capacity, current_count, max_limit, message)
        """
        booth = db.query(
            "SELECT booth_id, booth_name, booth_number, max_capacity FROM PollingBooth WHERE booth_id = %s",
            (booth_id,),
            fetchone=True
        )
        if not booth:
            return False, 0, 0, f"Error: Polling Booth ID {booth_id} does not exist."

        # Count active/enrolled voters (excluding deleted or rejected ones)
        count_res = db.query(
            """
            SELECT COUNT(*) AS total
            FROM Voter
            WHERE booth_id = %s
              AND status IN ('Submitted', 'Pending_Verification', 'Verified', 'Approved')
            """,
            (booth_id,),
            fetchone=True
        )
        current_count = count_res["total"] if count_res else 0
        max_capacity = booth["max_capacity"]

        if current_count >= max_capacity:
            return False, current_count, max_capacity, (
                f"Validation Failed: Polling Booth '{booth['booth_name']}' (Booth #{booth['booth_number']}) "
                f"has reached its maximum statutory capacity ({current_count}/{max_capacity}). "
                f"New voters must be assigned to an auxiliary polling booth."
            )

        return True, current_count, max_capacity, (
            f"Validation Passed: Booth capacity is available ({current_count}/{max_capacity} voters enrolled)."
        )

    @staticmethod
    def validate_appeal_window(rejection_date_str: str, appeal_date_str: str) -> Tuple[bool, int, str]:
        """Rule 4: 15-Day Appeal Window Validation.
        Appeals against voter rejection or deletion must be filed within 15 calendar days.
        Returns: (is_valid, days_elapsed, message)
        """
        try:
            rejection_date = datetime.strptime(rejection_date_str, "%Y-%m-%d").date()
            appeal_date = datetime.strptime(appeal_date_str, "%Y-%m-%d").date()
        except ValueError:
            return False, -1, "Error: Invalid date format. Expected YYYY-MM-DD."

        days_elapsed = (appeal_date - rejection_date).days

        if days_elapsed < 0:
            return False, days_elapsed, (
                f"Validation Failed: Appeal date ({appeal_date}) cannot be earlier than "
                f"rejection notice date ({rejection_date})."
            )

        if days_elapsed > Config.APPEAL_WINDOW_DAYS:
            return False, days_elapsed, (
                f"Validation Failed: Appeal window expired! Appeal was submitted {days_elapsed} days "
                f"after rejection notice (Limit is {Config.APPEAL_WINDOW_DAYS} calendar days)."
            )

        return True, days_elapsed, (
            f"Validation Passed: Appeal filed within the statutory {Config.APPEAL_WINDOW_DAYS}-day window "
            f"({days_elapsed} days elapsed)."
        )

    @staticmethod
    def transition_voter_status(voter_id: int, new_status: str, 
                                officer_id: Optional[int] = None, remarks: str = "") -> Tuple[bool, str]:
        """Rule 5: Record status changes in StatusHistory audit trail.
        Executes voter update and audit logging inside an atomic transaction.
        """
        valid_statuses = [
            "Submitted", "Pending_Verification", "Verified", 
            "Approved", "Rejected", "Under_Appeal", "Deleted"
        ]
        if new_status not in valid_statuses:
            return False, f"Error: Invalid voter status '{new_status}'."

        current_voter = db.query(
            "SELECT voter_id, status FROM Voter WHERE voter_id = %s",
            (voter_id,),
            fetchone=True
        )
        if not current_voter:
            return False, f"Error: Voter ID {voter_id} does not exist."

        old_status = current_voter["status"]
        if old_status == new_status:
            return False, f"Warning: Voter is already in '{new_status}' status. No transition occurred."

        # Atomic transaction: update voter and insert into StatusHistory
        operations = [
            ("UPDATE Voter SET status = %s WHERE voter_id = %s", (new_status, voter_id)),
            ("""
             INSERT INTO StatusHistory (voter_id, previous_status, new_status, change_date, changed_by_officer_id, remarks)
             VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s, %s)
             """, (voter_id, old_status, new_status, officer_id, remarks))
        ]

        success, _, err = db.execute_transaction(operations)
        if not success:
            return False, f"Database transaction failed: {err}"

        return True, f"Success: Voter status transitioned from '{old_status}' to '{new_status}' with audit trail recorded."
