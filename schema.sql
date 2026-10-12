-- =====================================================================
-- Special Intensive Revision (SIR) Electoral Roll Management System
-- Member 1: Database & SQL Implementation
-- Target RDBMS: MySQL 8.0+ / MariaDB 10.5+
-- =====================================================================

DROP DATABASE IF EXISTS sir_electoral_db;
CREATE DATABASE sir_electoral_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE sir_electoral_db;

-- ---------------------------------------------------------------------
-- Table 1: Constituency
-- Description: Assembly/Parliamentary electoral constituency
-- ---------------------------------------------------------------------
CREATE TABLE Constituency (
    constituency_id INT AUTO_INCREMENT PRIMARY KEY,
    constituency_code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    district VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_constituency_code CHECK (LENGTH(constituency_code) >= 2)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Table 2: PollingBooth
-- Description: Polling stations under a constituency with 1,200 voter limit
-- ---------------------------------------------------------------------
CREATE TABLE PollingBooth (
    booth_id INT AUTO_INCREMENT PRIMARY KEY,
    constituency_id INT NOT NULL,
    booth_number INT NOT NULL,
    booth_name VARCHAR(150) NOT NULL,
    location VARCHAR(255) NOT NULL,
    max_capacity INT NOT NULL DEFAULT 1200,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_booth_constituency FOREIGN KEY (constituency_id) 
        REFERENCES Constituency(constituency_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT uq_constituency_booth UNIQUE (constituency_id, booth_number),
    CONSTRAINT chk_booth_capacity CHECK (max_capacity > 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Table 3: Household
-- Description: Physical address units within a polling booth area
-- ---------------------------------------------------------------------
CREATE TABLE Household (
    household_id INT AUTO_INCREMENT PRIMARY KEY,
    household_number VARCHAR(50) NOT NULL,
    booth_id INT NOT NULL,
    address_line VARCHAR(255) NOT NULL,
    pincode VARCHAR(10) NOT NULL,
    head_of_household VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_household_booth FOREIGN KEY (booth_id) 
        REFERENCES PollingBooth(booth_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT uq_booth_household UNIQUE (booth_id, household_number)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Table 4: SIRCycle
-- Description: Revision cycle metadata including qualifying date for 18yo check
-- ---------------------------------------------------------------------
CREATE TABLE SIRCycle (
    cycle_id INT AUTO_INCREMENT PRIMARY KEY,
    cycle_name VARCHAR(100) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    qualifying_date DATE NOT NULL,
    status ENUM('Upcoming', 'Active', 'Completed') NOT NULL DEFAULT 'Active',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_cycle_dates CHECK (end_date >= start_date)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Table 5: Officer
-- Description: Electoral staff (BLO, ERO, AERO) managing the revision
-- ---------------------------------------------------------------------
CREATE TABLE Officer (
    officer_id INT AUTO_INCREMENT PRIMARY KEY,
    officer_code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    designation ENUM('BLO', 'AERO', 'ERO', 'DEO', 'Admin') NOT NULL,
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    assigned_booth_id INT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_officer_booth FOREIGN KEY (assigned_booth_id) 
        REFERENCES PollingBooth(booth_id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Table 6: Voter
-- Description: Registered citizens / applicants under SIR revision
-- ---------------------------------------------------------------------
CREATE TABLE Voter (
    voter_id INT AUTO_INCREMENT PRIMARY KEY,
    epic_number VARCHAR(20) NOT NULL UNIQUE,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    dob DATE NOT NULL,
    gender ENUM('Male', 'Female', 'Other') NOT NULL,
    guardian_name VARCHAR(100) NOT NULL,
    guardian_relation ENUM('Father', 'Mother', 'Husband', 'Other') NOT NULL,
    mobile VARCHAR(15),
    household_id INT NOT NULL,
    booth_id INT NOT NULL,
    cycle_id INT NOT NULL,
    status ENUM('Submitted', 'Pending_Verification', 'Verified', 'Approved', 'Rejected', 'Under_Appeal', 'Deleted') NOT NULL DEFAULT 'Submitted',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_voter_household FOREIGN KEY (household_id) 
        REFERENCES Household(household_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_voter_booth FOREIGN KEY (booth_id) 
        REFERENCES PollingBooth(booth_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_voter_cycle FOREIGN KEY (cycle_id) 
        REFERENCES SIRCycle(cycle_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_voter_name (first_name, last_name),
    INDEX idx_voter_status (status),
    INDEX idx_voter_booth (booth_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Table 7: StatusHistory
-- Description: Comprehensive audit log tracking every voter status transition
-- ---------------------------------------------------------------------
CREATE TABLE StatusHistory (
    history_id INT AUTO_INCREMENT PRIMARY KEY,
    voter_id INT NOT NULL,
    previous_status VARCHAR(50),
    new_status VARCHAR(50) NOT NULL,
    change_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by_officer_id INT NULL,
    remarks TEXT,
    CONSTRAINT fk_history_voter FOREIGN KEY (voter_id) 
        REFERENCES Voter(voter_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_history_officer FOREIGN KEY (changed_by_officer_id) 
        REFERENCES Officer(officer_id) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX idx_history_voter (voter_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Table 8: Appeal
-- Description: Appeals filed by applicants within the 15-day appeal window
-- ---------------------------------------------------------------------
CREATE TABLE Appeal (
    appeal_id INT AUTO_INCREMENT PRIMARY KEY,
    voter_id INT NOT NULL,
    rejection_date DATE NOT NULL,
    appeal_date DATE NOT NULL,
    reason TEXT NOT NULL,
    status ENUM('Pending', 'Approved', 'Dismissed') NOT NULL DEFAULT 'Pending',
    decided_by_officer_id INT NULL,
    decision_remarks TEXT,
    decision_date DATE NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_appeal_voter FOREIGN KEY (voter_id) 
        REFERENCES Voter(voter_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_appeal_officer FOREIGN KEY (decided_by_officer_id) 
        REFERENCES Officer(officer_id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Table 9: DuplicateAudit
-- Description: Tracks flagged duplicate voter registration attempts
-- ---------------------------------------------------------------------
CREATE TABLE DuplicateAudit (
    audit_id INT AUTO_INCREMENT PRIMARY KEY,
    attempted_epic VARCHAR(20) NOT NULL,
    matched_voter_id INT NOT NULL,
    matched_epic VARCHAR(20) NOT NULL,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    dob DATE NOT NULL,
    guardian_name VARCHAR(100) NOT NULL,
    flagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_duplicate_voter FOREIGN KEY (matched_voter_id) 
        REFERENCES Voter(voter_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- =====================================================================
-- Trigger: Automatic Status Change Tracking in StatusHistory
-- =====================================================================
DELIMITER $$
CREATE TRIGGER trg_voter_status_update
AFTER UPDATE ON Voter
FOR EACH ROW
BEGIN
    IF OLD.status <> NEW.status THEN
        INSERT INTO StatusHistory (voter_id, previous_status, new_status, change_date, remarks)
        VALUES (NEW.voter_id, OLD.status, NEW.status, CURRENT_TIMESTAMP, 'Status transition via system update');
    END IF;
END$$
DELIMITER ;

-- =====================================================================
-- Sample Data Insertion
-- =====================================================================

-- 1. Insert Constituencies
INSERT INTO Constituency (constituency_code, name, district, state) VALUES
('AC-101', 'Central Capital North', 'Metro District', 'State of Ind'),
('AC-102', 'Riverfront West', 'Metro District', 'State of Ind'),
('AC-103', 'Green Valley East', 'Highland District', 'State of Ind');

-- 2. Insert Polling Booths (Includes Booth 3 with test capacity for demonstration)
INSERT INTO PollingBooth (constituency_id, booth_number, booth_name, location, max_capacity) VALUES
(1, 1, 'Govt Higher Secondary School - Wing A', 'Room 101, Main Road', 1200),
(1, 2, 'Community Center Hall', 'Sector 4, Park View', 1200),
(1, 3, 'Special Polling Station (Demo Capacity)', 'Block B, Town Hall', 5), -- Low capacity to test 1,200 limit rule in demo
(2, 1, 'Riverfront Model School', 'Riverside Road', 1200),
(3, 1, 'Valley Public Library', 'Hilltop Road', 1200);

-- 3. Insert Households
INSERT INTO Household (household_number, booth_id, address_line, pincode, head_of_household) VALUES
('H-101', 1, '42 Baker Street, Block 1', '110001', 'Robert Davis'),
('H-102', 1, '43 Baker Street, Block 1', '110001', 'Sunita Sharma'),
('H-103', 2, '12 Orchid Avenue', '110004', 'Ananya Patel'),
('H-104', 3, '50 Test Lane', '110009', 'Vikramaditya Roy'),
('H-201', 4, '88 Riverside Blvd', '110022', 'George Fernandes');

-- 4. Insert SIR Cycles (Qualifying Date 2026-01-01)
INSERT INTO SIRCycle (cycle_name, start_date, end_date, qualifying_date, status, description) VALUES
('SIR 2026 Special Revision', '2025-11-01', '2026-02-28', '2026-01-01', 'Active', 'Special Intensive Revision of Electoral Rolls with qualifying date 01-01-2026'),
('Annual Revision 2025', '2024-10-01', '2025-01-15', '2025-01-01', 'Completed', 'Annual revision cycle for calendar year 2025');

-- 5. Insert Officers
INSERT INTO Officer (officer_code, name, designation, phone, email, assigned_booth_id) VALUES
('OFF-BLO-01', 'Rajesh Verma', 'BLO', '+91 9876543210', 'rajesh.blo@election.gov.in', 1),
('OFF-BLO-02', 'Meenakshi Iyer', 'BLO', '+91 9876543211', 'meenakshi.blo@election.gov.in', 2),
('OFF-ERO-01', 'Suresh Chandra IAS', 'ERO', '+91 9876543212', 'suresh.ero@election.gov.in', 1),
('OFF-AERO-01', 'Priyanka Das', 'AERO', '+91 9876543213', 'priyanka.aero@election.gov.in', 2);

-- 6. Insert Voters with diverse statuses
INSERT INTO Voter (epic_number, first_name, last_name, dob, gender, guardian_name, guardian_relation, mobile, household_id, booth_id, cycle_id, status) VALUES
('IND9823101', 'Aarav', 'Sharma', '2004-05-14', 'Male', 'Sunita Sharma', 'Mother', '9811223344', 2, 1, 1, 'Approved'),
('IND9823102', 'Diya', 'Sharma', '2006-03-22', 'Female', 'Sunita Sharma', 'Mother', '9811223345', 2, 1, 1, 'Approved'),
('IND9823103', 'Rohan', 'Davis', '1998-11-03', 'Male', 'Robert Davis', 'Father', '9822334455', 1, 1, 1, 'Approved'),
('IND9823104', 'Kavita', 'Patel', '2005-09-18', 'Female', 'Ananya Patel', 'Mother', '9833445566', 3, 2, 1, 'Verified'),
('IND9823105', 'Amit', 'Kumar', '2007-06-25', 'Male', 'Ramesh Kumar', 'Father', '9844556677', 1, 1, 1, 'Pending_Verification'),
('IND9823106', 'Pooja', 'Roy', '2003-01-10', 'Female', 'Vikramaditya Roy', 'Father', '9855667788', 4, 3, 1, 'Submitted'),
('IND9823107', 'Manoj', 'Fernandes', '1985-04-12', 'Male', 'George Fernandes', 'Father', '9866778899', 5, 4, 1, 'Rejected'),
('IND9823108', 'Neha', 'Kapoor', '2000-08-30', 'Female', 'Raj Kapoor', 'Father', '9877889900', 3, 2, 1, 'Under_Appeal');

-- 7. Insert Initial StatusHistory Records
INSERT INTO StatusHistory (voter_id, previous_status, new_status, change_date, changed_by_officer_id, remarks) VALUES
(1, 'Submitted', 'Approved', '2025-11-15 10:00:00', 3, 'Documents verified and approved during field verification'),
(2, 'Submitted', 'Approved', '2025-11-15 10:30:00', 3, 'Eligible on qualifying date 2026-01-01'),
(3, 'Submitted', 'Approved', '2025-11-16 11:15:00', 3, 'Regular voter updated'),
(4, 'Submitted', 'Verified', '2025-12-01 14:00:00', 1, 'Physical verification completed by BLO'),
(5, 'Submitted', 'Pending_Verification', '2025-12-05 09:30:00', 1, 'Awaiting address proof verification'),
(7, 'Submitted', 'Rejected', '2026-01-10 16:00:00', 3, 'Non-resident status verified during house inquiry'),
(8, 'Approved', 'Rejected', '2026-01-05 12:00:00', 3, 'Incorrect constituency jurisdiction flagged'),
(8, 'Rejected', 'Under_Appeal', '2026-01-12 15:00:00', 4, 'Appeal filed within 7 days of rejection notice');

-- 8. Insert Sample Appeal
INSERT INTO Appeal (voter_id, rejection_date, appeal_date, reason, status, decision_remarks) VALUES
(8, '2026-01-05', '2026-01-12', 'Resident proof attached from municipal corporation showing residence in Sector 4', 'Pending', 'Under review by ERO');
