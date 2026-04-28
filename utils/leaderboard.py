import pandas as pd
from admin.supabase_client import ALL_LIFTS

REP_PERCENT_MAP = {
    2: 0.95,
    3: 0.925,
    4: 0.90,
    5: 0.875,
    6: 0.86,
    8: 0.75,
    10: 0.70,
}


def estimate_1rm_from_map(weight, reps):
    """Estimate 1RM using your custom rep % map."""
    reps = int(reps)

    if reps <= 1:
        return weight  # treat singles as actual max if needed

    pct = REP_PERCENT_MAP.get(reps)

    if pct:
        return weight / pct

    # fallback to Epley if rep not in map
    return weight * (1 + reps / 30)


def build_estimated_1rm_history(data, user_name, lift_type):
    """
    Returns dataframe of estimated 1RM progression vs baseline using REP_PERCENT_MAP
    """
    user = data.get(user_name, {})
    lifts = user.get("lifts", {}).get(lift_type, [])

    if not lifts:
        return pd.DataFrame()

    baseline = user.get("base_lifts", {}).get(lift_type, 0)

    if baseline <= 0:
        return pd.DataFrame()

    records = []

    for attempt in lifts:
        reps = int(attempt.get("reps", 1))
        weight = float(attempt.get("weight_kg", 0))

        # only use 2+ reps for estimated curve
        if reps <= 1:
            continue

        est_1rm = estimate_1rm_from_map(weight, reps)

        records.append({
            "date": pd.to_datetime(attempt.get("date")),
            "estimated_1rm": est_1rm,
            "baseline": baseline,
            "pct_of_baseline": est_1rm / baseline,
            "athlete": user_name,
        })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records).sort_values("date")

    return df
def get_best_estimated_1rm(user_data, lift_type):
    attempts = user_data.get("lifts", {}).get(lift_type, [])
    estimates = []

    for a in attempts:
        reps = int(a.get("reps", 1))
        weight = float(a.get("weight_kg", 0))

        if reps <= 1:
            continue

        est = estimate_1rm_from_map(weight, reps)
        estimates.append(est)

    if not estimates:
        return None

    return max(estimates)


def get_cumulative_pr_score(user_data, lift_type):
    baseline = user_data.get("base_lifts", {}).get(lift_type, 0)
    bw = user_data.get("weight_kg", 1)

    if baseline <= 0:
        return 0

    # PR gain
    best_single = get_best_single_attempt(user_data, lift_type)
    pr_gain = max(0, (best_single - baseline)) if best_single else 0

    # BW ratio
    bw_ratio = (best_single / bw) if best_single else 0

    # Estimated PR term
    est_1rm = get_best_estimated_1rm(user_data, lift_type)

    if est_1rm is not None and est_1rm / baseline > 1: 
        est_ratio = (est_1rm / baseline) - 1
    else:
        est_ratio = 0

    score = (
        0.4 * pr_gain
        + 0.3 * bw_ratio
        + 0.3 * est_ratio
    )

    return score

def has_valid_base_lift(user_data, lift_type):
    """A lift only counts if the athlete has a positive baseline set for that lift."""
    return user_data.get("base_lifts", {}).get(lift_type, 0) > 0


def get_best_single_attempt(user_data, lift_type):
    """Return best 1-rep attempt for a lift, or None."""
    attempts = user_data.get("lifts", {}).get(lift_type, [])
    single_attempts = [a for a in attempts if int(a.get("reps", 1)) == 1]
    if not single_attempts:
        return None
    return max(a["weight_kg"] for a in single_attempts)
    
def get_total_cumulative_score(user_data, all_lifts):
    return sum(get_cumulative_pr_score(user_data, lift) for lift in all_lifts)

def get_lifts_missing_baseline(user_data):
    """Return lift types that have attempts logged but no base lift set."""
    missing = []
    for lift_type in ALL_LIFTS:
        if user_data.get("lifts", {}).get(lift_type) and not has_valid_base_lift(user_data, lift_type):
            missing.append(lift_type)
    return missing


def get_total_pr(data, user_name, all_lifts=ALL_LIFTS):
    """
    Calculate total PR improvement using only 1-rep attempts.
    Negative contributions are not counted.
    Lifts without a valid base lift do not contribute.
    """
    user = data[user_name]
    total = 0

    for lift_type in all_lifts:
        if not has_valid_base_lift(user, lift_type):
            continue

        baseline = user.get("base_lifts", {}).get(lift_type, 0)
        best_single = get_best_single_attempt(user, lift_type)

        if best_single is None:
            contribution = 0
        else:
            contribution = max(0, best_single - baseline)

        total += contribution

    return total


def build_overall_leaderboard(data, all_lifts=ALL_LIFTS):
    overall_data = []
    for name, user in data.items():
        total_pr = get_total_pr(data, name, all_lifts)
        cumulative_score = get_total_cumulative_score(user, all_lifts)
        overall_data.append(
            {
                "Rank": 0,
                "Name": name,
                "Total PR": total_pr,
                "Cumulative Score": round(cumulative_score, 2),
                "Body Weight (kg)": user.get("weight_kg", 0),
                "Gym Affiliation": user.get("gym", "N/A"),
            }
        )

    overall_data = sorted(overall_data, key=lambda x: x["Cumulative Score"], reverse=True)
    for i, row in enumerate(overall_data):
        row["Rank"] = i + 1

    return pd.DataFrame(overall_data)


def build_lift_leaderboard(data, lift):
    """
    Build a lift leaderboard using cumulative score.
    Includes:
    - Best 1RM attempt
    - Bodyweight ratio
    - Cumulative PR Score
    """
    leaderboard_data = []

    for name, user in data.items():
        if not has_valid_base_lift(user, lift):
            continue

        attempts = user.get("lifts", {}).get(lift, [])
        single_attempts = [a for a in attempts if int(a.get("reps", 1)) == 1]

        if single_attempts:
            max_lift = max(single_attempts, key=lambda x: x["weight_kg"])
            max_weight = max_lift["weight_kg"]
            body_weight = user.get("weight_kg", 1)
            body_weight_ratio = round(max_weight / body_weight, 2)

            # 🔥 NEW: cumulative score
            score = get_cumulative_pr_score(user, lift)

            leaderboard_data.append(
                {
                    "Rank": 0,
                    "Name": name,
                    "Weight (kg)": max_weight,
                    "Reps": max_lift["reps"],
                    "Body Weight (kg)": body_weight,
                    "Ratio (Lift/BW)": body_weight_ratio,
                    "Cumulative Score": round(score, 2),  # 👈 NEW COLUMN
                    "Gym Affiliation": user.get("gym", "N/A"),
                    "Date": max_lift["date"][:10],
                }
            )

    if not leaderboard_data:
        return pd.DataFrame()

    lb_df = (
        pd.DataFrame(leaderboard_data)
        .sort_values("Weight (kg)", ascending=False)
        .reset_index(drop=True)
    )

    lb_df.index = lb_df.index + 1
    lb_df["Rank"] = lb_df.index

    return lb_df.reset_index(drop=True)


def build_overall_leader_history(data, all_lifts=ALL_LIFTS):
    """
    Tracks who held #1 over time using CUMULATIVE SCORE instead of total PR.
    """
    if not data:
        return pd.DataFrame()

    # Track running maxes (still needed for progression)
    baseline_map = {
        athlete: {lift: user.get("base_lifts", {}).get(lift, 0) for lift in all_lifts}
        for athlete, user in data.items()
    }

    max_map = {
        athlete: {lift: baseline_map[athlete][lift] for lift in all_lifts}
        for athlete in data
    }

    events = []

    # Build chronological event list (same as before)
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

    for event in events:
        athlete = event["athlete"]
        lift_type = event["lift_type"]
        weight_kg = event["weight_kg"]

        # Update running max
        max_map[athlete][lift_type] = max(max_map[athlete][lift_type], weight_kg)

        totals = {}

        # 🔥 NEW: compute cumulative score for each athlete
        for name in data:
            user = data[name]

            total_score = 0

            for lift in all_lifts:
                if not has_valid_base_lift(user, lift):
                    continue

                # Temporarily override their best lift with current running max
                temp_user = {
                    **user,
                    "lifts": {
                        **user.get("lifts", {}),
                        lift: [{"weight_kg": max_map[name][lift], "reps": 1, "date": None}]
                    }
                    
                }

                total_score += get_cumulative_pr_score(temp_user, lift)

            totals[name] = total_score

        max_score = max(totals.values())
        tied_leaders = [n for n, v in totals.items() if v == max_score]

        # Keep current leader if still tied
        if current_leader in tied_leaders:
            leader_name = current_leader
        else:
            leader_name = tied_leaders[0]

        leader_score = totals[leader_name]

        if leader_name != current_leader or leader_score != current_leader_score:
            history.append(
                {
                    "logged_at": event["logged_at"],
                    "lift_date": event["lift_date"],
                    "leader": leader_name,
                    "cumulative_score": round(leader_score, 2),  # 👈 renamed
                    "trigger_athlete": athlete,
                    "trigger_lift": lift_type,
                    "trigger_weight": weight_kg,
                }
            )

            current_leader = leader_name
            current_leader_score = leader_score

    return pd.DataFrame(history)
