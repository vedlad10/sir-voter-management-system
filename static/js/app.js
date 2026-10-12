/**
 * Front-end interactivity and instant validation for SIR Electoral Roll System.
 * Member 4: Integration and Dynamic Client Logic.
 */

document.addEventListener("DOMContentLoaded", function () {
    // 1. Live Age Validation on DOB change in registration form
    const dobInput = document.getElementById("reg_dob");
    const cycleSelect = document.getElementById("reg_cycle");
    const ageFeedback = document.getElementById("age_feedback");

    if (dobInput && cycleSelect && ageFeedback) {
        const checkAge = async () => {
            const dob = dobInput.value;
            const cycleId = cycleSelect.value;
            if (!dob) return;

            try {
                const res = await fetch("/api/validate-age", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ dob: dob, cycle_id: cycleId })
                });
                const data = await res.json();
                
                if (data.valid) {
                    ageFeedback.innerHTML = `<span style="color: var(--success); font-size: 0.82rem;">✓ Verified: Age is ${data.age} years on qualifying date.</span>`;
                } else {
                    ageFeedback.innerHTML = `<span style="color: var(--danger); font-size: 0.82rem;">⚠ ${data.message}</span>`;
                }
            } catch (err) {
                console.error("Age validation error", err);
            }
        };

        dobInput.addEventListener("change", checkAge);
        cycleSelect.addEventListener("change", checkAge);
    }

    // 2. Live Booth Capacity Check on Booth Selection
    const boothSelect = document.getElementById("reg_booth");
    const boothFeedback = document.getElementById("booth_feedback");

    if (boothSelect && boothFeedback) {
        boothSelect.addEventListener("change", async function () {
            const boothId = boothSelect.value;
            if (!boothId) return;

            try {
                const res = await fetch("/api/validate-booth", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ booth_id: boothId })
                });
                const data = await res.json();

                if (data.has_capacity) {
                    boothFeedback.innerHTML = `<span style="color: var(--text-secondary); font-size: 0.82rem;">Enrolled: ${data.current_count} / ${data.max_capacity} voters</span>`;
                } else {
                    boothFeedback.innerHTML = `<span style="color: var(--danger); font-weight: 600; font-size: 0.82rem;">⚠ Capacity Reached: ${data.current_count} / ${data.max_capacity}!</span>`;
                }
            } catch (err) {
                console.error("Booth check error", err);
            }
        });
    }
});

// Interactive Rule Demo Test Runners (for Member 3 Showcase)
async function testRuleAge(dob, cycleId, outputElId) {
    const el = document.getElementById(outputElId);
    el.innerHTML = "<em>Calculating...</em>";
    const res = await fetch("/api/validate-age", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dob, cycle_id: cycleId })
    });
    const d = await res.json();
    el.innerHTML = `<div class="alert ${d.valid ? 'alert-success' : 'alert-danger'}">${d.message}</div>`;
}

async function testRuleDuplicate(first_name, last_name, dob, guardian_name, outputElId) {
    const el = document.getElementById(outputElId);
    el.innerHTML = "<em>Querying database index...</em>";
    const res = await fetch("/api/validate-duplicate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ first_name, last_name, dob, guardian_name })
    });
    const d = await res.json();
    el.innerHTML = `<div class="alert ${d.duplicate ? 'alert-danger' : 'alert-success'}">${d.message}</div>`;
}

async function testRuleBooth(boothId, outputElId) {
    const el = document.getElementById(outputElId);
    el.innerHTML = "<em>Checking booth enrollment limits...</em>";
    const res = await fetch("/api/validate-booth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ booth_id: boothId })
    });
    const d = await res.json();
    el.innerHTML = `<div class="alert ${d.has_capacity ? 'alert-success' : 'alert-danger'}">${d.message}</div>`;
}

async function testRuleAppeal(rejection_date, appeal_date, outputElId) {
    const el = document.getElementById(outputElId);
    el.innerHTML = "<em>Evaluating statutory appeal window...</em>";
    const res = await fetch("/api/validate-appeal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rejection_date, appeal_date })
    });
    const d = await res.json();
    el.innerHTML = `<div class="alert ${d.valid ? 'alert-success' : 'alert-danger'}">${d.message}</div>`;
}
