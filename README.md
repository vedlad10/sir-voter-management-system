# Special Intensive Revision (SIR) Electoral Roll Management System

A production-grade Electoral Roll Management and Revision web application built for the **Special Intensive Revision (SIR)** process. Designed and implemented across four distinct database engineering and application roles.

---

## Project Architecture & Team Ownership

###  Member 1 — Database & SQL Implementation
- **Schema Design & Relationships**: MySQL relational schema modeling `Constituency`, `PollingBooth`, `Household`, `Voter`, `Officer`, `SIRCycle`, `StatusHistory`, `Appeal`, and `DuplicateAudit`.
- **Integrity & Constraints**: Composite unique keys, foreign keys (`ON DELETE RESTRICT` / `CASCADE`), check constraints, and enumeration states (`PENDING`, `VERIFIED`, `APPROVED`, `REJECTED`, `FLAGGED_DUPLICATE`, `APPEAL_SUBMITTED`).
- **Normalized Data Architecture**: Normalized from unnormalized registration logs to **3NF / BCNF**, isolating transitivity (e.g. booth capacity attributes and address lookups).
- **Core SQL Queries**: Analytical queries in [`queries.sql`](./queries.sql) for voter lookups, pending verification queues, qualifying-date age calculations, and booth ceiling audits.

### Member 2 — Flask Backend & Member
- **Python Application Layer**: Structured Flask application ([`app.py`](./app.py)) with context processors and modular data services ([`models.py`](./models.py)).
- **Database Connection Manager**: High-reliability `DatabaseManager` in [`database.py`](./database.py) using `mysql-connector-python` with connection pooling, dictionary cursors, and an automatic SQLite fallback for offline demonstrations.
- **Security & Parameterization**: 100% parameterized SQL execution eliminating SQL injection vulnerabilities.
- **Transaction Safety**: Context-managed atomic units of work (`execute_transaction`) with automatic commit and rollback on failure.

###  Member 3 — Business Logic & DBMS Algorithms
- **Statutory SIR Rules Engine**: Implemented in [`rules.py`](./rules.py):
  1. **Exact-Match Duplicate Detection**: Composite matching on `(normalized_name, dob, normalized_guardian)`.
  2. **18-Year Age Qualification**: Exact age determination evaluated strictly on the SIR cycle's `qualifying_date`.
  3. **Polling Booth Hard Ceiling**: Strict enforcement of the 1,200-voter capacity ceiling per booth.
  4. **15-Day Appeal Window**: Temporal validation enforcing statutory deadlines from rejection date.
  5. **Status Audit Logging**: Complete chronological transition history stored in `StatusHistory`.
- **Enforcement Partitioning Strategy**: Clear architectural demarcation between DBMS constraints/triggers vs. application-layer rules.

### Member 4 — Prototype Integration & Testing
- **Unified Web Interface**: Responsive interface styled with modern glassmorphism design tokens in [`static/css/style.css`](./static/css/style.css).
- **Interactive Pages**:
  - **Dashboard**: High-level metrics, SIR cycle status, and recent activity.
  - **Voter Search**: Real-time filtering by EPIC number, name, and status.
  - **Form 6 Registration**: Voter registration form with live AJAX pre-validation.
  - **Officer Review Queue**: Verification workflow with single-click approve, flag, and reject actions.
  - **Polling Booth Monitor**: Visual progress bars tracking capacity thresholds against the 1,200-voter limit.
  - **Appeals Workflow**: Appeal submission with automatic 15-day eligibility checks.
  - **Interactive Rules Sandbox**: Live demonstration module testing both **passing** and **failing** rule scenarios.
- **Automated Test Suite**: 16 unit tests covering all components in [`test_system.py`](./test_system.py).
- **Interactive CLI Demo**: [`demo_cli.py`](./demo_cli.py) demonstrating all member deliverables directly in terminal.

---

## Quick Start Guide

### 1. Prerequisites
- Python 3.10+
- (Optional) MySQL 8.0+ (the system seamlessly uses SQLite if MySQL is not running)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/vedlad10/sir-voter-management-system.git
cd sir-voter-management-system

# Install dependencies
pip install -r requirements.txt
```

### 3. Running the Web Application
```bash
python app.py
```
Open your browser and naviganavigatto*`http://127.0.0.1:5000`**

### 4. Running the CLI Verification & Demos
```bash
# Run interactive CLI demonstrating Member 1-4 outputs and rule validations
python demo_cli.py

# Run the automated test suite (16 tests)
python -m unittest test_system.py -v
```

---

## Repository Structure

```
sir-voter-management-system/
├── app.py                  # Flask web application & API routes
├── config.py               # Database and statutory business rules configuration
├── database.py             # Dual-engine connection manager (MySQL + SQLite)
├── models.py               # Data access layer and database transactions
├── rules.py                # SIR statutory business rules engine
├── schema.sql              # MySQL DDL, constraints, triggers, and seed records
├── queries.sql             # SQL query scripts for Member 1 deliverables
├── demo_cli.py             # Interactive CLI demonstration tool
├── test_system.py          # Automated test suite (16 tests)
├── requirements.txt        # Python package dependencies
├── docs/
│   └── PROJECT_REPORT.md   # Comprehensive report, ER diagrams & normalization
├── static/
│   ├── css/style.css       # Custom design system (vanilla CSS)
│   └── js/app.js           # Client-side AJAX validation & interactivity
└── templates/              # Jinja2 HTML templates
    ├── base.html
    ├── index.html
    ├── search.html
    ├── register.html
    ├── voter_detail.html
    ├── review.html
    ├── booths.html
    ├── appeals.html
    └── rules_demo.html
```

---

##  License
Academic / Coursework Project Submission.
