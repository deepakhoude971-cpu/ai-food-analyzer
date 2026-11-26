import datetime
import json
import time
from google import genai
from google.genai import types
from PIL import Image
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(
    page_title="AI Food & Micronutrient Analyzer", page_icon="🥗", layout="wide"
)
st.markdown(
    """<style>
[data-testid="stMetric"] { background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); padding: 15px; border-radius: 12px; }
.stButton>button { background: linear-gradient(90deg, #10b981 0%, #059669 100%); color: white; border: none; border-radius: 10px; font-weight: bold; }
</style>""",
    unsafe_allow_html=True,
)

st.title("🥗 AI Food Recognition & Micronutrient Analyzer")
st.write(
    "Upload a food image to get instant calorie estimation, macro breakdown,"
    " and micronutrient analysis."
)

if "meal_history" not in st.session_state:
    st.session_state.meal_history = []

if "GEMINI_API_KEY" not in st.secrets:
    st.error(
        "API Key missing! Add GEMINI_API_KEY in Streamlit Settings > Secrets."
    )
    st.stop()

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"].strip())
USDA_API_KEY = st.secrets.get("USDA_API_KEY", "DEMO_KEY")


def get_usda_data(ingredient, grams):
    try:
        res = requests.get(
            "https://usda.gov",
            params={
                "api_key": USDA_API_KEY,
                "query": ingredient,
                "dataType": ["Foundation", "SR Legacy", "Survey (FNDDS)"],
                "pageSize": 1,
            },
            timeout=5,
        ).json()
        foods = res.get("foods")
        if foods:
            first_food = next(iter(foods))
            n = {
                x["nutrientName"]: x["value"]
                for x in first_food["foodNutrients"]
            }
            f = grams / 100.0
            return {
                "cal": n.get("Energy", 0) * f,
                "pro": n.get("Protein", 0) * f,
                "carb": n.get("Carbohydrate, by difference", 0) * f,
                "fat": n.get("Total lipid (fat)", 0) * f,
                "iron": n.get("Iron, Fe", 0) * f,
                "calc": n.get("Calcium, Ca", 0) * f,
                "vitc": n.get("Vitamin C, total ascorbic acid", 0) * f,
                "pot": n.get("Potassium, K", 0) * f,
                "sod": n.get("Sodium, Na", 0) * f,
            }
    except Exception:
        return None


uploaded_file = st.file_uploader(
    "Choose a food image...", type=["jpg", "jpeg", "png"]
)
portion_size = st.selectbox(
    "Select Estimated Portion Size:",
    [
        "Standard Serving",
        "Small (Half Portion)",
        "Large (Double Portion)",
        "100 grams",
    ],
)

if uploaded_file:
    image = Image.open(uploaded_file)
    image.thumbnail((450, 450))
    col1, col2 = st.columns(2)
    with col1:
        st.image(image, caption="Uploaded Image", use_container_width=True)
        extra_notes = st.text_input(
            "Optional: Type ingredients/details (e.g., 'peanut butter, 1 tsp"
            " ghee, less sugar'):"
        )
        submit = st.button("📊 Analyze Nutritional Value", type="primary")

    if submit:
        with st.spinner("Analyzing food & calculating nutrition..."):
            try:
                prompt = f"""Check if image has food or drink. If NO, return {{"is_food": false}}.
                If YES, use user's optional notes: "{extra_notes}" as ground truth if provided, and look VERY closely at textures/colors to list EVERY visible item, fruit, seed, spread, liquid, and base food in food_name. Break it into standard English ingredients/liquids scaled for '{portion_size}', and provide fallback values.
                Return ONLY valid JSON:
                {{"is_food": true, "food_name": "<Exact dish + every visible fruit, spread & topping>", "items": [{{"name": "<English ingredient>", "grams": <num>, "fb": {{"cal": <num>, "pro": <num>, "carb": <num>, "fat": <num>, "iron": <num>, "calc": <num>, "vitc": <num>, "pot": <num>, "sod": <num>}}}}], "health_insight": "<2-sentence health tip>"}}"""

                response = None
                last_error = None
                for model_name in [
                    "gemini-3.8-flash",
                    "gemini-3.5-flash",
                    "gemini-3.5-flash-lite",
                ]:
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=list((image, prompt)),
                            config=types.GenerateContentConfig(
                                temperature=0.1,
                                response_mime_type="application/json",
                            ),
                        )
                        break
                    except Exception as err:
                        last_error = err
                        time.sleep(1)
                        continue

                if response is None:
                    st.error(f"Model Error: {str(last_error)}")
                    st.stop()

                data = json.loads(response.text)

                with col2:
                    if not data.get("is_food", True):
                        st.warning(
                            "⚠️ No food detected! Please upload a clear image"
                            " of a meal, fruit, or drink."
                        )
                    else:
                        t = {
                            "cal": 0.0,
                            "pro": 0.0,
                            "carb": 0.0,
                            "fat": 0.0,
                            "iron": 0.0,
                            "calc": 0.0,
                            "vitc": 0.0,
                            "pot": 0.0,
                            "sod": 0.0,
                        }
                        for item in data.get("items", []):
                            vals = get_usda_data(
                                item["name"], float(item["grams"])
                            ) or item.get("fb", t)
                            for k in t:
                                t[k] = t[k] + float(vals.get(k, 0))

                        cal_val = round(t["cal"])
                        pro_val = round(t["pro"], 1)
                        carb_val = round(t["carb"], 1)
                        fat_val = round(t["fat"], 1)

                        st.session_state.meal_history.append({
                            "Time": datetime.datetime.now().strftime(
                                "%I:%M %p"
                            ),
                            "Food / Drink": data["food_name"],
                            "Portion": portion_size,
                            "Calories": cal_val,
                            "Protein (g)": pro_val,
                            "Carbs (g)": carb_val,
                            "Fat (g)": fat_val,
                        })

                        st.success(f"Food Identified: **{data['food_name']}**")
                        st.markdown(
                            "**🥗 Detected Items:**"
                            f" {', '.join(x.get('name', '').title() for x in data.get('items', []))}"
                        )

                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Calories (kcal)", f"{cal_val}")
                        m2.metric("Protein", f"{pro_val}g")
                        m3.metric("Carbs", f"{carb_val}g")
                        m4.metric("Fat", f"{fat_val}g")

                        st.subheader("🥪 Macronutrient Distribution")
                        fig = px.pie(
                            {
                                "Nutrient": ["Protein", "Carbs", "Fats"],
                                "Grams": [pro_val, carb_val, fat_val],
                            },
                            values="Grams",
                            names="Nutrient",
                            hole=0.4,
                            color_discrete_sequence=px.colors.qualitative.Pastel,
                        )
                        st.plotly_chart(fig, use_container_width=True)

                        st.subheader("🔬 Micronutrient Analysis")
                        st.table({
                            "Iron (mg)": round(t["iron"], 2),
                            "Calcium (mg)": round(t["calc"], 1),
                            "Vitamin C (mg)": round(t["vitc"], 1),
                            "Potassium (mg)": round(t["pot"], 1),
                            "Sodium (mg)": round(t["sod"], 1),
                        })

                        st.info(
                            f"💡 **AI Health Insight:** {data['health_insight']}"
                        )
            except Exception as e:
                st.error(f"Error: {str(e)}")

if st.session_state.meal_history:
    st.divider()
    st.subheader("📋 Session Meal History")
    h1, h2, h3, h4 = st.columns(4)
    h1.metric(
        "Total Calories",
        f"{sum(x['Calories'] for x in st.session_state.meal_history)} kcal",
    )
    h2.metric(
        "Total Protein",
        f"{round(sum(x['Protein (g)'] for x in st.session_state.meal_history), 1)}g",
    )
    h3.metric(
        "Total Carbs",
        f"{round(sum(x['Carbs (g)'] for x in st.session_state.meal_history), 1)}g",
    )
    h4.metric(
        "Total Fat",
        f"{round(sum(x['Fat (g)'] for x in st.session_state.meal_history), 1)}g",
    )
    st.table(st.session_state.meal_history)
    if st.button("🗑️ Clear History"):
        st.session_state.meal_history = []
        st.rerun()
