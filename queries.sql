-- =====================================================================
-- Special Intensive Revision (SIR) Electoral Roll Management System
-- Member 1: Core SQL Queries for Electoral Administration
-- =====================================================================
USE sir_electoral_db;

-- ---------------------------------------------------------------------
-- 1. Voter Search Query (Parameterized Example)
-- Searches voters across name, EPIC, booth, constituency, and status
-- ---------------------------------------------------------------------
SELECT 
    v.voter_id,
    v.epic_number,
    CONCAT(v.first_name, ' ', v.last_name) AS full_name,
    v.dob,
    v.gender,
    v.guardian_name,
    v.guardian_relation,
    v.mobile,
    v.status,
    pb.booth_number,
    pb.booth_name,
    c.name AS constituency_name,
    h.address_line,
    h.pincode
FROM Voter v
JOIN PollingBooth pb ON v.booth_id = pb.booth_id
JOIN Constituency c ON pb.constituency_id = c.constituency_id
JOIN Household h ON v.household_id = h.household_id
WHERE (v.first_name LIKE '%Aarav%' OR v.last_name LIKE '%Aarav%' OR v.epic_number = 'IND9823101')
ORDER BY v.last_name, v.first_name;

-- ---------------------------------------------------------------------
-- 2. Pending Voters Query
-- Retrieves all applications requiring field verification or approval
-- ---------------------------------------------------------------------
SELECT 
    v.voter_id,
    v.epic_number,
    CONCAT(v.first_name, ' ', v.last_name) AS applicant_name,
    v.dob,
    TIMESTAMPDIFF(YEAR, v.dob, sc.qualifying_date) AS age_at_qualifying_date,
    v.status,
    pb.booth_name,
    o.name AS assigned_blo_name,
    o.phone AS blo_contact,
    v.created_at
FROM Voter v
JOIN PollingBooth pb ON v.booth_id = pb.booth_id
JOIN SIRCycle sc ON v.cycle_id = sc.cycle_id
LEFT JOIN Officer o ON pb.booth_id = o.assigned_booth_id AND o.designation = 'BLO'
WHERE v.status IN ('Submitted', 'Pending_Verification')
ORDER BY v.created_at ASC;

-- ---------------------------------------------------------------------
-- 3. Eligible Voters Query
-- Eligible voters: age >= 18 on active SIR qualifying date with Approved status
-- ---------------------------------------------------------------------
SELECT 
    v.voter_id,
    v.epic_number,
    CONCAT(v.first_name, ' ', v.last_name) AS voter_name,
    v.dob,
    sc.qualifying_date,
    TIMESTAMPDIFF(YEAR, v.dob, sc.qualifying_date) AS verified_age,
    v.gender,
    v.guardian_name,
    pb.booth_number,
    pb.booth_name,
    c.name AS constituency_name,
    v.status
FROM Voter v
JOIN SIRCycle sc ON v.cycle_id = sc.cycle_id
JOIN PollingBooth pb ON v.booth_id = pb.booth_id
JOIN Constituency c ON pb.constituency_id = c.constituency_id
WHERE v.status = 'Approved'
  AND TIMESTAMPDIFF(YEAR, v.dob, sc.qualifying_date) >= 18
ORDER BY pb.booth_number, v.last_name;

-- ---------------------------------------------------------------------
-- 4. Polling Booth Capacity Monitoring (1,200 Limit Verification)
-- ---------------------------------------------------------------------
SELECT 
    pb.booth_id,
    pb.booth_number,
    pb.booth_name,
    c.name AS constituency_name,
    pb.max_capacity,
    COUNT(v.voter_id) AS total_enrolled_voters,
    (pb.max_capacity - COUNT(v.voter_id)) AS remaining_capacity,
    CASE 
        WHEN COUNT(v.voter_id) >= pb.max_capacity THEN 'CAPACITY_REACHED'
        WHEN COUNT(v.voter_id) >= (pb.max_capacity * 0.9) THEN 'WARNING_NEAR_LIMIT'
        ELSE 'AVAILABLE'
    END AS capacity_status
FROM PollingBooth pb
JOIN Constituency c ON pb.constituency_id = c.constituency_id
LEFT JOIN Voter v ON pb.booth_id = v.booth_id AND v.status IN ('Approved', 'Verified', 'Submitted', 'Pending_Verification')
GROUP BY pb.booth_id, pb.booth_number, pb.booth_name, c.name, pb.max_capacity
ORDER BY total_enrolled_voters DESC;

-- ---------------------------------------------------------------------
-- 5. Audit Trail Query (Status Transitions via StatusHistory)
-- ---------------------------------------------------------------------
SELECT 
    sh.history_id,
    v.epic_number,
    CONCAT(v.first_name, ' ', v.last_name) AS voter_name,
    sh.previous_status,
    sh.new_status,
    sh.change_date,
    COALESCE(o.name, 'System Process') AS changed_by,
    COALESCE(o.designation, 'Auto') AS officer_role,
    sh.remarks
FROM StatusHistory sh
JOIN Voter v ON sh.voter_id = v.voter_id
LEFT JOIN Officer o ON sh.changed_by_officer_id = o.officer_id
ORDER BY sh.change_date DESC;

-- ---------------------------------------------------------------------
-- 6. Duplicate Detection Query
-- Identifies voters sharing exact Name, Date of Birth, and Guardian Name
-- ---------------------------------------------------------------------
SELECT 
    LOWER(CONCAT(v.first_name, ' ', v.last_name)) AS normalized_name,
    v.dob,
    LOWER(v.guardian_name) AS normalized_guardian,
    COUNT(*) AS occurrence_count,
    GROUP_CONCAT(v.epic_number ORDER BY v.voter_id SEPARATOR ', ') AS duplicate_epics,
    GROUP_CONCAT(v.status ORDER BY v.voter_id SEPARATOR ', ') AS statuses
FROM Voter v
GROUP BY 
    LOWER(CONCAT(v.first_name, ' ', v.last_name)),
    v.dob,
    LOWER(v.guardian_name)
HAVING COUNT(*) > 1;

-- ---------------------------------------------------------------------
-- 7. 15-Day Appeal Window Compliance Query
-- ---------------------------------------------------------------------
SELECT 
    a.appeal_id,
    v.epic_number,
    CONCAT(v.first_name, ' ', v.last_name) AS applicant_name,
    a.rejection_date,
    a.appeal_date,
    DATEDIFF(a.appeal_date, a.rejection_date) AS days_elapsed,
    CASE 
        WHEN DATEDIFF(a.appeal_date, a.rejection_date) <= 15 THEN 'VALID_WITHIN_WINDOW'
        ELSE 'INVALID_WINDOW_EXPIRED'
    END AS window_compliance,
    a.status AS appeal_status,
    a.reason
FROM Appeal a
JOIN Voter v ON a.voter_id = v.voter_id;
