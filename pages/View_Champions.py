import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px

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


def get_total_pr(data, user_name):
    """Calculate total PR improvement (max - baseline) for one athlete."""
    user = data.get(user_name, {})
    total = 0
    base_lifts = user.get("base_lifts", {})
    lifts = user.get("lifts", {})

    for lift_type in ALL_LIFTS:
        baseline = base_lifts.get(lift_type, 0)

        if lift_type in lifts and lifts[lift_type]:
            max_weight = max(attempt["weight_kg"] for attempt in lifts[lift_type])
        else:
            max_weight = baseline

        total += max_weight - baseline

    return total


# ===== SIDEBAR =====
st.sidebar.title("⚔️ Squat War Portal")
st.sidebar.markdown("---")

if st.sidebar.button("⬅ Back to Main"):
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

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Name", selected_user)
        col2.metric("Age", user_data.get("age", "N/A"))
        col3.metric("Body Weight", f'{user_data.get("weight_kg", 0)} kg')
        col4.metric("Gym Affiliation", user_data.get("gym", "N/A"))

        st.metric("Total PR Improvement", f"{get_total_pr(data, selected_user)}kg")

        st.markdown("---")
        st.markdown("**Base Lifts**")

        base_lifts_display = []
        base_lifts = user_data.get("base_lifts", {})
        body_weight = user_data.get("weight_kg", 0) or 1

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
                history_df = pd.DataFrame(lift_history)

                if not history_df.empty:
                    history_df["date"] = pd.to_datetime(history_df["date"]).dt.date
                    history_df["Body Weight Ratio"] = round(
                        history_df["weight_kg"] / body_weight, 2
                    )
                    history_df = history_df.sort_values("date")

                    baseline = user_data.get("base_lifts", {}).get(selected_lift_history, 0)
                    max_weight = history_df["weight_kg"].max()
                    min_weight = history_df["weight_kg"].min()
                    avg_weight = round(history_df["weight_kg"].mean(), 1)
                    total_attempts = len(history_df)
                    pr_improvement = max_weight - baseline

                    st.write(f"### {selected_lift_history} Stats")

                    col1, col2, col3, col4, col5 = st.columns(5)
                    col1.metric("Baseline", f"{baseline}kg")
                    col2.metric("Current PR", f"{max_weight}kg")
                    col3.metric("PR Improvement", f"{pr_improvement}kg")
                    col4.metric("Average Weight", f"{avg_weight}kg")
                    col5.metric("Total Attempts", total_attempts)

                    col6, col7 = st.columns(2)
                    col6.metric("Min Lift", f"{min_weight}kg")
                    col7.metric("Best Ratio", f"{history_df['Body Weight Ratio'].max():.2f}x BW")

                    st.markdown("---")
                    st.write(f"### {selected_lift_history} History")
                    st.dataframe(
                        history_df[["weight_kg", "reps", "Body Weight Ratio", "date"]],
                        use_container_width=True,
                    )

                    fig = px.line(
                        history_df,
                        x="date",
                        y="weight_kg",
                        markers=True,
                        title=f"{selected_user}'s {selected_lift_history} Progress",
                        hover_data=["Body Weight Ratio"],
                    )
                    fig.update_traces(marker=dict(size=10))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No dated lifts logged yet")
        else:
            st.info(f"{selected_user} hasn't logged any dated lifts yet")
