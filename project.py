import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import json
import time
import plotly.express as px

st.set_page_config(page_title="AI Food & Micronutrient Analyzer", page_icon="🥗", layout="wide")
st.title("🥗 AI Food Recognition & Micronutrient Analyzer")
st.write("Upload a food image to get instant calorie estimation, macro breakdown, and micronutrient analysis.")

# Load API key directly from Streamlit Secrets
if "GEMINI_API_KEY" not in st.secrets:
    st.error("API Key missing! Add GEMINI_API_KEY in Streamlit Settings > Secrets.")
    st.stop()

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"].strip())

# Upload & Portion Controls
uploaded_file = st.file_uploader("Choose a food image...", type=["jpg", "jpeg", "png"])
portion_size = st.selectbox("Select Estimated Portion Size:", ["Standard Serving", "Small (Half Portion)", "Large (Double Portion)", "100 grams"])

if uploaded_file:
    image = Image.open(uploaded_file)
    image.thumbnail((450, 450))
    col1, col2 = st.columns(2)

    with col1:
        st.image(image, caption="Uploaded Image", use_container_width=True)
        submit = st.button("📊 Analyze Nutritional Value", type="primary")

    if submit:
        with st.spinner("Analyzing food & calculating nutrition..."):
            try:
                prompt = f"""
                You are an expert nutritionist AI. Check if the image contains actual food or drinks.
                If NO food is present (e.g., human, animal, object, blank page), return ONLY: {{"is_food": false}}
                If food IS present, calculate unique, accurate nutritional values scaled for '{portion_size}'.
                Respond ONLY with valid JSON matching this exact structure (no markdown or extra text):
                {{
                    "is_food": true,
                    "food_name": "<Exact names of visible food items>",
                    "calories": <integer_calories>,
                    "protein_g": <number>,
                    "carbs_g": <number>,
                    "fat_g": <number>,
                    "micronutrients": {{
                        "Iron (mg)": <number>,
                        "Calcium (mg)": <number>,
                        "Vitamin C (mg)": <number>,
                        "Potassium (mg)": <number>,
                        "Sodium (mg)": <number>
                    }},
                    "health_insight": "<Brief 2-sentence health tip specific to this meal>"
                }}
                """

                response = None
                last_error = None
                for model_name in ['gemini-3.5-flash-lite', 'gemini-3.8-flash', 'gemini-3.5-flash']:
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                        contents=(image, prompt),
                            config=types.GenerateContentConfig(temperature=0.4)
                        )
                        break
                    except Exception as err:
                        last_error = err
                        time.sleep(1)
                        continue

                if response is None:
                    st.error(f"Model Error: {str(last_error)}")
                    st.stop()

                raw_text = response.text.replace("```json", "").replace("```", "").strip()
                data = json.loads(raw_text)

                with col2:
                    if not data.get("is_food", True):
                        st.warning("⚠️ No food detected! Please upload a clear image of a meal, fruit, or drink.")
                    else:
                        st.success(f"Food Identified: **{data['food_name']}**")
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Calories", f"{data['calories']} kcal")
                        m2.metric("Protein", f"{data['protein_g']}g")
                        m3.metric("Carbs", f"{data['carbs_g']}g")
                        m4.metric("Fat", f"{data['fat_g']}g")

                        st.subheader("🥪 Macronutrient Distribution")
                        fig = px.pie(
                            {"Nutrient": ["Protein", "Carbs", "Fats"], "Grams": [data['protein_g'], data['carbs_g'], data['fat_g']]},
                            values="Grams", names="Nutrient", hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel
                        )
                        st.plotly_chart(fig, use_container_width=True)

                        st.subheader("🔬 Micronutrient Analysis")
                        st.table(data['micronutrients'])
                        st.info(f"💡 **AI Health Insight:** {data['health_insight']}")

            except json.JSONDecodeError:
                st.error("Failed to parse AI response. Please click Analyze again.")
            except Exception as e:
                st.error(f"Error: {str(e)}")
