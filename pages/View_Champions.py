import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

from admin.supabase_client import load_data, ALL_LIFTS

st.set_page_config(
    page_title="View Champions",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Hide Streamlit's automatic page nav
hide_pages = """
<style>
[data-testid="stSidebarNav"] { display: none; }
</style>
"""
st.markdown(hide_pages, unsafe_allow_html=True)

# Rep -> percentage of 1RM that the athlete should be capable of lifting
# Used for 2+ rep estimated 1RM calculations.
REP_PERCENT_MAP = {
    2: 0.95,
    3: 0.925,
    4: 0.90,
    5: 0.875,
    6: 0.86,
    8: 0.75,
    10: 0.80,  # change to 0.70 if that is the target value later
}


def estimate_1rm_from_set(weight_kg: float, reps: int) -> float:
    """
    Estimate 1RM from a set using the custom rep-percentage model.
    For reps not explicitly listed, fall back to Epley.
    """
    reps = int(reps)

    if reps <= 1:
        return round(weight_kg, 2)

    pct = REP_PERCENT_MAP.get(reps)
    if pct:
        return round(weight_kg / pct, 2)

    return round(weight_kg * (1 + reps / 30.0), 2)


def has_valid_base_lift(user_data, lift_type):
    return user_data.get("base_lifts", {}).get(lift_type, 0) > 0


def get_lifts_missing_baseline(user_data):
    """
    Return lift types where attempts exist but no base lift has been set.
    """
    missing = []
    for lift_type in ALL_LIFTS:
        has_attempts = bool(user_data.get("lifts", {}).get(lift_type))
        has_base = has_valid_base_lift(user_data, lift_type)
        if has_attempts and not has_base:
            missing.append(lift_type)
    return missing


def get_best_single_attempt(user_data, lift_type):
    attempts = user_data.get("lifts", {}).get(lift_type, [])
    single_attempts = [a for a in attempts if int(a.get("reps", 1)) == 1]
    if not single_attempts:
        return None
    return max(a["weight_kg"] for a in single_attempts)


def get_total_pr(data, user_name):
    """
    Total PR improvement for the athlete page:
    - only counts lifts with a valid base lift
    - only counts 1-rep attempts
    - negative contributions are clamped to zero
    """
    user = data.get(user_name, {})
    base_lifts = user.get("base_lifts", {})
    total = 0

    for lift_type in ALL_LIFTS:
        if not has_valid_base_lift(user, lift_type):
            continue

        baseline = base_lifts.get(lift_type, 0)
        best_single = get_best_single_attempt(user, lift_type)

        if best_single is None:
            contribution = 0
        else:
            contribution = max(0, best_single - baseline)

        total += contribution

    return total


def build_history_frame(lift_history, baseline, body_weight):
    """
    Build a cleaned history dataframe with:
    - actual date
    - logged_at if available
    - estimated 1RM per set
    - effective max BEFORE the attempt at that date
    """
    history_df = pd.DataFrame(lift_history)
    if history_df.empty:
        return history_df

    history_df["date"] = pd.to_datetime(history_df["date"], errors="coerce")

    if "logged_at" in history_df.columns:
        history_df["logged_at"] = pd.to_datetime(history_df["logged_at"], utc=True, errors="coerce")
    else:
        history_df["logged_at"] = pd.to_datetime(history_df["date"], utc=True, errors="coerce")

    history_df = history_df.dropna(subset=["date"]).copy()
    history_df["reps"] = history_df["reps"].fillna(1).astype(int)
    history_df["weight_kg"] = history_df["weight_kg"].astype(float)

    # Stable ordering for same-day attempts
    history_df = history_df.sort_values(["date", "logged_at"], kind="mergesort").reset_index(drop=True)

    history_df["Body Weight Ratio"] = round(history_df["weight_kg"] / body_weight, 2)

    # Estimated 1RM for every set
    history_df["attempt_1rm"] = history_df.apply(
        lambda row: estimate_1rm_from_set(row["weight_kg"], int(row["reps"])),
        axis=1,
    )

    # Effective max BEFORE each attempt, based on all prior attempts up to that date
    effective_before = []
    running_effective = float(baseline)

    for _, row in history_df.iterrows():
        effective_before.append(running_effective)
        running_effective = max(running_effective, float(row["attempt_1rm"]))

    history_df["effective_max_before_attempt"] = effective_before
    history_df["gain_vs_effective_max"] = history_df["attempt_1rm"] - history_df["effective_max_before_attempt"]
    history_df["gain_vs_effective_max"] = history_df["gain_vs_effective_max"].clip(lower=0)

    return history_df


# ===== SIDEBAR =====
st.sidebar.title("⚔️ Squat War Portal")
st.sidebar.markdown("---")

if st.sidebar.button("⬅ Back to Leaderboard"):
    st.switch_page("squat_war.py")

st.sidebar.markdown("---")

# ===== PAGE CONTENT =====
st.title("🏆 View Champions")
st.markdown("### Athlete Stats")

data = load_data()
users = list(data.keys())

if not users:
    st.warning("No athletes yet.")
else:
    selected_user = st.selectbox("Select User:", users)

    if selected_user and selected_user in data:
        user_data = data[selected_user]
        body_weight = user_data.get("weight_kg", 0) or 1

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Name", selected_user)
        col2.metric("Age", user_data.get("age", "N/A"))
        col3.metric("Body Weight", f'{user_data.get("weight_kg", 0)} kg')
        col4.metric("Gym Affiliation", user_data.get("gym", "N/A"))

        st.metric("Total PR Improvement", f"{get_total_pr(data, selected_user)}kg")

        missing_base_lifts = get_lifts_missing_baseline(user_data)
        if missing_base_lifts:
            st.warning(
                "This athlete has lift attempts without a base lift set for: "
                f"{', '.join(missing_base_lifts)}. "
                "Please add the base lifts so those attempts can count."
            )

        st.markdown("---")
        st.markdown("**Base Lifts**")

        base_lifts_display = []
        base_lifts = user_data.get("base_lifts", {})

        for lift_name, weight in base_lifts.items():
            if weight and weight > 0:
                ratio = round(weight / body_weight, 2)
                base_lifts_display.append(
                    {
                        "Lift": lift_name,
                        "Weight (kg)": weight,
                        "Body Weight Ratio": ratio,
                    }
                )

        if base_lifts_display:
            base_df = pd.DataFrame(base_lifts_display)
            st.dataframe(base_df, use_container_width=True)
        else:
            st.info("No base lifts set yet")

        st.markdown("---")
        st.markdown("**Dated Lift History**")

        lifts = user_data.get("lifts", {})
        if lifts:
            selected_lift_history = st.selectbox("View History:", list(lifts.keys()))

            if selected_lift_history and selected_lift_history in lifts:
                lift_history = lifts[selected_lift_history]
                baseline = user_data.get("base_lifts", {}).get(selected_lift_history, 0)

                history_df = build_history_frame(lift_history, baseline, body_weight)

                if not history_df.empty:
                    single_df = history_df[history_df["reps"] == 1].copy()
                    multi_df = history_df[history_df["reps"] > 1].copy()

                    best_single = single_df["weight_kg"].max() if not single_df.empty else baseline
                    current_pr_improvement = max(0, best_single - baseline)

                    best_estimated_1rm = multi_df["attempt_1rm"].max() if not multi_df.empty else None
                    best_estimated_ratio = (
                        round(best_estimated_1rm / body_weight, 2) if best_estimated_1rm is not None else None
                    )

                    min_weight = history_df["weight_kg"].min()
                    total_attempts = len(history_df)

                    st.write(f"### {selected_lift_history} Stats")

                    col1, col2, col3, col4, col5 = st.columns(5)
                    col1.metric("Baseline", f"{baseline}kg")
                    col2.metric("Current 1-Rep PR", f"{best_single}kg")
                    col3.metric("PR Improvement", f"{current_pr_improvement}kg")
                    col4.metric(
                        "Best 2+ Rep Estimated 1RM",
                        f"{best_estimated_1rm:.1f}kg" if best_estimated_1rm is not None else "N/A",
                    )
                    col5.metric("Total Attempts", total_attempts)

                    col6, col7 = st.columns(2)
                    col6.metric("Min Lift", f"{min_weight}kg")
                    col7.metric(
                        "Best 2+ Rep 1RM Ratio",
                        f"{best_estimated_ratio:.2f}x BW" if best_estimated_ratio is not None else "N/A",
                    )

                    st.markdown("---")

                    # ===== SINGLE-REP ATTEMPTS =====
                    st.write(f"### {selected_lift_history} Single-Rep Attempts")
                    if not single_df.empty:
                        st.dataframe(
                            single_df[["date", "weight_kg", "reps", "Body Weight Ratio"]],
                            use_container_width=True,
                        )

                        fig_single = px.line(
                            single_df,
                            x="date",
                            y="weight_kg",
                            markers=True,
                            title=f"{selected_user}'s {selected_lift_history} Single-Rep History",
                            hover_data=["reps", "Body Weight Ratio"],
                        )
                        fig_single.update_traces(marker=dict(size=10))
                        st.plotly_chart(fig_single, use_container_width=True)
                    else:
                        st.info("No 1-rep attempts logged yet for this lift.")

                    st.markdown("---")

                    # ===== 2+ REP ESTIMATED 1RM CURVE =====
                    st.write(f"### {selected_lift_history} 2+ Rep Estimated 1RM Curve")
                    if not multi_df.empty:
                        st.dataframe(
                            multi_df[
                                [
                                    "date",
                                    "weight_kg",
                                    "reps",
                                    "attempt_1rm",
                                    "effective_max_before_attempt",
                                    "gain_vs_effective_max",
                                    "Body Weight Ratio",
                                ]
                            ],
                            use_container_width=True,
                        )

                        fig_multi = go.Figure()

                        fig_multi.add_trace(
                            go.Scatter(
                                x=multi_df["date"],
                                y=multi_df["attempt_1rm"],
                                mode="lines+markers",
                                name="Estimated 1RM",
                                hovertemplate=(
                                    "Date: %{x|%Y-%m-%d}<br>"
                                    "Estimated 1RM: %{y:.1f}kg<extra></extra>"
                                ),
                            )
                        )

                        fig_multi.add_trace(
                            go.Scatter(
                                x=multi_df["date"],
                                y=multi_df["effective_max_before_attempt"],
                                mode="lines+markers",
                                name="Effective Max Before Attempt",
                                hovertemplate=(
                                    "Date: %{x|%Y-%m-%d}<br>"
                                    "Effective Max Before Attempt: %{y:.1f}kg<extra></extra>"
                                ),
                            )
                        )

                        fig_multi.update_layout(
                            title=f"{selected_user}'s {selected_lift_history} Estimated 1RM vs Effective Max",
                            xaxis_title="Date",
                            yaxis_title="kg",
                            showlegend=True,
                        )

                        st.plotly_chart(fig_multi, use_container_width=True)
                    else:
                        st.info("No 2+ rep attempts logged yet for this lift.")
                else:
                    st.info("No dated lifts logged yet")
        else:
            st.info(f"{selected_user} hasn't logged any dated lifts yet")
