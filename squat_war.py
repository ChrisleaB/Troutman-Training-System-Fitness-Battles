# -*- coding: utf-8 -*-
"""
Created on Tue Apr 21 11:11:18 2026

@author: boydc
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

from admin.supabase_client import (
    load_data,
    add_athlete,
    update_athlete,
    add_lift,
    set_base_lift,
    delete_athlete_lifts,
    delete_athlete,
    ARNOLD_DATE,
    ALL_LIFTS,
)

st.set_page_config(
    page_title="Ultimate Troutman Training Systems Squat War 2026",
    layout="wide",
)

# Hide sidebar navigation tabs
hide_pages = """
<style>
[data-testid="stSidebarNav"] { display: none; }
</style>
"""
st.markdown(hide_pages, unsafe_allow_html=True)

# Initialize session state
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
if "just_submitted" not in st.session_state:
    st.session_state.just_submitted = False
if "reset_base_lift" not in st.session_state:
    st.session_state.reset_base_lift = False
if "champion_logged_in" not in st.session_state:
    st.session_state.champion_logged_in = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "success_message" not in st.session_state:
    st.session_state.success_message = ""


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
        overall_data.append(
            {
                "Rank": 0,
                "Name": name,
                "Total PR": total_pr,
                "Body Weight (kg)": user.get("weight_kg", 0),
                "Gym Affiliation": user.get("gym", "N/A"),
            }
        )

    overall_data = sorted(overall_data, key=lambda x: x["Total PR"], reverse=True)
    for i, row in enumerate(overall_data):
        row["Rank"] = i + 1

    return pd.DataFrame(overall_data)


def build_lift_leaderboard(data, lift):
    """
    Build a lift leaderboard using only 1-rep attempts.
    Athletes without a valid base lift for that movement are excluded.
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
            body_weight_ratio = round(max_weight / user["weight_kg"], 2)

            leaderboard_data.append(
                {
                    "Rank": 0,
                    "Name": name,
                    "Weight (kg)": max_weight,
                    "Reps": max_lift["reps"],
                    "Body Weight (kg)": user["weight_kg"],
                    "Ratio (Lift/BW)": body_weight_ratio,
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
    Tracks who held #1 overall over time.
    Uses logged_at timestamps so the timeline reflects when submissions were made.
    Only 1-rep attempts contribute.
    Negative PR changes are clamped to 0.
    Lifts without a valid base lift do not contribute.
    """
    if not data:
        return pd.DataFrame()

    baseline_map = {
        athlete: {lift: user.get("base_lifts", {}).get(lift, 0) for lift in all_lifts}
        for athlete, user in data.items()
    }

    max_map = {
        athlete: {lift: baseline_map[athlete][lift] for lift in all_lifts}
        for athlete in data
    }

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
                        "reps": attempt["reps"],
                    }
                )

    if not events:
        return pd.DataFrame()

    events = sorted(events, key=lambda x: x["logged_at"])

    history = []
    current_leader = None
    current_leader_total = None

    for event in events:
        athlete = event["athlete"]
        lift_type = event["lift_type"]
        weight_kg = event["weight_kg"]

        max_map[athlete][lift_type] = max(max_map[athlete][lift_type], weight_kg)

        totals = {}
        for name in data:
            total_pr = 0
            user = data[name]
            for lift in all_lifts:
                if not has_valid_base_lift(user, lift):
                    continue
                baseline = baseline_map[name][lift]
                current_max = max_map[name][lift]
                total_pr += max(0, current_max - baseline)
            totals[name] = total_pr

        max_total = max(totals.values())
        tied_leaders = [name for name, value in totals.items() if value == max_total]

        if current_leader in tied_leaders:
            leader_name = current_leader
        else:
            leader_name = tied_leaders[0]

        leader_total = totals[leader_name]

        if leader_name != current_leader or leader_total != current_leader_total:
            history.append(
                {
                    "logged_at": event["logged_at"],
                    "lift_date": event["lift_date"],
                    "leader": leader_name,
                    "total_pr": leader_total,
                    "trigger_athlete": athlete,
                    "trigger_lift": lift_type,
                    "trigger_weight": weight_kg,
                }
            )
            current_leader = leader_name
            current_leader_total = leader_total

    return pd.DataFrame(history)


# ===== SIDEBAR =====
st.sidebar.title("⚔️ Squat War Portal")
st.sidebar.caption(
    "If you previously signed up (can see your name on the leaderboard), "
    "you already have a login account.\n\n"
    "Username = your name\nPassword = your name"
)
st.sidebar.markdown("---")

data = load_data()
users = list(data.keys())

if st.session_state.get("current_user") and st.session_state.current_user not in users:
    st.session_state.current_user = None
    st.session_state.champion_logged_in = False

# Champion login
with st.sidebar.expander("Login Champion", expanded=False):
    if st.session_state.champion_logged_in and st.session_state.current_user in users:
        st.success(f"Logged in as {st.session_state.current_user}")
        st.caption("Your password is the same as your name/username (include the space).")

        if st.button("Logout Champion", key="champion_logout"):
            st.session_state.champion_logged_in = False
            st.session_state.current_user = None
            st.rerun()
    else:
        login_user = st.selectbox(
            "Select your name:",
            users if users else ["No users yet"],
            key="champion_login_user",
        )
        login_password = st.text_input("Password:", type="password", key="champion_login_pass")
        st.caption("Your password is the same as your name/username.")

        if st.button("Login Champion", key="champion_login_btn"):
            if login_user in data and login_password == login_user:
                st.session_state.current_user = login_user
                st.session_state.champion_logged_in = True
                st.rerun()
            else:
                st.error("Incorrect name or password.")

# Page navigation
if st.sidebar.button("View Champions"):
    st.switch_page("pages/View_Champions.py")

# Admin login
with st.sidebar.expander("Admin", expanded=False):
    if not st.session_state.get("admin_logged_in", False):
        admin_password = st.text_input("Password:", type="password", key="admin_pass")

        if st.button("Login", key="admin_login"):
            if admin_password == "user":
                st.session_state.admin_logged_in = True
                st.rerun()
            else:
                st.error("✗ Incorrect password")
    else:
        st.success("✓ Admin logged in")
        st.markdown("---")
        st.markdown("**Admin Controls**")

        st.warning("⚠️ CAUTION: These actions cannot be undone!")

        clear_user = st.selectbox("Select user to clear data:", users if users else ["No users"])

        if st.button("Clear User Data", key="clear_user_data"):
            if clear_user and clear_user in data:
                delete_athlete_lifts(clear_user)
                st.session_state.just_submitted = True
                st.rerun()

        st.markdown("---")
        st.markdown("**Delete Athlete**")

        delete_user = st.selectbox("Select athlete to delete:", users if users else ["No users"])
        confirm_delete = st.checkbox("I understand this permanently deletes the athlete")

        if st.button("Delete Athlete", key="delete_athlete_btn"):
            if not confirm_delete:
                st.warning("Please confirm deletion first.")
            elif delete_user and delete_user in data:
                success = delete_athlete(delete_user)
                if success:
                    st.session_state.just_submitted = True
                    st.rerun()
                else:
                    st.error("Failed to delete athlete.")

        st.markdown("---")
        if st.button("Logout", key="admin_logout"):
            st.session_state.admin_logged_in = False
            st.rerun()

st.sidebar.markdown("---")

if st.session_state.champion_logged_in:
    mode = st.sidebar.radio(
        "Select Action:",
        ["Submit Lift", "Edit Champion Profile"],
    )
else:
    mode = st.sidebar.radio(
        "Select Action:",
        ["Enter the Arena, Champion"],
    )

if mode == "Enter the Arena, Champion":
    st.sidebar.subheader("Add New Athlete")
    new_user = st.sidebar.text_input("Athlete Name:")
    new_age = st.sidebar.number_input("Age:", min_value=15, max_value=80)
    new_weight = st.sidebar.number_input("Body Weight (kg):", min_value=40, max_value=200)

    gym_options = ["Troutman Training Systems", "NA", "Other"]
    selected_gym = st.sidebar.selectbox("Gym Affiliation:", gym_options)
    st.sidebar.caption("(if no affiliation --> NA)")

    if selected_gym == "Other":
        new_gym = st.sidebar.text_input("Enter gym name:")
    else:
        new_gym = selected_gym

    if st.sidebar.button("Add", key="add_athlete"):
        if new_user and new_user not in data:
            ok = add_athlete(new_user, int(new_age), float(new_weight), new_gym)
            if ok:
                st.session_state.current_user = new_user
                st.session_state.champion_logged_in = True
                st.session_state.success_message = f"Champion {new_user} entered and logged in 🗡️"
                st.session_state.just_submitted = True
                st.rerun()
            else:
                st.sidebar.error("Could not add athlete.")
        elif new_user in data:
            st.sidebar.error(f"✗ {new_user} already exists!")

elif mode == "Edit Champion Profile":
    st.sidebar.subheader("Edit Your Profile")

    if not st.session_state.champion_logged_in or not st.session_state.current_user:
        st.sidebar.info("Log in as a Champion to edit your own profile.")
    else:
        edit_user = st.session_state.current_user
        user_data = data[edit_user]

        st.sidebar.markdown(f"**Editing: {edit_user}**")
        new_age = st.sidebar.number_input(
            "Age:", min_value=15, max_value=80, value=user_data.get("age", 0)
        )
        new_weight = st.sidebar.number_input(
            "Body Weight (kg):", min_value=40, max_value=200, value=user_data.get("weight_kg", 0)
        )

        gym_options = ["Troutman Training Systems", "NA", "Other"]
        current_gym = user_data.get("gym", "NA")
        default_gym = current_gym if current_gym in gym_options else "Other"
        selected_gym = st.sidebar.selectbox(
            "Gym Affiliation:", gym_options, index=gym_options.index(default_gym)
        )

        if selected_gym == "Other":
            new_gym = st.sidebar.text_input(
                "Enter gym name:",
                value=current_gym if current_gym not in gym_options else "",
            )
        else:
            new_gym = selected_gym

        if st.sidebar.button("Save Changes", key="save_profile"):
            ok = update_athlete(edit_user, int(new_age), float(new_weight), new_gym)
            if ok:
                st.session_state.just_submitted = True
                st.rerun()
            else:
                st.sidebar.error("Could not update athlete.")

elif mode == "Submit Lift":
    st.sidebar.subheader("Log Your Lift")

    if not st.session_state.champion_logged_in or not st.session_state.current_user:
        st.sidebar.info("Log in as a Champion to submit lifts for yourself.")
    else:
        selected_user = st.session_state.current_user
        st.sidebar.markdown(f"**Submitting as: {selected_user}**")

        if st.session_state.reset_base_lift:
            st.session_state.set_base_lift_mode = False
            st.session_state.reset_base_lift = False

        st.sidebar.markdown("**Base Lifts (PR Baseline)**")
        st.sidebar.caption("What you were lifting PRE-Arnold or before PR attempts")
        add_base_lift = st.sidebar.checkbox("Set Base Lift?", key="set_base_lift_mode")

        if add_base_lift:
            base_lift_type = st.sidebar.selectbox("Lift Type:", ALL_LIFTS)
            base_weight = st.sidebar.number_input("Base Weight (kg):", min_value=20, max_value=500)

            if st.sidebar.button("Set Base Lift", key="set_base"):
                ok = set_base_lift(selected_user, base_lift_type, float(base_weight))
                if ok:
                    st.session_state.reset_base_lift = True
                    st.session_state.just_submitted = True
                    st.rerun()
                else:
                    st.sidebar.error("Could not set base lift.")
        else:
            st.sidebar.markdown("**Lift Attempt**")
            lift_types = ALL_LIFTS
            selected_lift = st.sidebar.selectbox("Lift Type:", lift_types)

            weight_kg = st.sidebar.number_input("Weight (kg):", min_value=20, max_value=500)
            reps = st.sidebar.number_input("Reps:", min_value=1, max_value=20, value=1)

            lift_date = st.sidebar.date_input("Date of Lift:", value=datetime.now().date())

            if st.sidebar.button("Submit Lift", key="submit_lift"):
                if lift_date < ARNOLD_DATE:
                    st.sidebar.error(
                        "❌ Invalid submission! Must be during or after Arnold (March 4, 2026)"
                    )
                elif reps > 10:
                    st.sidebar.error(
                        "while you may be strong, this app is not and cannot support greater than 10 reps"
                    )
                elif selected_lift:
                    ok = add_lift(selected_user, selected_lift, float(weight_kg), int(reps), lift_date)
                    if ok:
                        st.session_state.just_submitted = True
                        st.rerun()
                    else:
                        st.sidebar.error("Could not submit lift.")

# Show popup if submission just happened
if st.session_state.just_submitted:
    st.success(st.session_state.success_message or "✓ Submission saved")
    st.session_state.success_message = ""
    st.session_state.just_submitted = False

# ===== MAIN CONTENT =====
st.title("⚔️ Ultimate Troutman Training Systems (and Associates) Squat War 2026")
st.markdown(
    """
    <p style='color:#CBA6F7; font-size:25px; margin-bottom:5px;'>
    Rules: All lifts POST-Arnold (March 4, 2026 onwards) are valid submissions
    </p>

    <p style='color:#D4AF37; font-size:15px;'>
    Added logins: if your name is below you have an account, see the sidebar for more details
    </p>
    """,
    unsafe_allow_html=True,
)
st.markdown("*For technical support, questions, or suggestions, contact Chris at boyd.christinalea@gmail.com*")
st.markdown("---")

if not users:
    st.warning("No athletes yet. Add athletes in the sidebar!")
else:
    # ===== OVERALL CHAMPION =====
    overall_df = build_overall_leaderboard(data)

    st.subheader("REIGNING CHAMPIONS")

    if not overall_df.empty:
        st.dataframe(overall_df, use_container_width=True)

        if overall_df.iloc[0]["Total PR"] > 0:
            st.success(
                f" **BEARER OF ABSOLUTE SUPREMACY: {overall_df.iloc[0]['Name']}** "
                f"with {overall_df.iloc[0]['Total PR']}kg total PR improvement!"
            )
        else:
            st.info("No PRs set yet!")

    # ===== OVERALL LEADER HISTORY =====
    st.markdown("---")
    st.subheader("Overall Leader History")

    history_df = build_overall_leader_history(data)

    if not history_df.empty:
        history_df = history_df.sort_values("logged_at").reset_index(drop=True)
        history_df["logged_at_str"] = history_df["logged_at"].dt.strftime("%Y-%m-%d %H:%M UTC")

        history_display = history_df[
            ["logged_at_str", "leader", "total_pr", "trigger_athlete", "trigger_lift", "trigger_weight"]
        ].copy()
        history_display.columns = [
            "Logged At",
            "Leader",
            "Total PR",
            "Trigger Athlete",
            "Trigger Lift",
            "Trigger Weight (kg)",
        ]

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=history_df["logged_at"],
                y=history_df["total_pr"],
                mode="lines+markers+text",
                text=history_df["leader"],
                textposition="top center",
                hovertemplate=(
                    "Logged At: %{x|%Y-%m-%d %H:%M}<br>"
                    "Leader: %{text}<br>"
                    "Total PR: %{y}kg<extra></extra>"
                ),
            )
        )
        fig.update_layout(
            title="History of the #1 Overall Leader",
            xaxis_title="Logged At",
            yaxis_title="Leader's Total PR (kg)",
            showlegend=False,
        )

        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(history_display, use_container_width=True)
    else:
        st.info("No dated lifts yet, so there is no leaderboard history to plot.")

    # ===== INDIVIDUAL LIFT LEADERBOARDS =====
    st.markdown("---")
    st.subheader("Live Leaderboards")

    lift_tabs = st.tabs(ALL_LIFTS)

    for tab, lift in zip(lift_tabs, ALL_LIFTS):
        with tab:
            st.markdown(f"### {lift} Leaderboard")

            lb_df = build_lift_leaderboard(data, lift)

            if not lb_df.empty:
                st.dataframe(lb_df, use_container_width=True)

                top_pr = lb_df.iloc[0]["Weight (kg)"]
                st.info(
                    f"**Current {lift} PR: {top_pr}kg** "
                    f"(set by {lb_df.iloc[0]['Name']} on {lb_df.iloc[0]['Date']})"
                )

                fig = px.bar(
                    lb_df,
                    x="Name",
                    y="Weight (kg)",
                    title=f"{lift} - Max Weights",
                    color="Ratio (Lift/BW)",
                    color_continuous_scale="Viridis",
                    hover_data=["Gym Affiliation", "Ratio (Lift/BW)", "Date"],
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"No athletes with a valid base lift and 1-rep attempt for {lift} yet.")

st.markdown("---")
st.caption("Ultimate Troutman Training System's Squat War 2026 - May the gains be ever in your favor ⚔️")
