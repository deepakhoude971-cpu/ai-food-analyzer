import streamlit as st
from google import genai
from PIL import Image
import json
import time
import plotly.express as px

# 1. Page Configuration & Title
st.set_page_config(page_title="AI Food & Micronutrient Analyzer", page_icon="🥗", layout="wide")
st.title("🥗 AI Food Recognition & Micronutrient Analyzer")
st.write("Upload a food image to get instant calorie estimation, macro breakdown, and micronutrient analysis.")

# 2. Sidebar for API Key Input
st.sidebar.header("🔑 API Setup")
api_key = st.sidebar.text_input("Enter Google Gemini API Key:", type="password")
st.sidebar.markdown("[Get Free API Key Here](https://google.com)")

# 3. Main UI Components
uploaded_file = st.file_uploader("Choose a food image...", type=["jpg", "jpeg", "png"])
portion_size = st.selectbox(
    "Select Estimated Portion Size:",
    ["Standard Serving", "Small (Half Portion)", "Large (Double Portion)", "100 grams"]
)

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    col1, col2 = st.columns(2)

    with col1:
        st.image(image, caption="Uploaded Food Image", use_container_width=True)
        submit = st.button("📊 Analyze Nutritional Value")

    if submit:
        if not api_key:
            st.error("Please enter your Gemini API Key in the sidebar to proceed!")
        else:
            with st.spinner("AI is analyzing your food... Please wait..."):
                try:
                    client = genai.Client(api_key=api_key.strip())

                    prompt = f"""
                    You are an expert nutritionist AI. Analyze the provided food image based on the portion size: '{portion_size}'.
                    Identify the food items, estimate the calories, macronutrients, and key micronutrients.
                    You MUST respond ONLY with a valid JSON object matching this exact structure:
                    {{
                        "food_name": "Name of the dish or food items identified",
                        "calories": 350,
                        "protein_g": 15,
                        "carbs_g": 45,
                        "fat_g": 12,
                        "micronutrients": {{
                            "Iron (mg)": 2.5,
                            "Calcium (mg)": 120,
                            "Vitamin C (mg)": 45,
                            "Potassium (mg)": 350,
                            "Sodium (mg)": 200
                        }},
                        "health_insight": "A brief 2-sentence expert advice or health warning about this meal."
                    }}
                    Do not include any markdown formatting, triple backticks (```), or extra text outside the JSON.
                    """

                    # Auto-Retry with Backup Model if 503 High Demand happens
                    models_to_try = ['gemini-3.8-flash', 'gemini-3.8-flash-lite', 'gemini-3.8-flash']
                    response = None
                    last_error = None

                    for model_name in models_to_try:
                        try:
                            response = client.models.generate_content(
                                model=model_name,
                                contents=(image, prompt)
                            )
                            break
                        except Exception as err:
                            last_error = err
                            if "503" in str(err) or "UNAVAILABLE" in str(err):
                                time.sleep(2)
                                continue
                            else:
                                raise err

                    if response is None:
                        raise last_error

                    # Clean response string
                    raw_text = response.text.strip()
                    if raw_text.startswith("```json"):
                        raw_text = raw_text.replace("```json", "").replace("```", "").strip()
                    elif raw_text.startswith("```"):
                        raw_text = raw_text.replace("```", "").strip()

                    data = json.loads(raw_text)

                    # Display Results in Column 2
                    with col2:
                        st.success(f"Food Identified: **{data['food_name']}**")

                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Calories", f"{data['calories']} kcal")
                        m2.metric("Protein", f"{data['protein_g']}g")
                        m3.metric("Carbs", f"{data['carbs_g']}g")
                        m4.metric("Fat", f"{data['fat_g']}g")

                        st.subheader("🥪 Macronutrient Distribution")
                        macro_data = {
                            "Nutrient": ["Protein", "Carbohydrates", "Fats"],
                            "Grams": [data['protein_g'], data['carbs_g'], data['fat_g']]
                        }
                        fig = px.pie(
                            macro_data,
                            values="Grams",
                            names="Nutrient",
                            hole=0.4,
                            color_discrete_sequence=px.colors.qualitative.Pastel
                        )
                        st.plotly_chart(fig, use_container_width=True)

                        st.subheader("🔬 Micronutrient Analysis")
                        st.table(data['micronutrients'])

                        st.info(f"💡 **AI Health Insight:** {data['health_insight']}")

                except json.JSONDecodeError:
                    st.error("Failed to parse AI response. Please click Analyze again.")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
