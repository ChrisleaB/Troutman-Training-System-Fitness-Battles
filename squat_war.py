import streamlit as st
import pandas as pd
import json
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import os

st.set_page_config(page_title="Ultimate Troutman Squat War 2026", layout="wide")

# Arnold Classic date
ARNOLD_DATE = datetime(2026, 3, 4).date()

# Use Streamlit Session State instead of local file
@st.cache_resource
def init_db():
    try:
        with open("squat_war_data.json", 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def load_data():
    if 'data' not in st.session_state:
        st.session_state.data = init_db()
    return st.session_state.data

def save_data(data):
    st.session_state.data = data
    with open("squat_war_data.json", 'w') as f:
        json.dump(data, f, indent=2)

# ===== SIDEBAR =====
st.sidebar.title("⚔️ Squat War Portal")
st.sidebar.markdown("---")

data = load_data()
users = list(data.keys())

mode = st.sidebar.radio("Select Action:", ["View Leaderboard", "Add Lift", "Add Athlete", "Edit Profile"])

if mode == "Add Athlete":
    st.sidebar.subheader("Add New Athlete")
    new_user = st.sidebar.text_input("Athlete Name:")
    new_age = st.sidebar.number_input("Age:", min_value=15, max_value=80)
    new_weight = st.sidebar.number_input("Body Weight (kg):", min_value=40, max_value=200)
    
    # Gym affiliation selection
    gym_options = ["Troutman Training Systems", "NA", "Other"]
    selected_gym = st.sidebar.selectbox("Gym Affiliation:", gym_options)
    st.sidebar.caption("(if no affiliation --> NA)")
    
    if selected_gym == "Other":
        new_gym = st.sidebar.text_input("Enter gym name:")
    else:
        new_gym = selected_gym
    
        
    if st.sidebar.button("Add", key="add_athlete"):
        if new_user and new_user not in data:
            data[new_user] = {
                'age': new_age,
                'weight_kg': new_weight,
                'gym': new_gym,
                'base_lifts': {
                    'Front Squat': 0,
                    'Back Squat': 0
                },
                'lifts': {},
                'created': datetime.now().isoformat()
            }
            save_data(data)
            st.toast("✓ Submission saved")
            st.rerun()
        elif new_user in data:
            st.sidebar.error(f"✗ {new_user} already exists!")

elif mode == "Edit Profile":
    st.sidebar.subheader("Edit Your Profile")
    
    edit_user = st.sidebar.selectbox("Select Your Name:", users if users else ["No users yet"])
    
    if edit_user and edit_user in data:
        user_data = data[edit_user]
        
        st.sidebar.markdown("**Edit Information**")
        new_age = st.sidebar.number_input("Age:", min_value=15, max_value=80, value=user_data['age'])
        new_weight = st.sidebar.number_input("Body Weight (kg):", min_value=40, max_value=200, value=user_data['weight_kg'])
        
        gym_options = ["Troutman Training Systems", "NA", "Other"]
        current_gym = user_data.get('gym', 'NA')
        default_gym = current_gym if current_gym in gym_options else "Other"
        selected_gym = st.sidebar.selectbox("Gym Affiliation:", gym_options, index=gym_options.index(default_gym))
        
        if selected_gym == "Other":
            new_gym = st.sidebar.text_input("Enter gym name:", value=current_gym if current_gym not in gym_options else "")
        else:
            new_gym = selected_gym
        
        if st.sidebar.button("Save Changes", key="save_profile"):
            data[edit_user]['age'] = new_age
            data[edit_user]['weight_kg'] = new_weight
            data[edit_user]['gym'] = new_gym
            save_data(data)
            st.toast("✓ Submission saved")
            st.rerun()

elif mode == "Add Lift":
    st.sidebar.subheader("? Log Your Lift")
    
    selected_user = st.sidebar.selectbox("Select Your Name:", users if users else ["No users yet"])
    
    if selected_user and selected_user in data:
        # Base lift option
        st.sidebar.markdown("**Base Lifts (PR Baseline)**")
        add_base_lift = st.sidebar.checkbox("Set Base Lift?")
        
        if add_base_lift:
            base_lift_type = st.sidebar.selectbox("Lift Type:", ["Front Squat", "Back Squat"])
            base_weight = st.sidebar.number_input("Base Weight (kg):", min_value=20, max_value=500)
            
            if st.sidebar.button("Set Base Lift", key="set_base"):
                if 'base_lifts' not in data[selected_user]:
                    data[selected_user]['base_lifts'] = {}
                data[selected_user]['base_lifts'][base_lift_type] = base_weight
                save_data(data)
                st.toast("✓ Submission saved")
                st.rerun()
        
        else:
            st.sidebar.markdown("**Log Dated Lift**")
            lift_types = ["Front Squat", "Back Squat"]
            selected_lift = st.sidebar.selectbox("Lift Type:", lift_types)
            
            weight_kg = st.sidebar.number_input("Weight (kg):", min_value=20, max_value=500)
            reps = st.sidebar.number_input("Reps:", min_value=1, max_value=20, value=1)
            
            # Date picker
            lift_date = st.sidebar.date_input("Date of Lift:", value=datetime.now().date())
            
            if st.sidebar.button("Submit Lift", key="submit_lift"):
                # Validate date
                if lift_date < ARNOLD_DATE:
                    st.sidebar.error(f"❌ Invalid submission! Must be during or after Arnold (March 4, 2026)")
                elif selected_lift:
                    if 'lifts' not in data[selected_user]:
                        data[selected_user]['lifts'] = {}
                    
                    if selected_lift not in data[selected_user]['lifts']:
                        data[selected_user]['lifts'][selected_lift] = []
                    
                    # Convert date to datetime string
                    lift_datetime = datetime.combine(lift_date, datetime.min.time()).isoformat()
                    
                    data[selected_user]['lifts'][selected_lift].append({
                        'weight_kg': weight_kg,
                        'reps': reps,
                        'date': lift_datetime
                    })
                    
                    save_data(data)
                    st.toast("✓ Submission saved")
                    st.rerun()

# ===== MAIN CONTENT =====
st.title("⚔️ Ultimate Troutman Training Systems (and Associates)")
st.markdown("# Squat War 2026")
st.markdown("*All lifts POST Arnold (March 4, 2026 onwards) are valid submissions*")
st.markdown("---")

if not users:
    st.warning("No athletes yet. Add athletes in the sidebar!")
else:
    all_lifts = ["Front Squat", "Back Squat"]
    
    # Calculate total PR (max lift - baseline) for each user
    def get_total_pr(user_name):
        user = data[user_name]
        total = 0
        base_lifts = user.get('base_lifts', {})
        lifts = user.get('lifts', {})
        
        for lift_type in all_lifts:
            baseline = base_lifts.get(lift_type, 0)
            
            # Find max weight for this lift from dated attempts
            if lift_type in lifts and lifts[lift_type]:
                max_weight = max([attempt['weight_kg'] for attempt in lifts[lift_type]])
            else:
                max_weight = baseline
            
            # PR is improvement from baseline
            pr_improvement = max_weight - baseline
            total += pr_improvement
        
        return total
    
    # ===== OVERALL TAB =====
    overall_data = []
    for name, user in data.items():
        total_pr = get_total_pr(name)
        overall_data.append({
            'Rank': len(overall_data) + 1,
            'Name': name,
            'Total PR': total_pr,
            'Body Weight (kg)': user['weight_kg'],
            'Gym Affiliation': user.get('gym', 'N/A')
        })
    
    overall_data = sorted(overall_data, key=lambda x: x['Total PR'], reverse=True)
    for i, row in enumerate(overall_data):
        row['Rank'] = i + 1
    
    st.subheader("? ? OVERALL CHAMPION")
    
    if overall_data:
        overall_df = pd.DataFrame(overall_data)
        st.dataframe(overall_df, use_container_width=True)
        
        # Overall champion
        if overall_df.iloc[0]['Total PR'] > 0:
            st.success(f"? **REIGNING CHAMPION: {overall_df.iloc[0]['Name']}** with {overall_df.iloc[0]['Total PR']}kg total PR improvement!")
        else:
            st.info("No PRs set yet!")
    
    st.markdown("---")
    st.subheader("? Live Leaderboards")
    
    lift_tabs = st.tabs(all_lifts)
    
    for tab, lift in zip(lift_tabs, all_lifts):
        with tab:
            st.markdown(f"### {lift} Leaderboard")
            
            leaderboard_data = []
            for name, user in data.items():
                base_lift_weight = user.get('base_lifts', {}).get(lift, 0)
                
                if base_lift_weight > 0:
                    body_weight_ratio = round(base_lift_weight / user['weight_kg'], 2)
                    leaderboard_data.append({
                        'Rank': len(leaderboard_data) + 1,
                        'Name': name,
                        'Weight (kg)': base_lift_weight,
                        'Body Weight (kg)': user['weight_kg'],
                        'Ratio (Lift/BW)': body_weight_ratio,
                        'Gym Affiliation': user.get('gym', 'N/A')
                    })
            
            if leaderboard_data:
                lb_df = pd.DataFrame(leaderboard_data).sort_values('Weight (kg)', ascending=False).reset_index(drop=True)
                lb_df.index = lb_df.index + 1
                
                st.dataframe(lb_df, use_container_width=True)
                
                # Display PR
                top_pr = lb_df.iloc[0]['Weight (kg)']
                st.info(f"? **Current {lift} PR: {top_pr}kg** (set by {lb_df.iloc[0]['Name']})")
                
                fig = px.bar(lb_df, x='Name', y='Weight (kg)', title=f"{lift} - Max Weights",
                            color='Ratio (Lift/BW)', color_continuous_scale='Viridis',
                            hover_data=['Gym Affiliation', 'Ratio (Lift/BW)'])
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"No {lift} base lifts set yet")
    
    st.markdown("---")
    st.subheader("? Individual Progress")
    
    selected_user = st.selectbox("Select User:", users)
    
    if selected_user:
        user_data = data[selected_user]
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Name", selected_user)
        col2.metric("Age", user_data['age'])
        col3.metric("Body Weight", f"{user_data['weight_kg']} kg")
        col4.metric("Gym Affiliation", user_data.get('gym', 'N/A'))
        
        col5, col6 = st.columns(2)
        col5.metric("Total PR Improvement", f"{get_total_pr(selected_user)}kg")
        
        st.markdown("---")
        
        # Display base lifts
        st.markdown("**Base Lifts (PRs)**")
        base_lifts_display = []
        if 'base_lifts' in user_data:
            for lift_name, weight in user_data['base_lifts'].items():
                if weight > 0:
                    ratio = round(weight / user_data['weight_kg'], 2)
                    base_lifts_display.append({
                        'Lift': lift_name,
                        'PR (kg)': weight,
                        'Ratio': ratio
                    })
        
        if base_lifts_display:
            base_df = pd.DataFrame(base_lifts_display)
            st.dataframe(base_df, use_container_width=True)
        else:
            st.info("No base lifts set yet")
        
        st.markdown("---")
        st.markdown("**Dated Lift History**")
        
        if user_data['lifts']:
            selected_lift_history = st.selectbox("View History:", list(user_data['lifts'].keys()))
            
            if selected_lift_history:
                lift_history = user_data['lifts'][selected_lift_history]
                history_df = pd.DataFrame(lift_history)
                history_df['date'] = pd.to_datetime(history_df['date']).dt.date
                history_df['Body Weight Ratio'] = round(history_df['weight_kg'] / user_data['weight_kg'], 2)
                history_df = history_df.sort_values('date')
                
                st.write(f"### {selected_lift_history} History")
                st.dataframe(history_df[['weight_kg', 'reps', 'Body Weight Ratio', 'date']], use_container_width=True)
                
                fig = px.line(history_df, x='date', y='weight_kg', markers=True,
                             title=f"{selected_user}'s {selected_lift_history} Progress",
                             hover_data=['Body Weight Ratio'])
                fig.update_traces(marker=dict(size=10))
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"{selected_user} hasn't logged any dated lifts yet")

st.markdown("---")
st.caption("Ultimate Troutman Training Systems - May the gains be ever in your favor ⚔️?")
