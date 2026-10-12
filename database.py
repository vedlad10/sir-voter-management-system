"""Database connection and execution manager for the SIR Electoral Roll Management System.
Member 2: Flask Backend & Connectivity.
Implements parameterized queries, transaction handling, and robust database operations.
"""
import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    MySQLError = Exception

from config import Config

class DatabaseManager:
    """Manages database connectivity, parameterized queries, and transactions."""
    
    def __init__(self):
        self.driver = None
        self._init_connection()

    def _init_connection(self):
        """Attempts MySQL connection; falls back cleanly to SQLite if MySQL is unavailable."""
        if MYSQL_AVAILABLE:
            try:
                conn = mysql.connector.connect(
                    host=Config.MYSQL_HOST,
                    user=Config.MYSQL_USER,
                    password=Config.MYSQL_PASSWORD,
                    database=Config.MYSQL_DATABASE,
                    port=Config.MYSQL_PORT,
                    connect_timeout=3
                )
                if conn.is_connected():
                    self.driver = "mysql"
                    conn.close()
                    print(f"[DatabaseManager] Connected successfully to MySQL ({Config.MYSQL_DATABASE}@{Config.MYSQL_HOST})")
                    return
            except Exception as e:
                print(f"[DatabaseManager] MySQL connection failed ({e}). Initializing SQLite engine...")
        
        self.driver = "sqlite"
        self._init_sqlite_schema()
        print(f"[DatabaseManager] Operating in SQLite mode ({Config.SQLITE_DB_PATH})")

    def _init_sqlite_schema(self):
        """Initializes SQLite schema and seeds sample records if not already populated."""
        db_path = Config.SQLITE_DB_PATH
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.executescript("""
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS Constituency (
            constituency_id INTEGER PRIMARY KEY AUTOINCREMENT,
            constituency_code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            district TEXT NOT NULL,
            state TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS PollingBooth (
            booth_id INTEGER PRIMARY KEY AUTOINCREMENT,
            constituency_id INTEGER NOT NULL,
            booth_number INTEGER NOT NULL,
            booth_name TEXT NOT NULL,
            location TEXT NOT NULL,
            max_capacity INTEGER NOT NULL DEFAULT 1200,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (constituency_id) REFERENCES Constituency(constituency_id) ON DELETE RESTRICT,
            UNIQUE(constituency_id, booth_number)
        );

        CREATE TABLE IF NOT EXISTS Household (
            household_id INTEGER PRIMARY KEY AUTOINCREMENT,
            household_number TEXT NOT NULL,
            booth_id INTEGER NOT NULL,
            address_line TEXT NOT NULL,
            pincode TEXT NOT NULL,
            head_of_household TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (booth_id) REFERENCES PollingBooth(booth_id) ON DELETE RESTRICT,
            UNIQUE(booth_id, household_number)
        );

        CREATE TABLE IF NOT EXISTS SIRCycle (
            cycle_id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle_name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            qualifying_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active',
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS Officer (
            officer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            officer_code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            designation TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            assigned_booth_id INTEGER,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assigned_booth_id) REFERENCES PollingBooth(booth_id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS Voter (
            voter_id INTEGER PRIMARY KEY AUTOINCREMENT,
            epic_number TEXT NOT NULL UNIQUE,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            dob TEXT NOT NULL,
            gender TEXT NOT NULL,
            guardian_name TEXT NOT NULL,
            guardian_relation TEXT NOT NULL,
            mobile TEXT,
            household_id INTEGER NOT NULL,
            booth_id INTEGER NOT NULL,
            cycle_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Submitted',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (household_id) REFERENCES Household(household_id) ON DELETE RESTRICT,
            FOREIGN KEY (booth_id) REFERENCES PollingBooth(booth_id) ON DELETE RESTRICT,
            FOREIGN KEY (cycle_id) REFERENCES SIRCycle(cycle_id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS StatusHistory (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            voter_id INTEGER NOT NULL,
            previous_status TEXT,
            new_status TEXT NOT NULL,
            change_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            changed_by_officer_id INTEGER,
            remarks TEXT,
            FOREIGN KEY (voter_id) REFERENCES Voter(voter_id) ON DELETE CASCADE,
            FOREIGN KEY (changed_by_officer_id) REFERENCES Officer(officer_id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS Appeal (
            appeal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            voter_id INTEGER NOT NULL,
            rejection_date TEXT NOT NULL,
            appeal_date TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            decided_by_officer_id INTEGER,
            decision_remarks TEXT,
            decision_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (voter_id) REFERENCES Voter(voter_id) ON DELETE CASCADE,
            FOREIGN KEY (decided_by_officer_id) REFERENCES Officer(officer_id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS DuplicateAudit (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempted_epic TEXT NOT NULL,
            matched_voter_id INTEGER NOT NULL,
            matched_epic TEXT NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            dob TEXT NOT NULL,
            guardian_name TEXT NOT NULL,
            flagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (matched_voter_id) REFERENCES Voter(voter_id) ON DELETE CASCADE
        );
        """)
        
        # Check if sample data exists
        cursor.execute("SELECT COUNT(*) FROM Constituency")
        if cursor.fetchone()[0] == 0:
            cursor.executescript("""
            INSERT INTO Constituency (constituency_code, name, district, state) VALUES
            ('AC-101', 'Central Capital North', 'Metro District', 'State of Ind'),
            ('AC-102', 'Riverfront West', 'Metro District', 'State of Ind'),
            ('AC-103', 'Green Valley East', 'Highland District', 'State of Ind');

            INSERT INTO PollingBooth (constituency_id, booth_number, booth_name, location, max_capacity) VALUES
            (1, 1, 'Govt Higher Secondary School - Wing A', 'Room 101, Main Road', 1200),
            (1, 2, 'Community Center Hall', 'Sector 4, Park View', 1200),
            (1, 3, 'Special Polling Station (Demo Capacity)', 'Block B, Town Hall', 5),
            (2, 1, 'Riverfront Model School', 'Riverside Road', 1200),
            (3, 1, 'Valley Public Library', 'Hilltop Road', 1200);

            INSERT INTO Household (household_number, booth_id, address_line, pincode, head_of_household) VALUES
            ('H-101', 1, '42 Baker Street, Block 1', '110001', 'Robert Davis'),
            ('H-102', 1, '43 Baker Street, Block 1', '110001', 'Sunita Sharma'),
            ('H-103', 2, '12 Orchid Avenue', '110004', 'Ananya Patel'),
            ('H-104', 3, '50 Test Lane', '110009', 'Vikramaditya Roy'),
            ('H-201', 4, '88 Riverside Blvd', '110022', 'George Fernandes');

            INSERT INTO SIRCycle (cycle_name, start_date, end_date, qualifying_date, status, description) VALUES
            ('SIR 2026 Special Revision', '2025-11-01', '2026-02-28', '2026-01-01', 'Active', 'Special Intensive Revision with qualifying date 01-01-2026'),
            ('Annual Revision 2025', '2024-10-01', '2025-01-15', '2025-01-01', 'Completed', 'Annual revision cycle for calendar year 2025');

            INSERT INTO Officer (officer_code, name, designation, phone, email, assigned_booth_id) VALUES
            ('OFF-BLO-01', 'Rajesh Verma', 'BLO', '+91 9876543210', 'rajesh.blo@election.gov.in', 1),
            ('OFF-BLO-02', 'Meenakshi Iyer', 'BLO', '+91 9876543211', 'meenakshi.blo@election.gov.in', 2),
            ('OFF-ERO-01', 'Suresh Chandra IAS', 'ERO', '+91 9876543212', 'suresh.ero@election.gov.in', 1),
            ('OFF-AERO-01', 'Priyanka Das', 'AERO', '+91 9876543213', 'priyanka.aero@election.gov.in', 2);

            INSERT INTO Voter (epic_number, first_name, last_name, dob, gender, guardian_name, guardian_relation, mobile, household_id, booth_id, cycle_id, status) VALUES
            ('IND9823101', 'Aarav', 'Sharma', '2004-05-14', 'Male', 'Sunita Sharma', 'Mother', '9811223344', 2, 1, 1, 'Approved'),
            ('IND9823102', 'Diya', 'Sharma', '2006-03-22', 'Female', 'Sunita Sharma', 'Mother', '9811223345', 2, 1, 1, 'Approved'),
            ('IND9823103', 'Rohan', 'Davis', '1998-11-03', 'Male', 'Robert Davis', 'Father', '9822334455', 1, 1, 1, 'Approved'),
            ('IND9823104', 'Kavita', 'Patel', '2005-09-18', 'Female', 'Ananya Patel', 'Mother', '9833445566', 3, 2, 1, 'Verified'),
            ('IND9823105', 'Amit', 'Kumar', '2007-06-25', 'Male', 'Ramesh Kumar', 'Father', '9844556677', 1, 1, 1, 'Pending_Verification'),
            ('IND9823106', 'Pooja', 'Roy', '2003-01-10', 'Female', 'Vikramaditya Roy', 'Father', '9855667788', 4, 3, 1, 'Submitted'),
            ('IND9823107', 'Manoj', 'Fernandes', '1985-04-12', 'Male', 'George Fernandes', 'Father', '9866778899', 5, 4, 1, 'Rejected'),
            ('IND9823108', 'Neha', 'Kapoor', '2000-08-30', 'Female', 'Raj Kapoor', 'Father', '9877889900', 3, 2, 1, 'Under_Appeal');

            INSERT INTO StatusHistory (voter_id, previous_status, new_status, change_date, changed_by_officer_id, remarks) VALUES
            (1, 'Submitted', 'Approved', '2025-11-15 10:00:00', 3, 'Documents verified and approved during field verification'),
            (2, 'Submitted', 'Approved', '2025-11-15 10:30:00', 3, 'Eligible on qualifying date 2026-01-01'),
            (3, 'Submitted', 'Approved', '2025-11-16 11:15:00', 3, 'Regular voter updated'),
            (4, 'Submitted', 'Verified', '2025-12-01 14:00:00', 1, 'Physical verification completed by BLO'),
            (5, 'Submitted', 'Pending_Verification', '2025-12-05 09:30:00', 1, 'Awaiting address proof verification'),
            (7, 'Submitted', 'Rejected', '2026-01-10 16:00:00', 3, 'Non-resident status verified during house inquiry'),
            (8, 'Approved', 'Rejected', '2026-01-05 12:00:00', 3, 'Incorrect constituency jurisdiction flagged'),
            (8, 'Rejected', 'Under_Appeal', '2026-01-12 15:00:00', 4, 'Appeal filed within 7 days of rejection notice');

            INSERT INTO Appeal (voter_id, rejection_date, appeal_date, reason, status, decision_remarks) VALUES
            (8, '2026-01-05', '2026-01-12', 'Resident proof attached from municipal corporation showing residence in Sector 4', 'Pending', 'Under review by ERO');
            """)
            conn.commit()
            
        conn.close()

    def get_connection(self):
        """Returns an active raw connection with dictionary-like row access."""
        if self.driver == "mysql":
            return mysql.connector.connect(
                host=Config.MYSQL_HOST,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=Config.MYSQL_DATABASE,
                port=Config.MYSQL_PORT
            )
        else:
            conn = sqlite3.connect(Config.SQLITE_DB_PATH)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            
            # Register MySQL-compatible SQL functions in SQLite
            conn.create_function("CONCAT", -1, lambda *args: "".join(str(a) for a in args if a is not None))
            
            def _datediff(d1, d2):
                from datetime import datetime
                try:
                    dt1 = datetime.strptime(str(d1).split()[0], "%Y-%m-%d")
                    dt2 = datetime.strptime(str(d2).split()[0], "%Y-%m-%d")
                    return (dt1 - dt2).days
                except Exception:
                    return 0
            conn.create_function("DATEDIFF", 2, _datediff)

            def _timestampdiff(unit, d1, d2):
                from datetime import datetime
                try:
                    dt1 = datetime.strptime(str(d1).split()[0], "%Y-%m-%d")
                    dt2 = datetime.strptime(str(d2).split()[0], "%Y-%m-%d")
                    if str(unit).upper() == "YEAR":
                        return dt2.year - dt1.year - ((dt2.month, dt2.day) < (dt1.month, dt1.day))
                    return (dt2 - dt1).days
                except Exception:
                    return 0
            conn.create_function("TIMESTAMPDIFF", 3, _timestampdiff)
            
            return conn

    def query(self, sql: str, params: Union[Tuple, List] = (), fetchone: bool = False) -> Any:
        """Executes a parameterized SELECT query and returns dictionary rows.
        Guarantees SQL injection safety via parameter binding.
        """
        conn = self.get_connection()
        try:
            if self.driver == "mysql":
                cursor = conn.cursor(dictionary=True)
                cursor.execute(sql, params)
                res = cursor.fetchone() if fetchone else cursor.fetchall()
                cursor.close()
                return res
            else:
                # SQLite parameterized query syntax uses ? placeholder
                # Convert %s placeholder if present in MySQL-style query
                sql_sqlite = sql.replace("%s", "?")
                cursor = conn.cursor()
                cursor.execute(sql_sqlite, params)
                if fetchone:
                    row = cursor.fetchone()
                    res = dict(row) if row else None
                else:
                    res = [dict(row) for row in cursor.fetchall()]
                cursor.close()
                return res
        finally:
            conn.close()

    def execute_transaction(self, operations: List[Tuple[str, Tuple]]) -> Tuple[bool, Optional[int], Optional[str]]:
        """Executes multiple parameterized statements inside a single transaction.
        Commits on success; rolls back entirely on failure.
        Returns: (success, last_inserted_id, error_message)
        """
        conn = self.get_connection()
        last_id = None
        try:
            if self.driver == "mysql":
                cursor = conn.cursor()
                for sql, params in operations:
                    cursor.execute(sql, params)
                    if cursor.lastrowid:
                        last_id = cursor.lastrowid
                conn.commit()
                cursor.close()
                return True, last_id, None
            else:
                cursor = conn.cursor()
                for sql, params in operations:
                    sql_sqlite = sql.replace("%s", "?")
                    cursor.execute(sql_sqlite, params)
                    if cursor.lastrowid:
                        last_id = cursor.lastrowid
                conn.commit()
                cursor.close()
                return True, last_id, None
        except Exception as e:
            conn.rollback()
            return False, None, str(e)
        finally:
            conn.close()


# Global DB instance
db = DatabaseManager()
