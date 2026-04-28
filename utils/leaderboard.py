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
# BASIC HELPERS (MUST BE FIRST)
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

    return 0.4 * pr_gain + 0.3 * bw_ratio + 0.3 * est_ratio


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
# LEADERBOARDS
# ======================
def get_total_pr(data, user_name, all_lifts=ALL_LIFTS):
    user = data[user_name]
    total = 0

    for lift in all_lifts:
        if not has_valid_base_lift(user, lift):
            continue

        baseline = user["base_lifts"].get(lift, 0)
        best = get_best_single_attempt(user, lift)

        total += max(0, best - baseline) if best else 0

    return total


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
