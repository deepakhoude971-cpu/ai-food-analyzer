import json
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
        if res.get("foods"):
            n = {
                x["nutrientName"]: x["value"]
                for x in res["foods"]["foodNutrients"]
            }
            f = grams / 100.0
            return [
                n.get("Energy", 0) * f,
                n.get("Protein", 0) * f,
                n.get("Carbohydrate, by difference", 0) * f,
                n.get("Total lipid (fat)", 0) * f,
                n.get("Iron, Fe", 0) * f,
                n.get("Calcium, Ca", 0) * f,
                n.get("Vitamin C, total ascorbic acid", 0) * f,
                n.get("Potassium, K", 0) * f,
                n.get("Sodium, Na", 0) * f,
            ]
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
        submit = st.button("📊 Analyze Nutritional Value", type="primary")

    if submit:
        with st.spinner("Analyzing food & calculating nutrition..."):
            try:
                prompt = f"""Check if image has food or drink. If NO, return {{"is_food": false}}.
                If YES, identify any food, meal, drink, or shake, break it into standard English ingredients/liquids (including oil/ghee/sugar/milk) scaled for '{portion_size}', and provide fallback values.
                Return ONLY valid JSON:
                {{"is_food": true, "food_name": "<Name>", "items": [{{"name": "<English ingredient>", "grams": <num>, "fb": [<cal>, <pro>, <carb>, <fat>, <iron_mg>, <calc_mg>, <vitc_mg>, <pot_mg>, <sod_mg>]}}], "health_insight": "<2-sentence health tip>"}}"""
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1, response_mime_type="application/json"
                    ),
                )
                data = json.loads(response.text)

                with col2:
                    if not data.get("is_food", True):
                        st.warning(
                            "⚠️ No food detected! Please upload a clear image"
                            " of a meal, fruit, or drink."
                        )
                    else:
                        t = [0.0] * 9
                        for item in data.get("items", []):
                            vals = get_usda_data(
                                item["name"], float(item["grams"])
                            ) or item.get("fb", [0] * 9)
                            t = [t[i] + float(vals[i]) for i in range(9)]

                        st.success(f"Food Identified: **{data['food_name']}**")
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Calories", f"{round(t[0])} kcal")
                        m2.metric("Protein", f"{round(t[1], 1)}g")
                        m3.metric("Carbs", f"{round(t[2], 1)}g")
                        m4.metric("Fat", f"{round(t[3], 1)}g")

                        st.subheader("🥪 Macronutrient Distribution")
                        fig = px.pie(
                            {
                                "Nutrient": ["Protein", "Carbs", "Fats"],
                                "Grams": [
                                    round(t[1], 1),
                                    round(t[2], 1),
                                    round(t[3], 1),
                                ],
                            },
                            values="Grams",
                            names="Nutrient",
                            hole=0.4,
                            color_discrete_sequence=px.colors.qualitative.Pastel,
                        )
                        st.plotly_chart(fig, use_container_width=True)

                        st.subheader("🔬 Micronutrient Analysis")
                        st.table({
                            "Iron (mg)": round(t[4], 2),
                            "Calcium (mg)": round(t[5], 1),
                            "Vitamin C (mg)": round(t[6], 1),
                            "Potassium (mg)": round(t[7], 1),
                            "Sodium (mg)": round(t[8], 1),
                        })
                        st.info(
                            f"💡 **AI Health Insight:** {data['health_insight']}"
                        )
            except Exception as e:
                st.error(f"Error: {str(e)}")
