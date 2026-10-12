"""Flask Application for Special Intensive Revision (SIR) Electoral Roll Management System.
Member 2: Flask Backend & Connectivity.
Member 4: Prototype Integration & End-to-End Workflow.
"""
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from config import Config
from database import db
from models import VoterModel, ElectoralMetadataModel, AppealModel
from rules import SIRRuleEngine

app = Flask(__name__)
app.config.from_object(Config)


@app.context_processor
def inject_global_data():
    """Provides active driver and common metadata to all templates."""
    return {
        "db_driver": db.driver,
        "current_year": datetime.now().year,
        "active_cycle": db.query("SELECT * FROM SIRCycle WHERE status = 'Active' LIMIT 1", fetchone=True)
    }


# =====================================================================
# 1. Main Dashboard
# =====================================================================
@app.route("/")
def index():
    # Compute dashboard statistical summaries
    stats = {
        "total_voters": db.query("SELECT COUNT(*) AS c FROM Voter", fetchone=True)["c"],
        "approved_voters": db.query("SELECT COUNT(*) AS c FROM Voter WHERE status = 'Approved'", fetchone=True)["c"],
        "pending_voters": db.query("SELECT COUNT(*) AS c FROM Voter WHERE status IN ('Submitted', 'Pending_Verification')", fetchone=True)["c"],
        "rejected_voters": db.query("SELECT COUNT(*) AS c FROM Voter WHERE status = 'Rejected'", fetchone=True)["c"],
        "under_appeal": db.query("SELECT COUNT(*) AS c FROM Voter WHERE status = 'Under_Appeal'", fetchone=True)["c"],
        "total_booths": db.query("SELECT COUNT(*) AS c FROM PollingBooth", fetchone=True)["c"],
        "total_households": db.query("SELECT COUNT(*) AS c FROM Household", fetchone=True)["c"],
    }
    
    recent_voters = VoterModel.get_all(limit=6)
    booths = ElectoralMetadataModel.get_booths_with_stats()
    
    return render_template("index.html", stats=stats, recent_voters=recent_voters, booths=booths)


# =====================================================================
# 2. Voter Search (Member 1 & Member 4)
# =====================================================================
@app.route("/search")
def search():
    query_str = request.args.get("q", "").strip()
    booth_id = request.args.get("booth_id", type=int)
    status = request.args.get("status", "").strip() or None
    constituency_id = request.args.get("constituency_id", type=int)

    results = VoterModel.search(
        search_query=query_str,
        booth_id=booth_id,
        status=status,
        constituency_id=constituency_id
    )

    booths = ElectoralMetadataModel.get_booths_with_stats()
    constituencies = ElectoralMetadataModel.get_constituencies()

    return render_template(
        "search.html",
        results=results,
        query_str=query_str,
        selected_booth=booth_id,
        selected_status=status,
        selected_constituency=constituency_id,
        booths=booths,
        constituencies=constituencies
    )


# =====================================================================
# 3. Voter Registration (Member 3 & Member 4)
# =====================================================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = {
            "first_name": request.form.get("first_name", "").strip(),
            "last_name": request.form.get("last_name", "").strip(),
            "dob": request.form.get("dob", "").strip(),
            "gender": request.form.get("gender", ""),
            "guardian_name": request.form.get("guardian_name", "").strip(),
            "guardian_relation": request.form.get("guardian_relation", ""),
            "mobile": request.form.get("mobile", "").strip(),
            "household_id": request.form.get("household_id", type=int),
            "booth_id": request.form.get("booth_id", type=int),
            "cycle_id": request.form.get("cycle_id", type=int),
        }

        success, voter_id, epic, errors = VoterModel.register_new_voter(data)
        if success:
            flash(f"Voter successfully registered! Assigned EPIC: {epic} (Application ID: #{voter_id})", "success")
            return redirect(url_for("voter_detail", voter_id=voter_id))
        else:
            for err in errors:
                flash(err, "danger")
            return render_template(
                "register.html",
                form_data=data,
                booths=ElectoralMetadataModel.get_booths_with_stats(),
                households=ElectoralMetadataModel.get_households(),
                cycles=ElectoralMetadataModel.get_active_cycles()
            )

    return render_template(
        "register.html",
        form_data={},
        booths=ElectoralMetadataModel.get_booths_with_stats(),
        households=ElectoralMetadataModel.get_households(),
        cycles=ElectoralMetadataModel.get_active_cycles()
    )


# =====================================================================
# 4. Voter Detail & Audit Trail
# =====================================================================
@app.route("/voter/<int:voter_id>")
def voter_detail(voter_id):
    voter = VoterModel.get_by_id(voter_id)
    if not voter:
        flash(f"Voter ID #{voter_id} not found.", "warning")
        return redirect(url_for("search"))

    history = VoterModel.get_status_history(voter_id)
    officers = ElectoralMetadataModel.get_officers()

    # Calculate verified age as of qualifying date
    dob = datetime.strptime(str(voter["dob"]).split(" ")[0], "%Y-%m-%d").date()
    q_date = datetime.strptime(str(voter["qualifying_date"]).split(" ")[0], "%Y-%m-%d").date()
    age = q_date.year - dob.year - ((q_date.month, q_date.day) < (dob.month, dob.day))

    return render_template(
        "voter_detail.html",
        voter=voter,
        history=history,
        officers=officers,
        age_at_qualifying=age
    )


# =====================================================================
# 5. Status Review & Verification (Member 2 Live State Change)
# =====================================================================
@app.route("/review", methods=["GET", "POST"])
def review():
    if request.method == "POST":
        voter_id = request.form.get("voter_id", type=int)
        new_status = request.form.get("new_status")
        officer_id = request.form.get("officer_id", type=int)
        remarks = request.form.get("remarks", "").strip()

        ok, msg = SIRRuleEngine.transition_voter_status(
            voter_id=voter_id,
            new_status=new_status,
            officer_id=officer_id,
            remarks=remarks
        )
        if ok:
            flash(msg, "success")
        else:
            flash(msg, "danger")

        return redirect(url_for("review"))

    pending_list = VoterModel.get_pending_voters()
    officers = ElectoralMetadataModel.get_officers()
    recent_history = db.query(
        """
        SELECT sh.*, v.epic_number, CONCAT(v.first_name, ' ', v.last_name) AS voter_name,
               o.name AS officer_name, o.designation AS officer_designation
        FROM StatusHistory sh
        JOIN Voter v ON sh.voter_id = v.voter_id
        LEFT JOIN Officer o ON sh.changed_by_officer_id = o.officer_id
        ORDER BY sh.change_date DESC
        LIMIT 10
        """
    )

    return render_template(
        "review.html",
        pending_list=pending_list,
        officers=officers,
        recent_history=recent_history
    )


# =====================================================================
# 6. Polling Booths & Capacity Monitoring (1,200 Limit)
# =====================================================================
@app.route("/booths")
def booths():
    booths_list = ElectoralMetadataModel.get_booths_with_stats()
    return render_template("booths.html", booths=booths_list)


# =====================================================================
# 7. Appeals & 15-Day Window Compliance
# =====================================================================
@app.route("/appeals", methods=["GET", "POST"])
def appeals():
    if request.method == "POST":
        voter_id = request.form.get("voter_id", type=int)
        rejection_date = request.form.get("rejection_date", "").strip()
        appeal_date = request.form.get("appeal_date", "").strip()
        reason = request.form.get("reason", "").strip()

        ok, msg = AppealModel.submit_appeal(voter_id, rejection_date, appeal_date, reason)
        if ok:
            flash(msg, "success")
        else:
            flash(msg, "danger")
        return redirect(url_for("appeals"))

    all_appeals = AppealModel.get_all()
    # Voters eligible to file appeal (Rejected or Deleted status)
    rejected_voters = db.query("SELECT voter_id, epic_number, first_name, last_name, status FROM Voter WHERE status IN ('Rejected', 'Deleted')")
    
    return render_template(
        "appeals.html",
        appeals=all_appeals,
        rejected_voters=rejected_voters,
        today_date=date.today().strftime("%Y-%m-%d")
    )


# =====================================================================
# 8. Interactive Rules & Validation Demo (Member 3 Showcase)
# =====================================================================
@app.route("/rules-demo")
def rules_demo():
    cycles = ElectoralMetadataModel.get_active_cycles()
    booths = ElectoralMetadataModel.get_booths_with_stats()
    duplicate_logs = VoterModel.get_duplicate_logs()
    
    return render_template(
        "rules_demo.html",
        cycles=cycles,
        booths=booths,
        duplicate_logs=duplicate_logs
    )


# =====================================================================
# 9. JSON API Endpoints for Live AJAX Checks
# =====================================================================
@app.route("/api/validate-age", methods=["POST"])
def api_validate_age():
    data = request.get_json() or {}
    dob = data.get("dob", "")
    cycle_id = int(data.get("cycle_id", 1))
    is_valid, age, msg = SIRRuleEngine.check_eligibility_18yo(dob, cycle_id)
    return jsonify({"valid": is_valid, "age": age, "message": msg})


@app.route("/api/validate-duplicate", methods=["POST"])
def api_validate_duplicate():
    data = request.get_json() or {}
    is_dup, match, msg = SIRRuleEngine.check_duplicate_voter(
        data.get("first_name", ""),
        data.get("last_name", ""),
        data.get("dob", ""),
        data.get("guardian_name", "")
    )
    return jsonify({"duplicate": is_dup, "matched": match, "message": msg})


@app.route("/api/validate-booth", methods=["POST"])
def api_validate_booth():
    data = request.get_json() or {}
    booth_id = int(data.get("booth_id", 1))
    has_cap, cur, max_c, msg = SIRRuleEngine.check_booth_capacity_limit(booth_id)
    return jsonify({"has_capacity": has_cap, "current_count": cur, "max_capacity": max_c, "message": msg})


@app.route("/api/validate-appeal", methods=["POST"])
def api_validate_appeal():
    data = request.get_json() or {}
    rej_date = data.get("rejection_date", "")
    app_date = data.get("appeal_date", "")
    is_valid, days, msg = SIRRuleEngine.validate_appeal_window(rej_date, app_date)
    return jsonify({"valid": is_valid, "days_elapsed": days, "message": msg})


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
