"""Data models and operations layer for the SIR Electoral Roll Management System.
Member 2 & 4: Flask backend logic, data retrieval, and record persistence.
"""
import random
import string
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple
from database import db
from rules import SIRRuleEngine


def generate_epic_number() -> str:
    """Generates a realistic statutory Election Photo Identity Card (EPIC) number."""
    prefix = "IND"
    digits = "".join(random.choices(string.digits, k=7))
    return f"{prefix}{digits}"


class VoterModel:
    """Encapsulates voter data access and workflow coordination."""

    @staticmethod
    def get_all(limit: int = 100) -> List[Dict]:
        sql = """
            SELECT v.*, pb.booth_name, pb.booth_number, c.name AS constituency_name, h.address_line
            FROM Voter v
            JOIN PollingBooth pb ON v.booth_id = pb.booth_id
            JOIN Constituency c ON pb.constituency_id = c.constituency_id
            JOIN Household h ON v.household_id = h.household_id
            ORDER BY v.voter_id DESC
            LIMIT %s
        """
        return db.query(sql, (limit,))

    @staticmethod
    def get_by_id(voter_id: int) -> Optional[Dict]:
        sql = """
            SELECT v.*, pb.booth_name, pb.booth_number, pb.max_capacity,
                   c.name AS constituency_name, c.district, c.state,
                   h.address_line, h.pincode, h.household_number,
                   sc.cycle_name, sc.qualifying_date
            FROM Voter v
            JOIN PollingBooth pb ON v.booth_id = pb.booth_id
            JOIN Constituency c ON pb.constituency_id = c.constituency_id
            JOIN Household h ON v.household_id = h.household_id
            JOIN SIRCycle sc ON v.cycle_id = sc.cycle_id
            WHERE v.voter_id = %s
        """
        return db.query(sql, (voter_id,), fetchone=True)

    @staticmethod
    def search(search_query: str = "", booth_id: Optional[int] = None, 
               status: Optional[str] = None, constituency_id: Optional[int] = None) -> List[Dict]:
        """Parameterized search across multiple voter attributes."""
        sql = """
            SELECT v.voter_id, v.epic_number, v.first_name, v.last_name, 
                   v.dob, v.gender, v.guardian_name, v.guardian_relation, 
                   v.mobile, v.status, pb.booth_number, pb.booth_name, 
                   c.name AS constituency_name, h.address_line
            FROM Voter v
            JOIN PollingBooth pb ON v.booth_id = pb.booth_id
            JOIN Constituency c ON pb.constituency_id = c.constituency_id
            JOIN Household h ON v.household_id = h.household_id
            WHERE 1=1
        """
        params = []

        if search_query:
            sql += """ AND (
                LOWER(v.first_name) LIKE %s 
                OR LOWER(v.last_name) LIKE %s 
                OR LOWER(v.epic_number) LIKE %s
                OR LOWER(v.guardian_name) LIKE %s
                OR LOWER(h.address_line) LIKE %s
            )"""
            term = f"%{search_query.strip().lower()}%"
            params.extend([term, term, term, term, term])

        if booth_id:
            sql += " AND v.booth_id = %s"
            params.append(booth_id)

        if status:
            sql += " AND v.status = %s"
            params.append(status)

        if constituency_id:
            sql += " AND pb.constituency_id = %s"
            params.append(constituency_id)

        sql += " ORDER BY v.voter_id DESC"
        return db.query(sql, tuple(params))

    @staticmethod
    def get_pending_voters() -> List[Dict]:
        """Retrieves applicants awaiting verification or approval."""
        sql = """
            SELECT v.voter_id, v.epic_number, v.first_name, v.last_name, v.dob,
                   v.gender, v.guardian_name, v.status, v.created_at,
                   pb.booth_name, pb.booth_number, c.name AS constituency_name,
                   sc.qualifying_date
            FROM Voter v
            JOIN PollingBooth pb ON v.booth_id = pb.booth_id
            JOIN Constituency c ON pb.constituency_id = c.constituency_id
            JOIN SIRCycle sc ON v.cycle_id = sc.cycle_id
            WHERE v.status IN ('Submitted', 'Pending_Verification')
            ORDER BY v.created_at ASC
        """
        return db.query(sql)

    @staticmethod
    def get_eligible_voters(cycle_id: Optional[int] = None) -> List[Dict]:
        """Retrieves verified voters who satisfy age >= 18 on the qualifying date."""
        sql = """
            SELECT v.voter_id, v.epic_number, v.first_name, v.last_name, v.dob,
                   v.gender, v.guardian_name, v.status, pb.booth_name, pb.booth_number,
                   c.name AS constituency_name, sc.qualifying_date
            FROM Voter v
            JOIN PollingBooth pb ON v.booth_id = pb.booth_id
            JOIN Constituency c ON pb.constituency_id = c.constituency_id
            JOIN SIRCycle sc ON v.cycle_id = sc.cycle_id
            WHERE v.status = 'Approved'
        """
        params = []
        if cycle_id:
            sql += " AND v.cycle_id = %s"
            params.append(cycle_id)

        sql += " ORDER BY pb.booth_number, v.last_name"
        rows = db.query(sql, tuple(params))

        # Filter strictly by qualifying date age >= 18
        eligible = []
        for r in rows:
            dob = datetime.strptime(str(r["dob"]).split(" ")[0], "%Y-%m-%d").date()
            q_date = datetime.strptime(str(r["qualifying_date"]).split(" ")[0], "%Y-%m-%d").date()
            age = q_date.year - dob.year - ((q_date.month, q_date.day) < (dob.month, dob.day))
            r["verified_age"] = age
            if age >= 18:
                eligible.append(r)
        return eligible

    @staticmethod
    def register_new_voter(data: Dict[str, Any]) -> Tuple[bool, Optional[int], Optional[str], List[str]]:
        """Registers a new voter after validating all Member 3 rules:
        - 18yo eligibility check using SIR qualifying date
        - Exact-match duplicate detection (Name, DOB, Guardian)
        - 1,200 booth capacity limit check
        Returns: (success, voter_id, epic_number, error_messages)
        """
        errors = []

        # 1. 18-Year Age Check
        is_eligible, calculated_age, age_msg = SIRRuleEngine.check_eligibility_18yo(
            data["dob"], int(data["cycle_id"])
        )
        if not is_eligible:
            errors.append(age_msg)

        # 2. Duplicate Check
        is_dup, _, dup_msg = SIRRuleEngine.check_duplicate_voter(
            data["first_name"], data["last_name"], data["dob"], data["guardian_name"]
        )
        if is_dup:
            errors.append(dup_msg)

        # 3. Booth Capacity Check
        has_capacity, _, _, cap_msg = SIRRuleEngine.check_booth_capacity_limit(
            int(data["booth_id"])
        )
        if not has_capacity:
            errors.append(cap_msg)

        if errors:
            return False, None, None, errors

        # Generate unique EPIC number
        epic = generate_epic_number()

        # Atomic transaction: Insert Voter and initial StatusHistory
        insert_voter_sql = """
            INSERT INTO Voter (
                epic_number, first_name, last_name, dob, gender,
                guardian_name, guardian_relation, mobile,
                household_id, booth_id, cycle_id, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        voter_params = (
            epic, data["first_name"].strip(), data["last_name"].strip(),
            data["dob"], data["gender"], data["guardian_name"].strip(),
            data["guardian_relation"], data.get("mobile", ""),
            int(data["household_id"]), int(data["booth_id"]),
            int(data["cycle_id"]), "Submitted"
        )

        conn = db.get_connection()
        try:
            if db.driver == "mysql":
                cursor = conn.cursor()
                cursor.execute(insert_voter_sql, voter_params)
                voter_id = cursor.lastrowid
                
                # Initial audit trail
                history_sql = """
                    INSERT INTO StatusHistory (voter_id, previous_status, new_status, remarks)
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(history_sql, (voter_id, None, "Submitted", "Initial online application submitted"))
                conn.commit()
                cursor.close()
            else:
                cursor = conn.cursor()
                cursor.execute(insert_voter_sql.replace("%s", "?"), voter_params)
                voter_id = cursor.lastrowid
                
                history_sql = """
                    INSERT INTO StatusHistory (voter_id, previous_status, new_status, remarks)
                    VALUES (?, ?, ?, ?)
                """
                cursor.execute(history_sql, (voter_id, None, "Submitted", "Initial online application submitted"))
                conn.commit()
                cursor.close()

            return True, voter_id, epic, []
        except Exception as e:
            conn.rollback()
            return False, None, None, [f"Database write error: {str(e)}"]
        finally:
            conn.close()

    @staticmethod
    def get_status_history(voter_id: int) -> List[Dict]:
        sql = """
            SELECT sh.*, o.name AS officer_name, o.designation AS officer_designation
            FROM StatusHistory sh
            LEFT JOIN Officer o ON sh.changed_by_officer_id = o.officer_id
            WHERE sh.voter_id = %s
            ORDER BY sh.change_date DESC
        """
        return db.query(sql, (voter_id,))

    @staticmethod
    def get_duplicate_logs() -> List[Dict]:
        sql = """
            SELECT da.*, v.status AS matched_status
            FROM DuplicateAudit da
            JOIN Voter v ON da.matched_voter_id = v.voter_id
            ORDER BY da.flagged_at DESC
        """
        return db.query(sql)


class ElectoralMetadataModel:
    """Retrieves operational reference lists (Booths, Households, Cycles, Officers)."""

    @staticmethod
    def get_constituencies() -> List[Dict]:
        return db.query("SELECT * FROM Constituency ORDER BY constituency_code")

    @staticmethod
    def get_booths_with_stats() -> List[Dict]:
        sql = """
            SELECT pb.booth_id, pb.booth_number, pb.booth_name, pb.location, pb.max_capacity,
                   c.name AS constituency_name, c.constituency_code,
                   COUNT(CASE WHEN v.status IN ('Submitted', 'Pending_Verification', 'Verified', 'Approved') THEN 1 END) AS enrolled_voters,
                   (pb.max_capacity - COUNT(CASE WHEN v.status IN ('Submitted', 'Pending_Verification', 'Verified', 'Approved') THEN 1 END)) AS slots_remaining
            FROM PollingBooth pb
            JOIN Constituency c ON pb.constituency_id = c.constituency_id
            LEFT JOIN Voter v ON pb.booth_id = v.booth_id
            GROUP BY pb.booth_id, pb.booth_number, pb.booth_name, pb.location, pb.max_capacity, c.name, c.constituency_code
            ORDER BY pb.booth_number
        """
        return db.query(sql)

    @staticmethod
    def get_households(booth_id: Optional[int] = None) -> List[Dict]:
        sql = "SELECT h.*, pb.booth_name FROM Household h JOIN PollingBooth pb ON h.booth_id = pb.booth_id"
        params = []
        if booth_id:
            sql += " WHERE h.booth_id = %s"
            params.append(booth_id)
        sql += " ORDER BY h.household_number"
        return db.query(sql, tuple(params))

    @staticmethod
    def get_active_cycles() -> List[Dict]:
        return db.query("SELECT * FROM SIRCycle ORDER BY start_date DESC")

    @staticmethod
    def get_officers() -> List[Dict]:
        return db.query("SELECT * FROM Officer WHERE is_active = 1 ORDER BY designation, name")


class AppealModel:
    """Handles statutory appeal filing and 15-day validation."""

    @staticmethod
    def get_all() -> List[Dict]:
        sql = """
            SELECT a.*, v.epic_number, v.first_name, v.last_name, v.status AS voter_current_status,
                   o.name AS deciding_officer_name
            FROM Appeal a
            JOIN Voter v ON a.voter_id = v.voter_id
            LEFT JOIN Officer o ON a.decided_by_officer_id = o.officer_id
            ORDER BY a.created_at DESC
        """
        return db.query(sql)

    @staticmethod
    def submit_appeal(voter_id: int, rejection_date: str, appeal_date: str, reason: str) -> Tuple[bool, str]:
        # Validate 15-day window
        is_valid, days, msg = SIRRuleEngine.validate_appeal_window(rejection_date, appeal_date)
        if not is_valid:
            return False, msg

        # Execute appeal insertion and transition voter status to 'Under_Appeal'
        insert_appeal = """
            INSERT INTO Appeal (voter_id, rejection_date, appeal_date, reason, status)
            VALUES (%s, %s, %s, %s, 'Pending')
        """
        update_voter = "UPDATE Voter SET status = 'Under_Appeal' WHERE voter_id = %s"
        log_history = """
            INSERT INTO StatusHistory (voter_id, previous_status, new_status, remarks)
            VALUES (%s, 'Rejected', 'Under_Appeal', %s)
        """
        remarks = f"Appeal filed within statutory window ({days} days elapsed). Reason: {reason[:100]}"

        success, _, err = db.execute_transaction([
            (insert_appeal, (voter_id, rejection_date, appeal_date, reason)),
            (update_voter, (voter_id,)),
            (log_history, (voter_id, remarks))
        ])

        if not success:
            return False, f"Database transaction failed: {err}"
        return True, f"Success: Appeal lodged successfully within 15-day window ({days} days elapsed)."
