import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

# Fast page configuration
st.set_page_config(
    page_title="Nutrition Network",
    page_icon="⚕️",
    layout="wide"
)

# Utility functions for profile setup
def convert_weight_to_kg(weight_lbs):
    """Convert weight from pounds to kilograms"""
    return weight_lbs * 0.453592

def convert_height_to_cm(feet, inches):
    """Convert height from feet/inches to centimeters"""
    total_inches = feet * 12 + inches
    return total_inches * 2.54

def calculate_bmr(weight_kg, height_cm, age, gender):
    """Calculate Basal Metabolic Rate using Mifflin-St Jeor equation"""
    if gender.lower() == "male":
        return 88.362 + (13.397 * weight_kg) + (4.799 * height_cm) - (5.677 * age)
    else:
        return 447.593 + (9.247 * weight_kg) + (3.098 * height_cm) - (4.330 * age)

def calculate_tdee(bmr, activity_level):
    """Calculate Total Daily Energy Expenditure"""
    multipliers = {
        "Sedentary (little or no exercise)": 1.2,
        "Lightly active (light exercise/sports 1-3 days/week)": 1.375,
        "Moderately active (moderate exercise/sports 3-5 days/week)": 1.55,
        "Very active (hard exercise/sports 6-7 days a week)": 1.725,
        "Extra active (very hard exercise/sports & physical job)": 1.9
    }
    return bmr * multipliers.get(activity_level, 1.2)

def calculate_macros(calories, goal):
    """Calculate macro distribution based on goal"""
    if goal == "Lose weight":
        # Higher protein, moderate carbs, lower fat
        protein_pct, carb_pct, fat_pct = 0.35, 0.40, 0.25
    elif goal == "Gain weight (muscle)":
        # High protein, higher carbs, moderate fat
        protein_pct, carb_pct, fat_pct = 0.30, 0.45, 0.25
    else:  # Maintain weight
        # Balanced macros
        protein_pct, carb_pct, fat_pct = 0.25, 0.45, 0.30
    
    protein_cals = calories * protein_pct
    carb_cals = calories * carb_pct
    fat_cals = calories * fat_pct
    
    return {
        'protein': protein_cals / 4,  # 4 cal per gram
        'carbs': carb_cals / 4,      # 4 cal per gram
        'fat': fat_cals / 9,         # 9 cal per gram
        'fiber': 25 if goal == "Lose weight" else 30
    }

# Cache data loading
@st.cache_data(ttl=30)  # Cache for 30 seconds
def load_scanned_foods():
    """Load scanned foods with caching"""
    try:
        if os.path.exists('scanned_foods.json'):
            with open('scanned_foods.json', 'r') as f:
                data = json.load(f)
                return data.get('foods', [])
        return []
    except Exception:
        return []

# Simple metrics calculation
@st.cache_data(ttl=60)  # Cache for 1 minute
def calculate_daily_totals(foods):
    """Calculate daily nutrition totals with caching"""
    totals = {
        'calories': 0,
        'protein': 0,
        'carbs': 0,
        'fat': 0,
        'fiber': 0,
        'count': len(foods)
    }
    
    for food in foods:
        totals['calories'] += food.get('calories', 0) or 0
        totals['protein'] += food.get('protein', 0) or 0
        totals['carbs'] += food.get('carbs', 0) or 0
        totals['fat'] += food.get('fat', 0) or 0
        totals['fiber'] += food.get('fiber', 0) or 0
    
    return totals

# Initialize profile if not exists
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = None

# Main app
def main():
    # Check if user profile exists
    if st.session_state.user_profile is None:
        setup_profile()
        return
        
    st.title("Nutrition Network")
    st.markdown(f"Welcome back, **{st.session_state.user_profile['name']}**!")
    
    # Load data
    foods = load_scanned_foods()
    totals = calculate_daily_totals(foods)
    
    # Quick stats in columns
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Foods Scanned", totals['count'])
    
    with col2:
        st.metric("Calories", f"{totals['calories']:.0f}")
    
    with col3:
        st.metric("Protein", f"{totals['protein']:.1f}g")
    
    with col4:
        st.metric("Carbs", f"{totals['carbs']:.1f}g")
    
    # Recent foods section
    if foods:
        st.subheader("Recent Scans")
        
        # Show last 10 foods in a simple table
        recent_foods = foods[-10:][::-1]  # Last 10, reversed
        
        if recent_foods:
            df = pd.DataFrame([
                {
                    'Food': food.get('name', 'Unknown'),
                    'Brand': food.get('brand', ''),
                    'Calories': f"{food.get('calories', 0):.0f}",
                    'Protein': f"{food.get('protein', 0):.1f}g",
                    'Time': datetime.fromisoformat(food.get('timestamp', '')).strftime('%H:%M') if food.get('timestamp') else 'Unknown'
                }
                for food in recent_foods
            ])
            
            st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Simple progress bars using user's personal goals
        st.subheader("Daily Progress")
        
        # Use user's personalized goals
        daily_goals = st.session_state.user_profile['daily_goals']
        
        for nutrient, goal in daily_goals.items():
            current = totals.get(nutrient, 0)
            progress = min(current / goal, 1.0) if goal > 0 else 0
            st.progress(progress, text=f"{nutrient.title()}: {current:.0f}/{goal} ({progress*100:.0f}%)")
    
    else:
        st.info("No scanned foods yet! Use the main app to start scanning barcodes.")
        st.markdown("👉 Open http://localhost:5001 to scan foods")
    
    # Action buttons
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Refresh Data", help="Reload latest scanned foods"):
            st.cache_data.clear()
            st.rerun()
    
    with col_b:
        if st.button("Update Profile", help="Change your profile settings"):
            st.session_state.user_profile = None
            st.rerun()
    
    # Footer
    st.markdown("---")

def setup_profile():
    """Fast profile setup function"""
    st.title("Welcome to Nutrition Network!")
    st.markdown("Let's quickly set up your personalized nutrition profile:")
    
    with st.form("profile_setup"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Name", placeholder="Enter your name")
            age = st.number_input("Age", min_value=13, max_value=120, value=25)
            gender = st.selectbox("Gender", ["Male", "Female", "Other"])
            
        with col2:
            weight_lbs = st.number_input("Weight (lbs)", min_value=66.0, max_value=660.0, value=154.0, step=0.5)
            
            # Height input
            height_col1, height_col2 = st.columns(2)
            with height_col1:
                height_feet = st.number_input("Height (feet)", min_value=3, max_value=8, value=5)
            with height_col2:
                height_inches = st.number_input("Height (inches)", min_value=0, max_value=11, value=7)
            
        # Activity and goal
        activity_level = st.selectbox("Activity Level", [
            "Sedentary (little or no exercise)",
            "Lightly active (light exercise/sports 1-3 days/week)", 
            "Moderately active (moderate exercise/sports 3-5 days/week)",
            "Very active (hard exercise/sports 6-7 days a week)",
            "Extra active (very hard exercise/sports & physical job)"
        ])
        
        goal = st.selectbox("Primary Goal", [
            "Lose weight",
            "Maintain weight", 
            "Gain weight (muscle)"
        ])
        
        submitted = st.form_submit_button("Create My Profile", type="primary", use_container_width=True)
        
        if submitted and name and age:
            # Convert measurements
            weight = convert_weight_to_kg(weight_lbs)
            height = convert_height_to_cm(height_feet, height_inches)
            
            # Calculate goals
            bmr = calculate_bmr(weight, height, age, gender)
            tdee = calculate_tdee(bmr, activity_level)
            
            # Adjust calories based on goal
            if goal == "Lose weight":
                daily_calories = int(tdee - 500)
            elif goal == "Gain weight (muscle)":
                daily_calories = int(tdee + 300)
            else:
                daily_calories = int(tdee)
            
            macros = calculate_macros(daily_calories, goal)
            
            # Save profile
            st.session_state.user_profile = {
                'name': name,
                'age': age,
                'gender': gender,
                'weight': weight,
                'height': height,
                'activity_level': activity_level,
                'goal': goal,
                'bmr': bmr,
                'tdee': tdee,
                'daily_goals': {
                    'calories': daily_calories,
                    'protein': int(macros['protein']),
                    'carbs': int(macros['carbs']),
                    'fat': int(macros['fat']),
                    'fiber': int(macros['fiber'])
                }
            }
            
            st.success(f"Profile created successfully! Welcome, {name}!")
            st.balloons()
            st.rerun()

if __name__ == "__main__":
    main()