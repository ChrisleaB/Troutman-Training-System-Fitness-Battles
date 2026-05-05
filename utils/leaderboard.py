import pandas as pd
from admin.supabase_client import ALL_LIFTS

# ======================
# CONSTANTS
# ======================
REP_PERCENT_MAP = {
    2: 0.95,
    3: 0.925,
    4: 0.90,
    5: 0.875,
    6: 0.86,
    8: 0.75,
    10: 0.70,
}

# ======================
# BASIC HELPERS (must come first)
# ======================
def has_valid_base_lift(user_data, lift_type):
    return user_data.get("base_lifts", {}).get(lift_type, 0) > 0


def get_best_single_attempt(user_data, lift_type):
    attempts = user_data.get("lifts", {}).get(lift_type, [])
    singles = [a for a in attempts if int(a.get("reps", 1)) == 1]
    if not singles:
        return None
    return max(a["weight_kg"] for a in singles)

# ======================
# 1RM LOGIC
# ======================
def estimate_1rm_from_map(weight, reps):
    reps = int(reps)

    if reps <= 1:
        return weight

    pct = REP_PERCENT_MAP.get(reps)
    if pct:
        return weight / pct

    return weight * (1 + reps / 30)


def get_best_estimated_1rm(user_data, lift_type):
    attempts = user_data.get("lifts", {}).get(lift_type, [])
    estimates = []

    for a in attempts:
        reps = int(a.get("reps", 1))
        weight = float(a.get("weight_kg", 0))

        if reps <= 1:
            continue

        estimates.append(estimate_1rm_from_map(weight, reps))

    return max(estimates) if estimates else None

# ======================
# SCORING
# ======================
def get_cumulative_pr_score(user_data, lift_type):
    baseline = user_data.get("base_lifts", {}).get(lift_type, 0)
    bw = user_data.get("weight_kg", 1)

    if baseline <= 0:
        return 0

    best_single = get_best_single_attempt(user_data, lift_type)
    pr_gain = max(0, best_single - baseline) if best_single else 0
    bw_ratio = (best_single / bw) if best_single else 0

    est_1rm = get_best_estimated_1rm(user_data, lift_type)

    if est_1rm is not None and est_1rm / baseline > 1:
        est_ratio = (est_1rm / baseline) - 1
    else:
        est_ratio = 0

    return 0.3 * pr_gain + 0.4 * bw_ratio + 0.3 * est_ratio


def get_total_cumulative_score(user_data, all_lifts):
    return sum(get_cumulative_pr_score(user_data, lift) for lift in all_lifts)

# ======================
# ANALYTICS
# ======================
def build_estimated_1rm_history(data, user_name, lift_type):
    user = data.get(user_name, {})
    lifts = user.get("lifts", {}).get(lift_type, [])

    baseline = user.get("base_lifts", {}).get(lift_type, 0)
    if not lifts or baseline <= 0:
        return pd.DataFrame()

    records = []

    for a in lifts:
        reps = int(a.get("reps", 1))
        if reps <= 1:
            continue

        weight = float(a.get("weight_kg", 0))
        est = estimate_1rm_from_map(weight, reps)

        records.append({
            "date": pd.to_datetime(a.get("date")),
            "estimated_1rm": est,
            "baseline": baseline,
            "pct_of_baseline": est / baseline,
            "athlete": user_name,
        })

    return pd.DataFrame(records).sort_values("date") if records else pd.DataFrame()

# ======================
# LEADERBOARD HELPERS
# ======================
def get_lifts_missing_baseline(user_data):
    missing = []
    for lift in ALL_LIFTS:
        if user_data.get("lifts", {}).get(lift) and not has_valid_base_lift(user_data, lift):
            missing.append(lift)
    return missing


def get_total_pr(data, user_name, all_lifts=ALL_LIFTS):
    user = data[user_name]
    total = 0

    for lift in all_lifts:
        if not has_valid_base_lift(user, lift):
            continue

        baseline = user.get("base_lifts", {}).get(lift, 0)
        best = get_best_single_attempt(user, lift)

        total += max(0, best - baseline) if best else 0

    return total

# ======================
# LEADERBOARDS
# ======================
def build_overall_leaderboard(data, all_lifts=ALL_LIFTS):
    rows = []

    for name, user in data.items():
        rows.append({
            "Rank": 0,
            "Name": name,
            "Total PR": get_total_pr(data, name),
            "Cumulative Score": round(get_total_cumulative_score(user, all_lifts), 2),
            "Body Weight (kg)": user.get("weight_kg", 0),
            "Gym Affiliation": user.get("gym", "N/A"),
        })

    rows = sorted(rows, key=lambda x: x["Cumulative Score"], reverse=True)

    for i, r in enumerate(rows):
        r["Rank"] = i + 1

    return pd.DataFrame(rows)


def build_lift_leaderboard(data, lift):
    rows = []

    for name, user in data.items():
        if not has_valid_base_lift(user, lift):
            continue

        singles = [a for a in user.get("lifts", {}).get(lift, []) if int(a.get("reps", 1)) == 1]
        if not singles:
            continue

        best = max(singles, key=lambda x: x["weight_kg"])
        bw = user.get("weight_kg", 1)

        rows.append({
            "Rank": 0,
            "Name": name,
            "Weight (kg)": best["weight_kg"],
            "Reps": best["reps"],
            "Body Weight (kg)": bw,
            "Ratio (Lift/BW)": round(best["weight_kg"] / bw, 2),
            "Cumulative Score": round(get_cumulative_pr_score(user, lift), 2),
            "Gym Affiliation": user.get("gym", "N/A"),
            "Date": best["date"][:10],
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).sort_values("Weight (kg)", ascending=False).reset_index(drop=True)
    df["Rank"] = df.index + 1
    return df
    
def build_overall_leader_history(data, all_lifts=ALL_LIFTS):
    """
    Tracks who held #1 over time using cumulative score.
    """
    if not data:
        return pd.DataFrame()

    # Initialize baseline + running max maps
    baseline_map = {
        athlete: {lift: user.get("base_lifts", {}).get(lift, 0) for lift in all_lifts}
        for athlete, user in data.items()
    }

    max_map = {
        athlete: {lift: baseline_map[athlete][lift] for lift in all_lifts}
        for athlete in data
    }

    # Build event timeline
    events = []
    for athlete, user in data.items():
        for lift_type, attempts in user.get("lifts", {}).items():
            if lift_type not in all_lifts:
                continue

            if not has_valid_base_lift(user, lift_type):
                continue

            for attempt in attempts:
                if int(attempt.get("reps", 1)) != 1:
                    continue

                try:
                    event_dt = pd.to_datetime(
                        attempt.get("logged_at", attempt.get("date")),
                        utc=True,
                        errors="coerce",
                    )
                    if pd.isna(event_dt):
                        continue
                except Exception:
                    continue

                events.append(
                    {
                        "logged_at": event_dt,
                        "lift_date": attempt.get("date"),
                        "athlete": athlete,
                        "lift_type": lift_type,
                        "weight_kg": attempt["weight_kg"],
                    }
                )

    if not events:
        return pd.DataFrame()

    events = sorted(events, key=lambda x: x["logged_at"])

    history = []
    current_leader = None
    current_leader_score = None

    # Process events over time
    for event in events:
        athlete = event["athlete"]
        lift_type = event["lift_type"]
        weight_kg = event["weight_kg"]

        # Update running max
        max_map[athlete][lift_type] = max(max_map[athlete][lift_type], weight_kg)

        totals = {}

        # Compute cumulative score for each athlete
        for name in data:
            user = data[name]
            total_score = 0

            for lift in all_lifts:
                if not has_valid_base_lift(user, lift):
                    continue

                # simulate "current best" using running max
                temp_user = {
                    **user,
                    "lifts": {
                        lift: [{
                            "weight_kg": max_map[name][lift],
                            "reps": 1
                        }]
                    }
                }

                total_score += get_cumulative_pr_score(temp_user, lift)

            totals[name] = total_score

        max_score = max(totals.values())
        tied_leaders = [n for n, v in totals.items() if v == max_score]

        # Keep leader if tied
        if current_leader in tied_leaders:
            leader_name = current_leader
        else:
            leader_name = tied_leaders[0]

        leader_score = totals[leader_name]

        # Record change
        if leader_name != current_leader or leader_score != current_leader_score:
            history.append(
                {
                    "logged_at": event["logged_at"],
                    "lift_date": event["lift_date"],
                    "leader": leader_name,
                    "cumulative_score": round(leader_score, 2),
                    "trigger_athlete": athlete,
                    "trigger_lift": lift_type,
                    "trigger_weight": weight_kg,
                }
            )

            current_leader = leader_name
            current_leader_score = leader_score

    return pd.DataFrame(history)
