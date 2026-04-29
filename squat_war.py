# -*- coding: utf-8 -*-
"""
Created on Tue Apr 21 11:11:18 2026

@author: boydc
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from admin.supabase_client import (
    client,    
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
from utils.leaderboard import (
    has_valid_base_lift,
    get_best_single_attempt,
    get_lifts_missing_baseline,
    get_total_pr,
    build_overall_leaderboard,
    build_lift_leaderboard,
    build_overall_leader_history,
    build_estimated_1rm_history,
    get_cumulative_pr_score, 
    get_total_cumulative_score
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
if "mode" not in st.session_state:
    st.session_state.mode = "home"

# ===== DATA =====
data = load_data()
users = list(data.keys())

# Reset invalid user session
if st.session_state.get("current_user") and st.session_state.current_user not in users:
    st.session_state.current_user = None
    st.session_state.champion_logged_in = False
    st.session_state.mode = "home"

# Keep mode valid for login state
if st.session_state.champion_logged_in:
    if st.session_state.mode not in ("submit", "edit", "home"):
        st.session_state.mode = "home"
else:
    if st.session_state.mode in ("submit", "edit"):
        st.session_state.mode = "home"


# ===== SIDEBAR =====
st.sidebar.title("⚔️ Squat War Portal")
st.sidebar.caption(
    "If you previously signed up (can see your name on the leaderboard), "
    "you already have a login account. Username = your name. Password = your name."
)
st.sidebar.markdown("---")

# Enter the Arena (only when logged out)
if not st.session_state.champion_logged_in:
    with st.sidebar.expander("Enter the Arena Champion"):
        new_user = st.text_input("Athlete Name:")
        new_age = st.number_input("Age:", min_value=15, max_value=80)
        new_weight = st.number_input("Body Weight (kg):", min_value=40, max_value=200)

        gym_options = ["Troutman Training Systems", "NA", "Other"]
        selected_gym = st.selectbox("Gym Affiliation:", gym_options)
        st.caption("(if no affiliation --> NA)")

        if selected_gym == "Other":
            new_gym = st.text_input("Enter gym name:")
        else:
            new_gym = selected_gym

        if st.button("Add", key="add_athlete"):
            if new_user and new_user not in data:
                ok = add_athlete(new_user, int(new_age), float(new_weight), new_gym)
                if ok:
                    st.session_state.current_user = new_user
                    st.session_state.champion_logged_in = True
                    st.session_state.mode = "home" 
                    st.session_state.success_message = f"Champion {new_user} entered and logged in 🗡️"
                    st.session_state.just_submitted = True
                    st.rerun()
                else:
                    st.error("Could not add athlete.")
            elif new_user in data:
                st.error(f"✗ {new_user} already exists!")
    
# Champion login
with st.sidebar.expander("Login Champion", expanded=False):
    if st.session_state.champion_logged_in and st.session_state.current_user in users:
        st.success(f"Logged in as {st.session_state.current_user}")
        st.caption("Your password is the same as your name/username.")

        if st.button("Logout Champion", key="champion_logout"):
            st.session_state.champion_logged_in = False
            st.session_state.current_user = None
            st.session_state.mode = "home"
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
                st.session_state.mode = "home"
                st.rerun()
            else:
                st.error("Incorrect name or password.")

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

        # ===== CLEAR USER =====
        clear_user = st.selectbox(
            "Select user to clear data:",
            users if users else ["No users"]
        )

        if st.button("Clear User Data", key="clear_user_data"):
            if clear_user and clear_user in data:
                delete_athlete_lifts(clear_user)
                st.session_state.just_submitted = True
                st.rerun()

        # ===== EDIT / DELETE LIFTS =====
        st.markdown("---")
        st.markdown("**Edit / Delete Individual Lifts**")

        edit_user = st.selectbox(
            "Select athlete:",
            users if users else ["No users"],
            key="admin_edit_user"
        )

        if edit_user in data:
            user_data = data[edit_user]

            lift_type = st.selectbox(
                "Select lift type:",
                ALL_LIFTS,
                key="admin_lift_type"
            )

            attempts = user_data.get("lifts", {}).get(lift_type, [])

            if attempts:
                for i, attempt in enumerate(attempts):

                    unique_key = f"{edit_user}_{lift_type}_{i}"

                    with st.expander(
                        f"{attempt['weight_kg']}kg × {attempt['reps']} ({attempt.get('date','')})"
                    ):

                        new_weight = st.number_input(
                            "Weight (kg)",
                            value=float(attempt["weight_kg"]),
                            key=f"edit_weight_{unique_key}"
                        )

                        new_reps = st.number_input(
                            "Reps",
                            value=int(attempt["reps"]),
                            key=f"edit_reps_{unique_key}"
                        )

                        new_date = st.date_input(
                            "Date",
                            value=pd.to_datetime(
                                attempt.get("date", datetime.now())
                            ).date(),
                            key=f"edit_date_{unique_key}"
                        )

                        col1, col2 = st.columns(2)

                        # ✏️ EDIT
                        with col1:
                            if st.button("Save Edit", key=f"save_edit_{unique_key}"):
                                attempts[i] = {
                                    **attempt,
                                    "weight_kg": float(new_weight),
                                    "reps": int(new_reps),
                                    "date": new_date.isoformat()
                                }

                                client.table("athletes").update(
                                    {"lifts": user_data["lifts"]}
                                ).eq("name", edit_user).execute()

                                st.success("Lift updated")
                                st.rerun()

                        # 🗑 DELETE
                        with col2:
                            if st.button("Delete Lift", key=f"delete_lift_{unique_key}"):
                                attempts.pop(i)

                                client.table("athletes").update(
                                    {"lifts": user_data["lifts"]}
                                ).eq("name", edit_user).execute()

                                st.success("Lift deleted")
                                st.rerun()

            else:
                st.info("No lifts recorded for this movement.")

        # ===== DELETE ATHLETE =====
        st.markdown("---")
        st.markdown("**Delete Athlete**")

        delete_user = st.selectbox(
            "Select athlete to delete:",
            users if users else ["No users"]
        )

        confirm_delete = st.checkbox(
            "I understand this permanently deletes the athlete"
        )

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

        # ===== LOGOUT =====
        st.markdown("---")
        if st.button("Logout", key="admin_logout"):
            st.session_state.admin_logged_in = False
            st.rerun()
# Page navigation
if st.sidebar.button("View Champions", key="view_champions_btn"):
    st.switch_page("pages/View_Champions.py")
st.sidebar.markdown("---")

# Action buttons
if st.session_state.champion_logged_in:
    st.sidebar.markdown("### Actions")

    if st.sidebar.button("Submit Lift", key="nav_submit"):
        st.session_state.mode = "submit"
        st.rerun()

    if st.sidebar.button("Edit Champion Profile", key="nav_edit"):
        st.session_state.mode = "edit"
        st.rerun()

mode = st.session_state.mode
# ===== MODE-DRIVEN SIDEBAR FORMS =====
if mode == "edit":
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

elif mode == "submit":
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
            selected_lift = st.sidebar.selectbox("Lift Type:", ALL_LIFTS)

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

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            label="Total PR",
            value="",
            help="Total PR = Back Squat 1RM PR + Front Squat 1RM PR\n\nOnly counts improvements over baseline"
        )
    
    with col2:
        st.metric(
            label="Cumulative Score",
            value="",
            help=(
                "Cumulative Score = 0.4 × PR Gain\n"
                "+ 0.3 × (1RM / Bodyweight)\n"
                "+ 0.3 × [(Estimated 1RM / Baseline)-1]\n\n"
                "- Estimated term only counts if > baseline\n"
                "- Missing values count as 0"
            )
        )
    st.subheader("REIGNING CHAMPIONS")

    if not overall_df.empty:
        st.dataframe(overall_df, use_container_width=True)

        if overall_df.iloc[0]["Cumulative Score"] > 0:
            st.success(
                f"👑 **BEARER OF ABSOLUTE SUPREMACY: {overall_df.iloc[0]['Name']}**\n"
                f"🔥 Score: {overall_df.iloc[0]['Cumulative Score']:.2f} | "
                f"💪 Total PR: {overall_df.iloc[0]['Total PR']:.1f}kg"
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
            ["logged_at_str", "leader", "cumulative_score", "trigger_athlete", "trigger_lift", "trigger_weight"]
        ].copy()
        
        history_display.columns = [
            "Logged At",
            "Leader",
            "Cumulative Score",
            "Trigger Athlete",
            "Trigger Lift",
            "Trigger Weight (kg)",
        ]

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=history_df["logged_at"],
                y=history_df["cumulative_score"],
                mode="lines+markers+text",
                text=history_df["leader"],
                textposition="top center",
                hovertemplate=(
                    "Logged At: %{x|%Y-%m-%d %H:%M}<br>"
                    "Leader: %{text}<br>"
                    "Score: %{y:.2f}<extra></extra>"
                ),
            )
        )
        fig.update_layout(
            title="History of the #1 Overall Leader",
            xaxis_title="Logged At",
            yaxis_title="Leader's Cumulative Score",
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
            # ===== NEW SECTION: Estimated 1RM Tracker =====
            st.markdown("---")
            st.markdown("#### Estimated 1RM Progression (% of Baseline)")
    
            all_est_data = []
    
            for name in data.keys():
                df_est = build_estimated_1rm_history(data, name, lift)
    
                if not df_est.empty:
                    all_est_data.append(df_est)
    
            if all_est_data:
                combined_df = pd.concat(all_est_data)
    
                fig_est = px.line(
                    combined_df,
                    x="date",
                    y="pct_of_baseline",
                    color="athlete",
                    markers=True,
                    title=f"{lift} Estimated 1RM (% of Baseline)",
                )
    
                fig_est.update_layout(
                    yaxis_title="% of Baseline",
                    xaxis_title="Date",
                )
    
                st.plotly_chart(fig_est, use_container_width=True)
            else:
                st.info("No multi-rep data available for estimated 1RM tracking.")
            
            st.markdown("---")
            st.markdown("#### Who's got that DAWG in them")
            
            # ===== FILTER =====
            if st.session_state.champion_logged_in and st.session_state.current_user:
                filter_mode = st.radio(
                    "Show DAWG data:",
                    ["All Athletes", "My Lifts Only"],
                    horizontal=True,
                    key=f"dawg_filter_{lift}"
                )
            else:
                filter_mode = "All Athletes"
            
            scatter_data = []
            
            for name, user in data.items():
                if filter_mode == "My Lifts Only" and name != st.session_state.current_user:
                    continue
            
                attempts = user.get("lifts", {}).get(lift, [])
                bw = max(user.get("weight_kg", 1), 1)
                baseline = user.get("base_lifts", {}).get(lift, 1)
            
                if baseline <= 0:
                    continue
            
                for a in attempts:
                    weight = float(a.get("weight_kg", 0))
                    reps = int(a.get("reps", 1))
            
                    effort_raw = (weight / baseline) * reps
                    effort_scaled = min(effort_raw, 8)  # 🔥 cap at 8
                    rel_strength = weight / bw
            
                    scatter_data.append({
                        "Name": name,
                        "Reps": reps,
                        "Weight": weight,
                        "Effort": effort_raw,
                        "EffortScaled": effort_scaled,
                        "SuperDawg": effort_raw >= 10,  # 🔥 elite flag
                        "RelStrength": rel_strength,
                    })
            
            if scatter_data:
                df_scatter = pd.DataFrame(scatter_data)
            
                # ===== BUCKETED SIZES =====
                df_scatter["Size"] = pd.cut(
                    df_scatter["EffortScaled"],
                    bins=[0, 1, 2, 3, 4, 5, 6, 7, 8],
                    labels= [4, 9, 16, 24, 34, 47, 60, 72]
                ).astype(float)
            
                df_scatter["Size"] = df_scatter["Size"].fillna(4)
                            
                df_scatter["Elite"] = df_scatter["RelStrength"] > 2
            
                col1, col2 = st.columns([3, 1])
            
                # ===== CHART =====
                with col1:
                    st.subheader(
                        "ℹ️ How to read this chart",
                        help=(
                            "Dot size = effort (scaled 1–8)\n\n"
                            "Effort = (weight ÷ baseline) × reps\n\n"
                            "Color = relative strength (weight ÷ bodyweight)\n\n"
                            "Gold ring = >2x bodyweight\n"
                            "Red ring = SUPER DAWG STATUS (10+ effort)"
                            
                        )
                    )
            
                    fig = px.scatter(
                        df_scatter,
                        x="Reps",
                        y="Weight",
                        size=None,
                        size_max=20,
                        color="RelStrength",
                        color_continuous_scale="plasma",
                        hover_name="Name",
                        hover_data={
                            "Reps": True,
                            "Weight": True,
                            "RelStrength": ":.2f",
                            "Effort": ":.2f",
                            "Size": False,
                        },
                        title=f"{lift} — Who's got that DAWG in them",
                    )
            
                    st.caption("Gold ring = >2x BW | Red ring = SUPER DAWG")
            
                    fig.update_traces(
                        marker=dict(
                            size=df_scatter["Size"],   # 👈 direct pixel control
                            opacity=0.75,
                            line=dict(width=0)
                        )
                    )
            
                    # ===== ELITE (gold) =====
                    for _, row in df_scatter.iterrows():
                        if row["Elite"]:
                            fig.add_scatter(
                                x=[row["Reps"]],
                                y=[row["Weight"]],
                                mode="markers",
                                marker=dict(
                                    size=row["Size"],
                                    color="rgba(0,0,0,0)",
                                    line=dict(color="gold", width=3),
                                ),
                                showlegend=False,
                                hoverinfo="skip"
                            )
            
                    # ===== SUPER DAWG (red) =====
                    for _, row in df_scatter.iterrows():
                        if row["SuperDawg"]:
                            fig.add_scatter(
                                x=[row["Reps"]],
                                y=[row["Weight"]],
                                mode="markers",
                                marker=dict(
                                    size=min(row["Size"] + 6, 24),
                                    color="rgba(0,0,0,0)",
                                    line=dict(color="red", width=4),
                                ),
                                showlegend=False,
                                hoverinfo="skip"
                            )
            
                    fig.add_vline(x=5, line_dash="dot", opacity=0.3)
                    fig.add_hline(y=df_scatter["Weight"].median(), line_dash="dot", opacity=0.3)
            
                    fig.update_layout(
                        coloraxis_colorbar=dict(title="Weight / BW"),
                        xaxis_title="Reps",
                        yaxis_title="Weight (kg)",
                    )
            
                    st.plotly_chart(fig, use_container_width=True)
            
                # ===== TOP 5 DAWG TABLE =====
                with col2:
                    st.markdown("### 🐶 DAWG Index")
            
                    # sort + take top 5
                    top_df = df_scatter.sort_values("Effort", ascending=False).head(5).copy()
                    
                    if not top_df.empty:
                        top_df["Lift"] = top_df.apply(
                            lambda r: f"{int(r['Weight'])}kg × {int(r['Reps'])}",
                            axis=1
                        )
                    
                        # 🔥 DAWG ranking emojis (by position)
                        dawg_ranks = ["🐺🔥", "🐺", "🐕‍🦺", "🐕", "🐶"]
                    
                        for rank, (_, row) in enumerate(top_df.iterrows()):
                            emoji = dawg_ranks[rank] if rank < len(dawg_ranks) else "🐾"
                            name = row["Name"].replace("*", "")
                            st.markdown(
                                f"{emoji} **{name}** — {row['Lift']}  \n"
                                f"<span style='color:#888'>Effort: {row['Effort']:.2f}</span>",
                                unsafe_allow_html=True
                            )
                    else:
                        st.info("No DAWG data yet.")
            
            else:
                st.info("No training data available yet.")

st.markdown("---")
st.caption("Ultimate Troutman Training System's Squat War 2026 - May the gains be ever in your favor ⚔️")
