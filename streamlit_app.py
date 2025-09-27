import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
import os
import time
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="BYTE Health Dashboard",
    page_icon="⚕️",
    layout="wide"
)

# Initialize AI variables
AI_ENABLED = False
model = None

# Configure Gemini AI
try:
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    
    if gemini_api_key:
        genai.configure(api_key=gemini_api_key)
        
        # Get the list of available models that support generateContent
        try:
            models = list(genai.list_models())
            available_models = [model.name for model in models if 'generateContent' in model.supported_generation_methods]
            
            # Try to use the first available model that supports generateContent
            model = None
            if available_models:
                for model_name in available_models:
                    try:
                        model = genai.GenerativeModel(model_name)
                        # Test the model with a simple prompt
                        test_response = model.generate_content("Hello")
                        AI_ENABLED = True
                        break
                    except Exception:
                        continue
            
            if not model:
                AI_ENABLED = False
                st.sidebar.warning("AI Assistant unavailable")
                
        except Exception:
            AI_ENABLED = False
            st.sidebar.warning("AI Assistant unavailable")
    else:
        AI_ENABLED = False
        st.sidebar.info("Add GEMINI_API_KEY to enable AI features")
except Exception:
    AI_ENABLED = False
    st.sidebar.warning("AI Assistant unavailable")

def list_available_models():
    """Debug function to list available Gemini models"""
    try:
        models = genai.list_models()
        return [model.name for model in models]
    except Exception as e:
        return [f"Error listing models: {e}"]

def get_ai_nutrition_advice(foods, user_profile):
    """Generate personalized nutrition advice using Gemini AI"""
    if not AI_ENABLED:
        return "AI recommendations unavailable. Please add your GEMINI_API_KEY to the .env file."
    
    try:
        # Calculate current intake from foods
        current_intake = calculate_daily_totals(foods)
        
        # Calculate daily goals based on user profile
        weight = user_profile['weight']  # already in kg
        height = user_profile['height']  # already in cm
        age = user_profile['age']
        gender = user_profile['gender']
        activity_level = user_profile['activity_level']
        goal = user_profile['goal']
        
        bmr = calculate_bmr(weight, height, age, gender)
        tdee = calculate_tdee(bmr, activity_level)
        
        # Adjust calories based on goal
        if goal == "Lose weight":
            daily_calories = tdee - 500
        elif goal == "Gain weight":
            daily_calories = tdee + 300
        else:  # Maintain weight
            daily_calories = tdee
            
        daily_goals = calculate_macros(daily_calories, goal)
        
        # Calculate nutrient gaps
        protein_gap = daily_goals['protein'] - current_intake['protein']
        carbs_gap = daily_goals['carbs'] - current_intake['carbs']
        fat_gap = daily_goals['fat'] - current_intake['fat']
        calorie_gap = daily_goals['calories'] - current_intake['calories']
        
        # Recent foods for context
        recent_foods = foods[-3:] if foods else []
        recent_food_names = [food.get('name', 'Unknown') for food in recent_foods]
        
        prompt = f"""
        As a professional nutritionist, analyze this user's profile and provide personalized recommendations:

        USER PROFILE:
        - Age: {user_profile['age']}
        - Gender: {user_profile['gender']}
        - Weight: {convert_kg_to_pounds(user_profile['weight'])} lbs
        - Height: {convert_cm_to_feet_inches(user_profile['height'])[0]}'{convert_cm_to_feet_inches(user_profile['height'])[1]}"
        - Activity Level: {user_profile['activity_level']}
        - Primary Goal: {user_profile['goal']}
        - Dietary Preferences: {', '.join(user_profile.get('dietary_preferences', [])) or 'None'}
        - Allergies: {', '.join(user_profile.get('allergies', [])) or 'None'}

        CURRENT NUTRITION STATUS:
        - Calories: {current_intake['calories']}/{daily_goals['calories']} (Gap: {calorie_gap})
        - Protein: {current_intake['protein']}g/{daily_goals['protein']}g (Gap: {protein_gap}g)
        - Carbs: {current_intake['carbs']}g/{daily_goals['carbs']}g (Gap: {carbs_gap}g)
        - Fat: {current_intake['fat']}g/{daily_goals['fat']}g (Gap: {fat_gap}g)

        RECENTLY SCANNED FOODS: {', '.join(recent_food_names) if recent_food_names else 'None today'}

        Provide 3-4 specific, actionable recommendations focusing on:
        1. Addressing nutrient gaps for their goal
        2. Meal/snack suggestions considering their preferences and allergies
        3. Timing advice based on activity level
        4. One motivational insight about their progress

        Keep responses concise and practical. Use bullet points.
        """
        
        response = model.generate_content(prompt)
        return response.text if response.text else "Unable to generate recommendations at this time."
        
    except Exception as e:
        return f"Error generating AI advice: {str(e)}"

def get_food_analysis(food_item, user_profile):
    """Analyze a scanned food item with AI feedback"""
    if not AI_ENABLED:
        return "AI analysis unavailable."
        
    try:
        prompt = f"""
        As a nutrition expert, analyze this food for a user with goal: {user_profile['goal']}
        
        Food: {food_item.get('name', 'Unknown food')}
        Calories per 100g: {food_item.get('calories', 0)}
        Protein: {food_item.get('protein', 0)}g
        Carbs: {food_item.get('carbs', 0)}g  
        Fat: {food_item.get('fat', 0)}g
        Fiber: {food_item.get('fiber', 0)}g
        Sugar: {food_item.get('sugar', 0)}g
        
        User's goal: {user_profile['goal']}
        Dietary preferences: {', '.join(user_profile.get('dietary_preferences', [])) or 'None'}
        
        Provide a brief 2-3 line analysis:
        - Is this food aligned with their goal?
        - One specific benefit or concern
        - A healthier alternative if needed
        
        Be encouraging but honest.
        """
        
        response = model.generate_content(prompt)
        return response.text if response.text else "Analysis unavailable."
        
    except Exception as e:
        return f"Analysis error: {str(e)}"

def get_ai_chat_response(user_question, user_profile, current_intake, daily_goals):
    """Handle user questions with AI chat"""
    if not AI_ENABLED:
        return "AI chat unavailable. Please add your GEMINI_API_KEY."
        
    try:
        prompt = f"""
        You are a friendly, knowledgeable nutrition coach. Answer this user's question:
        
        Question: {user_question}
        
        User Context:
        - Goal: {user_profile['goal']}
        - Activity: {user_profile['activity_level']}
        - Today's calories: {current_intake['calories']}/{daily_goals['calories']}
        - Today's protein: {current_intake['protein']}g/{daily_goals['protein']}g
        - Dietary preferences: {', '.join(user_profile.get('dietary_preferences', [])) or 'None'}
        - Allergies: {', '.join(user_profile.get('allergies', [])) or 'None'}
        
        Provide a helpful, personalized response. Be encouraging and specific to their situation.
        Keep it conversational and under 150 words.
        """
        
        response = model.generate_content(prompt)
        return response.text if response.text else "I'm having trouble responding right now. Please try again!"
        
    except Exception as e:
        return f"Chat error: {str(e)}"

def load_scanned_foods():
    """Load scanned foods from JSON file"""
    try:
        if os.path.exists('scanned_foods.json'):
            with open('scanned_foods.json', 'r') as f:
                data = json.load(f)
                return data.get('foods', [])
        return []
    except Exception as e:
        st.error(f"Error loading scanned foods: {e}")
        return []

def clear_scanned_foods():
    """Clear all scanned foods data"""
    try:
        # Clear the JSON file
        with open('scanned_foods.json', 'w') as f:
            json.dump({'foods': []}, f)
        
        # Clear session state
        if 'daily_intake' in st.session_state:
            st.session_state.daily_intake = {
                'calories': 0,
                'protein': 0,
                'carbs': 0,
                'fat': 0,
                'fiber': 0,
                'sugar': 0,
                'foods': []
            }
    except Exception as e:
        st.error(f"Error clearing scanned foods: {e}")

def calculate_daily_totals(foods):
    """Calculate daily nutrition totals from scanned foods"""
    totals = {
        'calories': 0,
        'protein': 0,
        'carbs': 0,
        'fat': 0,
        'fiber': 0,
        'sugar': 0
    }
    
    for food in foods:
        # Skip foods without nutrition info
        if 'calories' not in food:
            continue
            
        # Add to totals
        for nutrient in totals.keys():
            if nutrient in food:
                totals[nutrient] += food.get(nutrient, 0)
    
    return totals

# Load scanned foods and update daily intake
scanned_foods = load_scanned_foods()
daily_totals = calculate_daily_totals(scanned_foods)

if 'daily_intake' not in st.session_state:
    st.session_state.daily_intake = {
        'calories': daily_totals['calories'],
        'protein': daily_totals['protein'],
        'carbs': daily_totals['carbs'],
        'fat': daily_totals['fat'],
        'fiber': daily_totals['fiber'],
        'sugar': daily_totals['sugar'],
        'foods': scanned_foods
    }
else:
    # Update with latest scanned foods
    st.session_state.daily_intake.update({
        'calories': daily_totals['calories'],
        'protein': daily_totals['protein'],
        'carbs': daily_totals['carbs'],
        'fat': daily_totals['fat'],
        'fiber': daily_totals['fiber'],
        'sugar': daily_totals['sugar'],
        'foods': scanned_foods
    })

def convert_height_to_cm(feet, inches):
    """Convert height from feet and inches to centimeters"""
    total_inches = (feet * 12) + inches
    return total_inches * 2.54

def convert_weight_to_kg(pounds):
    """Convert weight from pounds to kilograms"""
    return pounds / 2.20462

def convert_cm_to_feet_inches(cm):
    """Convert height from centimeters to feet and inches"""
    total_inches = cm / 2.54
    feet = int(total_inches // 12)
    inches = round(total_inches % 12, 1)
    return feet, inches

def convert_kg_to_pounds(kg):
    """Convert weight from kilograms to pounds"""
    return round(kg * 2.20462, 1)

def calculate_bmr(weight, height, age, gender):
    """Calculate Basal Metabolic Rate using Mifflin-St Jeor Equation"""
    if gender.lower() == 'male':
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
    return bmr

def calculate_tdee(bmr, activity_level):
    """Calculate Total Daily Energy Expenditure"""
    activity_multipliers = {
        "Sedentary (little or no exercise)": 1.2,
        "Lightly active (light exercise/sports 1-3 days/week)": 1.375,
        "Moderately active (moderate exercise/sports 3-5 days/week)": 1.55,
        "Very active (hard exercise/sports 6-7 days a week)": 1.725,
        "Extra active (very hard exercise/sports & physical job)": 1.9
    }
    return bmr * activity_multipliers.get(activity_level, 1.2)

def calculate_macros(calories, goal):
    """Calculate recommended macronutrient distribution"""
    if goal == "Lose weight":
        # Higher protein for weight loss
        protein_ratio = 0.30
        fat_ratio = 0.25
        carb_ratio = 0.45
    elif goal == "Gain weight (muscle)":
        # Balanced for muscle gain
        protein_ratio = 0.25
        fat_ratio = 0.25
        carb_ratio = 0.50
    else:  # Maintain weight
        # Standard balanced diet
        protein_ratio = 0.20
        fat_ratio = 0.30
        carb_ratio = 0.50
    
    return {
        'protein': (calories * protein_ratio) // 4,  # 4 cal per gram
        'fat': (calories * fat_ratio) // 9,         # 9 cal per gram
        'carbs': (calories * carb_ratio) // 4,      # 4 cal per gram
        'fiber': max(25, calories // 100)           # General recommendation
    }

def create_calorie_gauge(current, goal):
    """Create an ultra-vibrant calorie gauge chart"""
    percentage = (current / goal) * 100 if goal > 0 else 0
    
    # Enhanced color scheme with ultra-vibrant colors
    if percentage < 50:
        color = "#FF0000"  # Pure burning red
        status_text = "Need More Fuel"
    elif percentage < 80:
        color = "#FFFF00"  # Electric sunny yellow
        status_text = "Getting There"
    elif percentage <= 100:
        color = "#00FF00"  # Neon leaf green
        status_text = "Perfect Zone"
    else:
        color = "#FF4500"  # Bright orange for over
        status_text = "Over Target"
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = current,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': f"Daily Calories<br><span style='font-size:0.8em'>{status_text}</span>"},
        delta = {'reference': goal, 'position': "top"},
        gauge = {
            'axis': {'range': [None, goal * 1.2]},
            'bar': {'color': color, 'thickness': 0.8},
            'steps': [
                {'range': [0, goal * 0.5], 'color': "rgba(255, 0, 0, 0.2)"},
                {'range': [goal * 0.5, goal * 0.8], 'color': "rgba(255, 255, 0, 0.2)"},
                {'range': [goal * 0.8, goal], 'color': "rgba(0, 255, 0, 0.2)"}
            ],
            'threshold': {
                'line': {'color': "black", 'width': 4},
                'thickness': 0.75,
                'value': goal
            }
        }
    ))
    
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={'color': "black", 'family': "Arial"},
        height=300
    )
    
    return fig

# Initialize profile if not exists
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = None

# Profile setup
if st.session_state.user_profile is None:
    st.title("Welcome to BYTE Health!")
    st.markdown("Let's set up your personalized nutrition profile:")
    
    with st.form("profile_setup"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Name", placeholder="Enter your name")
            age = st.number_input("Age", min_value=13, max_value=120, value=25)
            gender = st.selectbox("Gender/Sex", ["Male", "Female", "Other"])
            
        with col2:
            weight_lbs = st.number_input("Weight (lbs)", min_value=66.0, max_value=660.0, value=154.0, step=0.5)
            
            # Height input using feet and inches
            height_col1, height_col2 = st.columns(2)
            with height_col1:
                height_feet = st.number_input("Height (feet)", min_value=3, max_value=8, value=5, step=1)
            with height_col2:
                height_inches = st.number_input("Height (inches)", min_value=0, max_value=11, value=7, step=1)
            
            # Convert to metric for calculations
            weight = convert_weight_to_kg(weight_lbs)
            height = convert_height_to_cm(height_feet, height_inches)
            
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
        
        # Dietary preferences and allergies
        st.markdown("### Optional Information")
        col3, col4 = st.columns(2)
        
        with col3:
            dietary_preferences = st.multiselect("Dietary Preferences", [
                "Vegetarian", "Vegan", "Keto", "Paleo", "Mediterranean", 
                "Low-carb", "High-protein", "Gluten-free"
            ])
            
        with col4:
            allergies = st.multiselect("Food Allergies", [
                "Peanuts", "Tree nuts", "Dairy", "Eggs", "Soy", 
                "Wheat/Gluten", "Fish", "Shellfish", "Sesame"
            ])
        
        submitted = st.form_submit_button("Create My Profile", type="primary", use_container_width=True)
        
        if submitted and name and age and weight and height:
            # Calculate daily goals
            bmr = calculate_bmr(weight, height, age, gender)
            tdee = calculate_tdee(bmr, activity_level)
            
            # Adjust calories based on goal
            if goal == "Lose weight":
                daily_calories = tdee - 500  # 500 calorie deficit
            elif goal == "Gain weight (muscle)":
                daily_calories = tdee + 300  # 300 calorie surplus
            else:
                daily_calories = tdee  # Maintenance
            
            macros = calculate_macros(daily_calories, goal)
            
            st.session_state.user_profile = {
                'name': name,
                'age': age,
                'gender': gender,
                'weight': weight,
                'height': height,
                'activity_level': activity_level,
                'goal': goal,
                'dietary_preferences': dietary_preferences,
                'allergies': allergies,
                'bmr': bmr,
                'tdee': tdee,
                'daily_goals': {
                    'calories': int(daily_calories),
                    'protein': int(macros['protein']),
                    'carbs': int(macros['carbs']),
                    'fat': int(macros['fat']),
                    'fiber': int(macros['fiber'])
                }
            }
            
            # Clear any previous scanned foods data for new user
            clear_scanned_foods()
            st.rerun()

# Main app interface
if st.session_state.user_profile:
    profile = st.session_state.user_profile
    
    # Sidebar navigation
    page = st.sidebar.selectbox("Choose a page", 
        ["Dashboard", "AI Coach", "Scanner", "Analytics", "Profile"])
    
    # Sidebar profile summary
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Your Profile")
    st.sidebar.markdown(f"**Goal:** {profile['goal']}")
    st.sidebar.markdown(f"**Activity:** {profile['activity_level']}")
    if profile['dietary_preferences']:
        st.sidebar.markdown(f"**Diet:** {', '.join(profile['dietary_preferences'])}")
    
    # AI status in sidebar
    if AI_ENABLED:
        st.sidebar.success("AI Coach Active")
    else:
        st.sidebar.warning("🔑 Add GEMINI_API_KEY for AI features")

    if page == "Dashboard":
        st.header(f"Hi {profile['name']}! Today's Nutrition Dashboard")
        
        # Get current intake and goals
        intake = st.session_state.daily_intake
        goals = profile['daily_goals']
        
        # Check if user has scanned any foods yet
        has_food_data = len(intake['foods']) > 0
        
        if has_food_data:
            # Featured calorie gauge - make it pop!
            st.markdown("### Today's Calorie Progress")
            
            # Create a more prominent display for calories
            col1, col2 = st.columns([3, 2])
            
            with col1:
                # Enhanced styling for maximum visual impact
                st.markdown("""
                <style>
                .calorie-container {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 20px;
                    border-radius: 15px;
                    box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
                    backdrop-filter: blur(8.5px);
                    border: 1px solid rgba(255, 255, 255, 0.18);
                }
                </style>
                """, unsafe_allow_html=True)
                
                fig = create_calorie_gauge(intake['calories'], goals['calories'])
                st.plotly_chart(fig, use_container_width=True)
                
                # Progress summary
                remaining_cals = goals['calories'] - intake['calories']
                if remaining_cals > 0:
                    st.success(f"{remaining_cals} calories remaining to reach your goal!")
                elif remaining_cals == 0:
                    st.balloons()
                    st.success("Perfect! You've hit your calorie target!")
                else:
                    st.warning(f"{abs(remaining_cals)} calories over target")
            
            with col2:
                st.markdown("### Daily Targets")
                
                # Macro nutrients with progress bars
                nutrients = [
                    ("Protein", intake['protein'], goals['protein'], "g", "Protein"),
                    ("Carbs", intake['carbs'], goals['carbs'], "g", "Carbs"),
                    ("Fat", intake['fat'], goals['fat'], "g", "Fat"),
                    ("Fiber", intake['fiber'], goals['fiber'], "g", "Fiber")
                ]
                
                for name, current, goal, unit, emoji in nutrients:
                    progress = min(current / goal, 1.0)
                    remaining = max(goal - current, 0)
                    
                    st.markdown(f"**{emoji} {name}**")
                    st.progress(progress)
                    st.markdown(f"{current}{unit} / {goal}{unit} ({remaining}{unit} remaining)")
                    st.markdown("---")
        else:
            # Welcome message for new users
            st.markdown("### Welcome to Your Dashboard!")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown("""
                <div style="
                    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                    padding: 30px;
                    border-radius: 15px;
                    color: white;
                    text-align: center;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                ">
                <h2>Ready to start your health journey?</h2>
                <p style="font-size: 18px;">Scan your first food item to see your personalized dashboard come to life!</p>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("### Get Started")
                
                if st.button("Open Scanner", type="primary", use_container_width=True):
                    st.markdown("**Scanner URL:** http://127.0.0.1:5001")
                    st.markdown("Open this link in your browser to start scanning!")
                
                if st.checkbox("Auto-refresh (updates when foods are scanned)", value=True):
                    time.sleep(1)
                    st.rerun()
                
            with col2:
                st.markdown("**How it works:**")
                st.markdown("1. Open the scanner")
                st.markdown("2. Point camera at barcode")  
                st.markdown("3. Food automatically logged")
                st.markdown("4. Dashboard updates instantly")
        
        # Today's food log
        st.subheader("Today's Food Log")
        
        if intake['foods']:
            food_df = pd.DataFrame(intake['foods'])
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.dataframe(food_df, use_container_width=True)
            
            with col2:
                # Simple pie chart of foods by calories
                fig_pie = px.pie(
                    food_df, 
                    values='calories', 
                    names='name',
                    title="Calorie Distribution"
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No foods logged yet today. Use the scanner to add foods!")

    elif page == "AI Coach":
        st.header("Your Personal AI Nutrition Coach")
        
        if AI_ENABLED:
            # Get current data
            intake = st.session_state.daily_intake
            goals = profile['daily_goals']
            
            # AI Recommendations Section
            st.markdown("### Personalized Recommendations")
            
            with st.spinner("Generating personalized recommendations..."):
                ai_advice = get_ai_nutrition_advice(scanned_foods, profile)
            
            # Display AI recommendations in an attractive format
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 20px;
                border-radius: 10px;
                color: white;
                margin: 10px 0;
            ">
            """, unsafe_allow_html=True)
            
            st.markdown("**Your AI Nutrition Coach says:**")
            st.markdown(ai_advice)
            st.markdown("</div>", unsafe_allow_html=True)
            
            # Food analysis for recently scanned items
            if scanned_foods and len(scanned_foods) > 0:
                st.markdown("### Recent Food Analysis")
                
                # Show analysis for last 3 foods
                for i, food in enumerate(reversed(scanned_foods[-3:])):
                    with st.expander(f"AI Analysis: {food.get('name', 'Unknown Food')}", expanded=(i==0)):
                        food_analysis = get_food_analysis(food, profile)
                        st.markdown(food_analysis)

            # AI Chat Interface
            st.markdown("---")
            st.subheader("Chat with Your AI Coach")
            
            # Initialize chat history
            if 'chat_history' not in st.session_state:
                st.session_state.chat_history = []
            
            # Chat input
            user_question = st.text_input(
                "Ask me anything about nutrition:", 
                placeholder="e.g., 'What should I eat for dinner?' or 'How can I increase my protein?'",
                key="ai_chat_input"
            )
            
            if user_question:
                # Get AI response
                with st.spinner("Thinking..."):
                    ai_response = get_ai_chat_response(user_question, profile, intake, goals)
                
                # Add to chat history
                st.session_state.chat_history.append({
                    "question": user_question,
                    "answer": ai_response,
                    "timestamp": datetime.now().strftime("%H:%M")
                })
                
                # Show the latest response immediately
                st.success("**AI Coach Response:**")
                st.write(ai_response)
            
            # Display chat history
            if st.session_state.chat_history:
                st.markdown("**Recent Conversations:**")
                
                # Show last 5 conversations
                for i, chat in enumerate(reversed(st.session_state.chat_history[-5:])):
                    with st.expander(f"Q: {chat['question'][:50]}... ({chat['timestamp']})", expanded=(i==0)):
                        st.markdown(f"**You:** {chat['question']}")
                        st.markdown(f"**AI Coach:** {chat['answer']}")
                
                # Clear chat button
                if st.button("Clear Chat History"):
                    st.session_state.chat_history = []
                    st.rerun()
        else:
            st.warning("🔑 AI Coach features require a GEMINI_API_KEY!")
            st.markdown("""
            **Add your Gemini API key to unlock:**
            - Personalized nutrition recommendations
            - Real-time food analysis  
            - Goal-specific meal suggestions
            - Interactive nutrition coaching
            - Smart insights based on your progress
            
            **How to add your API key:**
            1. Get a free API key from Google AI Studio
            2. Add `GEMINI_API_KEY=your_key_here` to your .env file
            3. Restart the app to activate AI features
            """)

    elif page == "Scanner":
        st.header("Barcode Scanner Integration")
        st.info("Your barcode scanner is available at: http://127.0.0.1:5001")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### Live Scanner")
            st.markdown("Click the link above to open the automatic barcode scanner in your browser.")
            st.markdown("The scanner will automatically detect and log food items to your dashboard.")
            
            if st.button("Open Live Scanner", type="primary"):
                st.markdown("**Opening:** http://127.0.0.1:5001")
                st.balloons()
            
        with col2:
            st.markdown("### Upload Image")
            st.markdown("Alternatively, you can upload a photo of a barcode:")
            uploaded_file = st.file_uploader("Choose barcode image", type=['png', 'jpg', 'jpeg'])
            if uploaded_file:
                st.image(uploaded_file, caption="Uploaded barcode", use_column_width=True)
        
        st.subheader("Recent Scans")
        
        if scanned_foods:
            # Show recent scans with AI analysis if available
            for food in reversed(scanned_foods[-5:]):  # Last 5 items
                with st.expander(f"{food.get('name', 'Unknown')} - {food.get('calories', 0)} cal"):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.json(food)
                    with col2:
                        if AI_ENABLED:
                            st.markdown("**AI Analysis:**")
                            analysis = get_food_analysis(food, profile)
                            st.markdown(analysis)
        else:
            st.info("No scanned foods yet. Start scanning to see your history!")

    elif page == "Analytics":
        st.header("Nutrition Analytics & Trends")
        
        intake = st.session_state.daily_intake
        goals = profile['daily_goals']
        
        if intake['foods']:
            # Weekly overview (simulated data for demo)
            st.subheader("Weekly Trends")
            
            # Create sample weekly data
            days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            calories_data = [intake['calories'] * (0.8 + 0.4 * np.random.random()) for _ in days]
            
            fig_line = go.Figure()
            fig_line.add_trace(go.Scatter(x=days, y=calories_data, mode='lines+markers', name='Daily Calories'))
            fig_line.add_hline(y=goals['calories'], line_dash="dash", annotation_text="Target")
            fig_line.update_layout(title="Weekly Calorie Intake", xaxis_title="Day", yaxis_title="Calories")
            st.plotly_chart(fig_line, use_container_width=True)
            
            # Goal achievement metrics
            st.subheader("Goal Achievement")
            
            col1, col2, col3, col4 = st.columns(4)
            
            metrics = [
                ("Calories", intake['calories'], goals['calories']),
                ("Protein", intake['protein'], goals['protein']), 
                ("Carbs", intake['carbs'], goals['carbs']),
                ("Fat", intake['fat'], goals['fat'])
            ]
            
            for col, (name, current, target) in zip([col1, col2, col3, col4], metrics):
                with col:
                    percentage = (current / target * 100) if target > 0 else 0
                    st.metric(name, f"{current:.1f}", f"{percentage:.1f}% of goal")
        else:
            st.info("Analytics will appear once you start logging foods!")
        
        st.subheader("Weekly Summary")
        st.info("Advanced analytics coming soon! Track your progress over time.")

    elif page == "Profile":
        st.header("Your Profile & Settings")
        
        if profile:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.subheader("Personal Information")
                st.markdown(f"**Name:** {profile['name']}")
                st.markdown(f"**Age:** {profile['age']} years")
                st.markdown(f"**Gender:** {profile['gender']}")
                st.markdown(f"**Weight:** {convert_kg_to_pounds(profile['weight'])} lbs")
                feet, inches = convert_cm_to_feet_inches(profile['height'])
                st.markdown(f"**Height:** {feet}'{inches}\"")
                st.markdown(f"**Activity Level:** {profile['activity_level']}")
                st.markdown(f"**Primary Goal:** {profile['goal']}")
                
            with col2:
                st.subheader("Calculated Targets")
                st.markdown(f"**BMR:** {profile['bmr']:.0f} calories/day")
                st.markdown(f"**TDEE:** {profile['tdee']:.0f} calories/day")
                st.markdown(f"**Daily Calories:** {profile['daily_goals']['calories']} cal")
                st.markdown(f"**Protein:** {profile['daily_goals']['protein']}g")
                st.markdown(f"**Carbs:** {profile['daily_goals']['carbs']}g")
                st.markdown(f"**Fat:** {profile['daily_goals']['fat']}g")
                st.markdown(f"**Fiber:** {profile['daily_goals']['fiber']}g")
            
            col3, col4 = st.columns(2)
            
            with col3:
                st.subheader("Dietary Preferences")
                if profile['dietary_preferences']:
                    for pref in profile['dietary_preferences']:
                        st.markdown(f"✅ {pref}")
                else:
                    st.markdown("None specified")
                    
            with col4:
                st.subheader("Food Allergies")
                if profile['allergies']:
                    for allergy in profile['allergies']:
                        st.markdown(f"{allergy}")
                else:
                    st.markdown("None specified")
        
        # Update profile button
        if st.button("Update Profile", type="secondary"):
            st.session_state.user_profile = None
            st.rerun()

# Footer
st.markdown("---")
st.markdown("*BYTE Health App - Your personalized nutrition companion!*")