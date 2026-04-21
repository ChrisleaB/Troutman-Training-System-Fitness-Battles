import streamlit as st
import pandas as pd
import json
from datetime import datetime
import plotly.express as px

st.set_page_config(
    page_title="Ultimate Troutman Training Systems Squat War 2026",
    layout="wide",
    initial_sidebar_state="expanded"
)

ARNOLD_DATE = datetime(2026, 3, 4).date()

# Initialize page state
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Main"

@st.cache_resource
def init_db():
    try:
        with open("squat_war_data.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def load_data():
    if "data" not in st.session_state:
        st.session_state.data = init_db()
    return st.session_state.data

def get_total_pr(data, user_name):
    all_lifts = ["Front Squat", "Back Squat"]
    user = data[user_name]
    total = 0
    base_lifts = user.get("base_lifts", {})
    lifts = user.get("lifts", {})

    for lift_type in all_lifts:
        baseline = base_lifts.get(lift_type, 0)
        if lift_type in lifts and lifts[lift_type]:
            max_weight = max([attempt["weight_kg"] for attempt in lifts[lift_type]])
        else:
            max_weight = baseline
        total += max_weight - baseline

    return total

# ===== SIDEBAR NAVIGATION =====
st.sidebar.title("⚔️ Squat War Portal")
st.sidebar.markdown("---")

col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("? Main", use_container_width=True, key="nav_main"):
        st.session_state.current_page = "Main"
        st.rerun()

with col2:
    if st.button("? Champions", use_container_width=True, key="nav_champions"):
        st.session_state.current_page = "Champions"
        st.rerun()

st.sidebar.markdown("---")

# ===== PAGE: MAIN =====
if st.session_state.current_page == "Main":
    st.title("⚔️ Ultimate Troutman Training Systems Squat War 2026")
    st.markdown("#### Rules: All lifts POST-Arnold (March 4, 2026 onwards) are valid submissions")
    st.markdown("---")
    
    data = load_data()
    users = list(data.keys())
    
    if not users:
        st.warning("No athletes yet.")
    else:
        # Your main page content here
        st.write("Main page content goes here")

# ===== PAGE: CHAMPIONS =====
elif st.session_state.current_page == "Champions":
    st.title("? View Champions")
    
    data = load_data()
    users = list(data.keys())
    
    st.markdown("### Athlete Stats")
    
    if not users:
        st.warning("No athletes yet.")
    else:
        selected_user = st.selectbox("Select User:", users)

        if selected_user:
            user_data = data[selected_user]

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Name", selected_user)
            col2.metric("Age", user_data["age"])
            col3.metric("Body Weight", f'{user_data["weight_kg"]} kg')
            col4.metric("Gym Affiliation", user_data.get("gym", "N/A"))

            st.metric("Total PR Improvement", f"{get_total_pr(data, selected_user)}kg")

            st.markdown("---")
            st.markdown("**Base Lifts**")

            base_lifts_display = []
            if "base_lifts" in user_data:
                for lift_name, weight in user_data["base_lifts"].items():
                    if weight > 0:
                        ratio = round(weight / user_data["weight_kg"], 2)
                        base_lifts_display.append({
                            "Lift": lift_name,
                            "Weight (kg)": weight,
                            "Body Weight Ratio": ratio
                        })

            if base_lifts_display:
                base_df = pd.DataFrame(base_lifts_display)
                st.dataframe(base_df, use_container_width=True)
            else:
                st.info("No base lifts set yet")

            st.markdown("---")
            st.markdown("**Dated Lift History**")

            if user_data.get("lifts"):
                selected_lift_history = st.selectbox("View History:", list(user_data["lifts"].keys()))

                if selected_lift_history:
                    lift_history = user_data["lifts"][selected_lift_history]
                    history_df = pd.DataFrame(lift_history)
                    history_df["date"] = pd.to_datetime(history_df["date"]).dt.date
                    history_df["Body Weight Ratio"] = round(history_df["weight_kg"] / user_data["weight_kg"], 2)
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
                    st.dataframe(history_df[["weight_kg", "reps", "Body Weight Ratio", "date"]], use_container_width=True)

                    fig = px.line(
                        history_df,
                        x="date",
                        y="weight_kg",
                        markers=True,
                        title=f"{selected_user}'s {selected_lift_history} Progress",
                        hover_data=["Body Weight Ratio"]
                    )
                    fig.update_traces(marker=dict(size=10))
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"{selected_user} hasn't logged any dated lifts yet")
