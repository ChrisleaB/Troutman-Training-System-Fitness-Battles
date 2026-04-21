import json
from datetime import datetime, date
from typing import Dict, Any, List
import supabase
import streamlit as st

# Load from Streamlit secrets instead of hardcoding
SUPABASE_URL = st.secrets["https://npndhanidytvcpxavlnd.supabase.co"]
SUPABASE_KEY = st.secrets["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5wbmRoYW5pZHl0dmNweGF2bG5kIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY3OTU4MDMsImV4cCI6MjA5MjM3MTgwM30.QXAhNT7W8DmmVaxqUzlfrgbNRHaxuslTC8VheYgdLbs"]

client = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)

ARNOLD_DATE = date(2026, 3, 4)
ALL_LIFTS = ["Front Squat", "Back Squat"]


def load_data() -> Dict[str, Any]:
    """Load all athletes from Supabase"""
    try:
        response = client.table("athletes").select("*").execute()
        athletes = {}
        for row in response.data:
            athletes[row["name"]] = {
                "age": row["age"],
                "weight_kg": row["weight_kg"],
                "gym": row["gym"],
                "base_lifts": row["base_lifts"],
                "lifts": row["lifts"],
                "created": row["created_at"],
            }
        return athletes
    except Exception as e:
        print(f"Error loading data: {e}")
        return {}


def save_data(data: Dict[str, Any]) -> None:
    """Save all athletes to Supabase"""
    try:
        # First delete all existing records
        client.table("athletes").delete().neq("id", 0).execute()
        
        # Then insert all current data
        for name, user_data in data.items():
            client.table("athletes").insert({
                "name": name,
                "age": user_data.get("age", 0),
                "weight_kg": user_data.get("weight_kg", 0),
                "gym": user_data.get("gym", "NA"),
                "base_lifts": user_data.get("base_lifts", {"Front Squat": 0, "Back Squat": 0}),
                "lifts": user_data.get("lifts", {}),
                "created_at": user_data.get("created", datetime.now().isoformat()),
            }).execute()
    except Exception as e:
        print(f"Error saving data: {e}")


def add_athlete(name: str, age: int, weight_kg: float, gym: str) -> bool:
    """Add a new athlete"""
    try:
        client.table("athletes").insert({
            "name": name,
            "age": age,
            "weight_kg": weight_kg,
            "gym": gym,
            "base_lifts": {"Front Squat": 0, "Back Squat": 0},
            "lifts": {},
        }).execute()
        return True
    except Exception as e:
        print(f"Error adding athlete: {e}")
        return False


def update_athlete(name: str, age: int, weight_kg: float, gym: str) -> bool:
    """Update an athlete's profile"""
    try:
        client.table("athletes").update({
            "age": age,
            "weight_kg": weight_kg,
            "gym": gym,
            "updated_at": datetime.now().isoformat(),
        }).eq("name", name).execute()
        return True
    except Exception as e:
        print(f"Error updating athlete: {e}")
        return False


def add_lift(name: str, lift_type: str, weight_kg: float, reps: int, lift_date: date) -> bool:
    """Add a lift for an athlete"""
    try:
        data = load_data()
        if name not in data:
            return False
        
        if lift_type not in data[name]["lifts"]:
            data[name]["lifts"][lift_type] = []
        
        data[name]["lifts"][lift_type].append({
            "weight_kg": weight_kg,
            "reps": reps,
            "date": datetime.combine(lift_date, datetime.min.time()).isoformat(),
        })
        
        # Update this athlete's lifts
        client.table("athletes").update({
            "lifts": data[name]["lifts"],
            "updated_at": datetime.now().isoformat(),
        }).eq("name", name).execute()
        
        return True
    except Exception as e:
        print(f"Error adding lift: {e}")
        return False


def set_base_lift(name: str, lift_type: str, weight_kg: float) -> bool:
    """Set a base lift for an athlete"""
    try:
        data = load_data()
        if name not in data:
            return False
        
        data[name]["base_lifts"][lift_type] = weight_kg
        
        client.table("athletes").update({
            "base_lifts": data[name]["base_lifts"],
            "updated_at": datetime.now().isoformat(),
        }).eq("name", name).execute()
        
        return True
    except Exception as e:
        print(f"Error setting base lift: {e}")
        return False


def delete_athlete_lifts(name: str) -> bool:
    """Clear all lifts for an athlete"""
    try:
        client.table("athletes").update({
            "lifts": {},
            "base_lifts": {"Front Squat": 0, "Back Squat": 0},
            "updated_at": datetime.now().isoformat(),
        }).eq("name", name).execute()
        return True
    except Exception as e:
        print(f"Error clearing athlete: {e}")
        return False
