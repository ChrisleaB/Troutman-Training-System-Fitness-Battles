import streamlit as st
import pandas as pd
import json
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import os

st.set_page_config(page_title="Ultimate Troutman Squat War 2026", layout="wide")

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

mode = st.sidebar.radio("Select Action:", ["View Leaderboard", "Add Lift", "Manage Users"])

if mode == "Manage Users":
    st.sidebar.subheader("Add New User")
    new_user = st.sidebar.text_input("User Name:")
    new_age = st.sidebar.number_input("Age:", min_value=15, max_value=80)
    new_weight = st.sidebar.number_input("Body Weight (kg):", min_value=40, max_value=200)
    
    # Gym selection
    gym_options = ["Vanderbilt Gym", "Planet Fitness", "CrossFit Box", "Home Gym", "Other"]
    selected_gym = st.sidebar.selectbox("Gym:", gym_options)
    
    if selected_gym == "Other":
        new_gym = st.sidebar.text_input("Enter gym name:")
    else:
        new_gym = selected_gym
    
    # Description/Affiliation
    st.sidebar.markdown("**Description/Affiliation**")
    st.sidebar.caption("(if no affiliation --> NA)")
    new_description = st.sidebar.text_input("Description/Affiliation (optional):", placeholder="e.g., Troutman Athlete, Coach, etc.")
    
    if not new_description:
        new_description = "NA"
    
    if st.sidebar.button("Add User", key="add_user"):
        if new_user and new_user not in data:
            data[new_user] = {
                'age': new_age,
                'weight_kg': new_weight,
                'gym': new_gym,
                'description': new_description,
                'lifts': {},
                'created': datetime.now().isoformat()
            }
            save_data(data)
            st.sidebar.success(f"✓ Added {new_user} from {new_gym}!")
            st.rerun()
        elif new_user in data:
            st.sidebar.error(f"✗ {new_user} already exists!")

elif mode == "Add Lift":
    st.sidebar.subheader("? Log Your Lift")
    
    selected_user = st.sidebar.selectbox("Select Your Name:", users if users else ["No users yet"])
    
    if selected_user and selected_user in data:
        lift_types = ["Squat", "Bench Press", "Deadlift", "Overhead Press", "Front Squat", "Leg Press", "Other"]
        selected_lift = st.sidebar.selectbox("Lift Type:", lift_types)
        
        if selected_lift == "Other":
            selected_lift = st.sidebar.text_input("Enter lift name:")
        
        weight_kg = st.sidebar.number_input("Weight (kg):", min_value=20, max_value=500)
        reps = st.sidebar.number_input("Reps:", min_value=1, max_value=20, value=1)
        
        if st.sidebar.button("Submit Lift", key="submit_lift"):
            if selected_lift:
                if 'lifts' not in data[selected_user]:
                    data[selected_user]['lifts'] = {}
                
                if selected_lift not in data[selected_user]['lifts']:
                    data[selected_user]['lifts'][selected_lift] = []
                
                data[selected_user]['lifts'][selected_lift].append({
                    'weight_kg': weight_kg,
                    'reps': reps,
                    'date': datetime.now().isoformat()
                })
                
                save_data(data)
                st.sidebar.success(f"✓ {selected_user} logged {weight_kg}kg x{reps} {selected_lift}!")
                st.rerun()

# ===== MAIN CONTENT =====
st.title("⚔️ Ultimate Troutman Training Systems (and Associates)")
st.markdown("# Squat War 2026")
st.markdown("---")

if not users:
    st.warning("No users yet. Add users in the sidebar!")
else:
    all_lifts = set()
    for user in data.values():
        all_lifts.update(user['lifts'].keys())
    
    all_lifts = sorted(list(all_lifts))
    
    if not all_lifts:
        st.info("No lifts logged yet!")
    else:
        st.subheader("? Live Leaderboards")
        
        lift_tabs = st.tabs(all_lifts)
        
        for tab, lift in zip(lift_tabs, all_lifts):
            with tab:
                st.markdown(f"### {lift} Leaderboard")
                
                leaderboard_data = []
                for name, user in data.items():
                    if lift in user['lifts'] and user['lifts'][lift]:
                        max_lift = max(user['lifts'][lift], key=lambda x: x['weight_kg'])
                        leaderboard_data.append({
                            'Rank': len(leaderboard_data) + 1,
                            'Name': name,
                            'Weight (kg)': max_lift['weight_kg'],
                            'Reps': max_lift['reps'],
                            'Body Weight (kg)': user['weight_kg'],
                            'Ratio': round(max_lift['weight_kg'] / user['weight_kg'], 2),
                            'Gym': user.get('gym', 'N/A'),
                            'Affiliation': user.get('description', 'NA'),
                            'Date': max_lift['date'][:10]
                        })
                
                if leaderboard_data:
                    lb_df = pd.DataFrame(leaderboard_data).sort_values('Weight (kg)', ascending=False).reset_index(drop=True)
                    lb_df.index = lb_df.index + 1
                    
                    st.dataframe(lb_df, use_container_width=True)
                    
                    fig = px.bar(lb_df, x='Name', y='Weight (kg)', title=f"{lift} - Max Weights",
                                color='Weight (kg)', color_continuous_scale='Viridis',
                                hover_data=['Gym', 'Affiliation', 'Ratio'])
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info(f"No {lift} data yet")
        
        st.markdown("---")
        st.subheader("? Individual Progress")
        
        selected_user = st.selectbox("Select User:", users)
        
        if selected_user:
            user_data = data[selected_user]
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Name", selected_user)
            col2.metric("Age", user_data['age'])
            col3.metric("Body Weight", f"{user_data['weight_kg']} kg")
            col4.metric("Gym", user_data.get('gym', 'N/A'))
            
            col5, col6 = st.columns(2)
            col5.metric("Affiliation", user_data.get('description', 'NA'))
            
            st.markdown("---")
            
            if user_data['lifts']:
                selected_lift_history = st.selectbox("View History:", list(user_data['lifts'].keys()))
                
                if selected_lift_history:
                    lift_history = user_data['lifts'][selected_lift_history]
                    history_df = pd.DataFrame(lift_history)
                    history_df['date'] = pd.to_datetime(history_df['date']).dt.date
                    history_df = history_df.sort_values('date')
                    
                    st.write(f"### {selected_lift_history} History")
                    st.dataframe(history_df, use_container_width=True)
                    
                    fig = px.line(history_df, x='date', y='weight_kg', markers=True,
                                 title=f"{selected_user}'s {selected_lift_history} Progress")
                    fig.update_traces(marker=dict(size=10))
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"{selected_user} hasn't logged any lifts yet")

st.markdown("---")
st.caption("Ultimate Troutman Training Systems - May the gains be ever in your favor ⚔️?")