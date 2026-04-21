import json
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, List, Tuple

DATA_FILE = Path("squat_war_data.json")
ARNOLD_DATE = date(2026, 3, 4)
ALL_LIFTS = ["Front Squat", "Back Squat"]


def load_data() -> Dict[str, Any]:
    if DATA_FILE.exists():
        try:
            with DATA_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def remove_duplicates(data: Dict[str, Any]) -> Dict[str, Any]:
    for athlete in data:
        lifts_dict = data[athlete].get("lifts", {})
        for lift_type in list(lifts_dict.keys()):
            lifts = lifts_dict.get(lift_type, [])
            unique_lifts = []
            seen = set()
            for lift in lifts:
                lift_tuple = (lift.get("weight_kg"), lift.get("reps"), lift.get("date"))
                if lift_tuple not in seen:
                    unique_lifts.append(lift)
                    seen.add(lift_tuple)
            data[athlete]["lifts"][lift_type] = unique_lifts
    return data


def save_data(data: Dict[str, Any]) -> None:
    data = remove_duplicates(data)
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def ensure_user_schema(user: Dict[str, Any]) -> Dict[str, Any]:
    user = dict(user or {})
    user.setdefault("age", 0)
    user.setdefault("weight_kg", 0)
    user.setdefault("gym", "NA")
    user.setdefault("base_lifts", {"Front Squat": 0, "Back Squat": 0})
    user.setdefault("lifts", {})
    user.setdefault("created", datetime.now().isoformat())
    return user


def get_total_pr(user_name: str, data: Dict[str, Any]) -> float:
    user = ensure_user_schema(data.get(user_name, {}))
    total = 0.0
    base_lifts = user.get("base_lifts", {})
    lifts = user.get("lifts", {})

    for lift_type in ALL_LIFTS:
        baseline = float(base_lifts.get(lift_type, 0) or 0)
        if lift_type in lifts and lifts[lift_type]:
            max_weight = max(float(attempt.get("weight_kg", 0) or 0) for attempt in lifts[lift_type])
        else:
            max_weight = baseline
        total += max(0.0, max_weight - baseline)
    return total


def get_overall_leaderboard(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    overall_data = []
    for name, user in data.items():
        u = ensure_user_schema(user)
        overall_data.append({
            "Name": name,
            "Total PR": get_total_pr(name, data),
            "Body Weight (kg)": u.get("weight_kg", 0),
            "Gym Affiliation": u.get("gym", "N/A"),
        })

    overall_data.sort(key=lambda x: (x["Total PR"], x["Body Weight (kg)"], x["Name"]), reverse=True)
    for idx, row in enumerate(overall_data, start=1):
        row["Rank"] = idx
    return overall_data


def get_lift_leaderboard(data: Dict[str, Any], lift: str) -> List[Dict[str, Any]]:
    leaderboard_data = []
    for name, user in data.items():
        u = ensure_user_schema(user)
        lifts = u.get("lifts", {})
        if lift in lifts and lifts[lift]:
            max_lift = max(lifts[lift], key=lambda x: float(x.get("weight_kg", 0) or 0))
            max_weight = float(max_lift.get("weight_kg", 0) or 0)
            body_weight = float(u.get("weight_kg", 0) or 0)
            ratio = round(max_weight / body_weight, 2) if body_weight else 0
            leaderboard_data.append({
                "Name": name,
                "Weight (kg)": max_weight,
                "Reps": max_lift.get("reps", 0),
                "Body Weight (kg)": body_weight,
                "Ratio (Lift/BW)": ratio,
                "Gym Affiliation": u.get("gym", "N/A"),
                "Date": str(max_lift.get("date", ""))[:10],
            })

    leaderboard_data.sort(key=lambda x: (x["Weight (kg)"], x["Ratio (Lift/BW)"], x["Name"]), reverse=True)
    for idx, row in enumerate(leaderboard_data, start=1):
        row["Rank"] = idx
    return leaderboard_data


def get_overall_leader_history(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not data:
        return []

    # Start from Arnold date, before any post-Arnold lifts count.
    current_max = {
        name: {lift: float(ensure_user_schema(user).get("base_lifts", {}).get(lift, 0) or 0) for lift in ALL_LIFTS}
        for name, user in data.items()
    }

    events: List[Tuple[datetime, str, str, float, int]] = []
    for name, user in data.items():
        lifts = ensure_user_schema(user).get("lifts", {})
        for lift_type, attempts in lifts.items():
            for attempt in attempts:
                dt = attempt.get("date")
                if not dt:
                    continue
                try:
                    parsed = datetime.fromisoformat(dt)
                except Exception:
                    continue
                if parsed.date() < ARNOLD_DATE:
                    continue
                events.append((parsed, name, lift_type, float(attempt.get("weight_kg", 0) or 0), int(attempt.get("reps", 1) or 1)))

    events.sort(key=lambda x: x[0])

    def score_user(user_name: str) -> float:
        user = ensure_user_schema(data[user_name])
        return sum(max(0.0, current_max[user_name][lift] - float(user.get("base_lifts", {}).get(lift, 0) or 0)) for lift in ALL_LIFTS)

    history = []
    previous_leader = None

    # Initial state at the Arnold date.
    if data:
        totals = {name: score_user(name) for name in data}
        if totals:
            leader_name = max(totals, key=lambda n: (totals[n], n))
            history.append({
                "date": datetime.combine(ARNOLD_DATE, datetime.min.time()).isoformat(),
                "leader": leader_name,
                "total_pr": totals[leader_name],
                "changed": True,
            })
            previous_leader = leader_name

    for parsed, name, lift_type, weight, reps in events:
        current_max[name][lift_type] = max(current_max[name][lift_type], weight)
        totals = {user_name: score_user(user_name) for user_name in data}
        leader_name = max(totals, key=lambda n: (totals[n], n))
        if leader_name != previous_leader:
            history.append({
                "date": parsed.isoformat(),
                "leader": leader_name,
                "total_pr": totals[leader_name],
                "changed": True,
            })
            previous_leader = leader_name

    return history
