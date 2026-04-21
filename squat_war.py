import streamlit as st
import pandas as pd
import json
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import os

st.set_page_config(page_title="Ultimate Troutman Training Systems Squat War 2026", layout="wide")

# Arnold Classic date
ARNOLD_DATE = datetime(2026, 3, 4).date()

# Initialize session state
if 'admin_logged_in' not in st.session_state:
    st.session_state.admin_logged_in = False
if 'just_submitted' not in st.session_state:
    st.session_state.just_submitted = False

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

def remove_duplicates(data):
    """Remove duplicate lift entries"""
    for athlete in data:
        for lift_type in data[athlete].get('lifts', {}):
            lifts = data[athlete]['lifts'][lift_type]
            unique_lifts = []
            seen = set()
            for lift in lifts:
                lift_tuple = (lift['weight_kg'], lift['reps'], lift['date'])
                if lift_tuple not in seen:
                    unique_lifts.append(lift)
                    seen.add(lift_tuple)
            data[athlete]['lifts'][lift_type] = unique_lifts
    return data

def save_data(data):
    st.session_state.data = data
    data = remove_duplicates(data)
    with open("squat_war_data.json", 'w') as f:
        json.dump(data, f, indent=2)

# ===== SIDEBAR =====
st.sidebar.title("⚔️ Squat War Portal")
st.sidebar.markdown("---")

data = load_data()
users = list(data.keys())

# Admin login
with st.sidebar.expander("Admin", expanded=False):
    if not st.session_state.get('admin_logged_in', False):
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
                data[clear_user] = {
                    'age': data[clear_user]['age'],
                    'weight_kg': data[clear_user]['weight_kg'],
                    'gym': data[clear_user]['gym'],
                    'base_lifts': {
                        'Front Squat': 0,
                        'Back Squat': 0
                    },
                    'lifts': {},
                    'created': datetime.now().isoformat()
                }
                save_data(data)
                st.session_state.just_submitted = True
                st.rerun()
        
        st.markdown("---")
        if st.button("Logout", key="admin_logout"):
            st.session_state.admin_logged_in = False
            st.rerun()

st.sidebar.markdown("---")

mode = st.sidebar.radio("Select Action:", ["View Leaderboard", "Enter the Arena, Champion", "Submit Lift",  "Edit Profile"])

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
            st.session_state.just_submitted = True
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
            st.session_state.just_submitted = True
            st.rerun()

elif mode == "Submit Lift":
    st.sidebar.subheader("Log Your Lift")
    
    selected_user = st.sidebar.selectbox("Select Your Name:", users if users else ["No users yet"])
    
    if selected_user and selected_user in data:
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
                st.session_state.just_submitted = True
                st.rerun()
        
        else:
            st.sidebar.markdown("**Log Dated Lift**")
            lift_types = ["Front Squat", "Back Squat"]
            selected_lift = st.sidebar.selectbox("Lift Type:", lift_types)
            
            weight_kg = st.sidebar.number_input("Weight (kg):", min_value=20, max_value=500)
            reps = st.sidebar.number_input("Reps:", min_value=1, max_value=20, value=1)
            
            lift_date = st.sidebar.date_input("Date of Lift:", value=datetime.now().date())
            
            if st.sidebar.button("Submit Lift", key="submit_lift"):
                if lift_date < ARNOLD_DATE:
                    st.sidebar.error(f"❌ Invalid submission! Must be during or after Arnold (March 4, 2026)")
                elif selected_lift:
                    if 'lifts' not in data[selected_user]:
                        data[selected_user]['lifts'] = {}
                    
                    if selected_lift not in data[selected_user]['lifts']:
                        data[selected_user]['lifts'][selected_lift] = []
                    
                    lift_datetime = datetime.combine(lift_date, datetime.min.time()).isoformat()
                    
                    data[selected_user]['lifts'][selected_lift].append({
                        'weight_kg': weight_kg,
                        'reps': reps,
                        'date': lift_datetime
                    })
                    
                    save_data(data)
                    st.session_state.just_submitted = True
                    st.rerun()

# Show popup if submission just happened
if st.session_state.just_submitted:
    st.success("✓ Submission saved")
    st.session_state.just_submitted = False

# ===== MAIN CONTENT =====
st.title("⚔️ Ultimate Troutman Training Systems (and Associates) Squat War 2026")
st.markdown("###Rules: All lifts POST-Arnold (March 4, 2026 onwards) are valid submissions*")
st.markdown("*For technical support, questions, or suggestions, contact Chris at boyd.christinalea@gmail.com")
st.markdown("---")

if not users:
    st.warning("No athletes yet. Add athletes in the sidebar!")
else:
    all_lifts = ["Front Squat", "Back Squat"]
    
    def get_total_pr(user_name):
        """Calculate total PR improvement (max - baseline)"""
        user = data[user_name]
        total = 0
        base_lifts = user.get('base_lifts', {})
        lifts = user.get('lifts', {})
        
        for lift_type in all_lifts:
            baseline = base_lifts.get(lift_type, 0)
            
            if lift_type in lifts and lifts[lift_type]:
                max_weight = max([attempt['weight_kg'] for attempt in lifts[lift_type]])
            else:
                max_weight = baseline
            
            pr_improvement = max_weight - baseline
            total += pr_improvement
        
        return total
    
    # ===== OVERALL CHAMPION =====
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
    
    st.subheader("BEARER OF ABSOLUTE SUPREMACY")
    
    if overall_data:
        overall_df = pd.DataFrame(overall_data)
        st.dataframe(overall_df, use_container_width=True)
        
        if overall_df.iloc[0]['Total PR'] > 0:
            st.success(f" **REIGNING CHAMPION: {overall_df.iloc[0]['Name']}** with {overall_df.iloc[0]['Total PR']}kg total PR improvement!")
        else:
            st.info("No PRs set yet!")
    
    st.markdown("---")
    st.subheader("Live Leaderboards")
    
    lift_tabs = st.tabs(all_lifts)
    
    for tab, lift in zip(lift_tabs, all_lifts):
        with tab:
            st.markdown(f"### {lift} Leaderboard")
            
            leaderboard_data = []
            for name, user in data.items():
                lifts = user.get('lifts', {})
                
                if lift in lifts and lifts[lift]:
                    max_lift = max(lifts[lift], key=lambda x: x['weight_kg'])
                    max_weight = max_lift['weight_kg']
                    
                    body_weight_ratio = round(max_weight / user['weight_kg'], 2)
                    leaderboard_data.append({
                        'Rank': len(leaderboard_data) + 1,
                        'Name': name,
                        'Weight (kg)': max_weight,
                        'Reps': max_lift['reps'],
                        'Body Weight (kg)': user['weight_kg'],
                        'Ratio (Lift/BW)': body_weight_ratio,
                        'Gym Affiliation': user.get('gym', 'N/A'),
                        'Date': max_lift['date'][:10]
                    })
            
            if leaderboard_data:
                lb_df = pd.DataFrame(leaderboard_data).sort_values('Weight (kg)', ascending=False).reset_index(drop=True)
                lb_df.index = lb_df.index + 1
                
                st.dataframe(lb_df, use_container_width=True)
                
                top_pr = lb_df.iloc[0]['Weight (kg)']
                st.info(f"**Current {lift} PR: {top_pr}kg** (set by {lb_df.iloc[0]['Name']} on {lb_df.iloc[0]['Date']})")
                
                fig = px.bar(lb_df, x='Name', y='Weight (kg)', title=f"{lift} - Max Weights",
                            color='Ratio (Lift/BW)', color_continuous_scale='Viridis',
                            hover_data=['Gym Affiliation', 'Ratio (Lift/BW)', 'Date'])
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"No {lift} lifts logged yet")
    
    st.markdown("---")
    st.subheader("Individual Progress")
    
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
        
        st.markdown("**Base Lifts**")
        base_lifts_display = []
        if 'base_lifts' in user_data:
            for lift_name, weight in user_data['base_lifts'].items():
                if weight > 0:
                    ratio = round(weight / user_data['weight_kg'], 2)
                    base_lifts_display.append({
                        'Lift': lift_name,
                        'Weight (kg)': weight,
                        'Body Weight Ratio': ratio
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
                
                # ===== PR STATS =====
                baseline = user_data.get('base_lifts', {}).get(selected_lift_history, 0)
                max_weight = history_df['weight_kg'].max()
                min_weight = history_df['weight_kg'].min()
                avg_weight = round(history_df['weight_kg'].mean(), 1)
                total_attempts = len(history_df)
                pr_improvement = max_weight - baseline
                
                st.write(f"### {selected_lift_history} Stats")
                
                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("Baseline", f"{baseline}kg")
                col2.metric("Current PR", f"{max_weight}kg")
                col3.metric("PR Improvement", f"{pr_improvement}kg", delta=f"+{pr_improvement}kg")
                col4.metric("Average Weight", f"{avg_weight}kg")
                col5.metric("Total Attempts", total_attempts)
                
                col6, col7 = st.columns(2)
                col6.metric("Min Lift", f"{min_weight}kg")
                col7.metric("Best Ratio", f"{history_df['Body Weight Ratio'].max():.2f}x BW")
                
                st.markdown("---")
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
st.caption("Ultimate Troutman Training System's Squat War 2026 - May the gains be ever in your favor ⚔️")
