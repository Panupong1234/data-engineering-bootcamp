import json
import os
import pandas as pd
import streamlit as st
from google import genai
from google.genai import types
from google.cloud import bigquery
from google.oauth2 import service_account

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Course Recommender Pro",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    header {visibility: hidden;}
    .block-container { padding-top: 1.5rem; }

    .hero-banner {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .hero-banner h1 { color: #ffffff !important; margin: 0; font-size: 2.2rem; }
    .hero-banner p { color: #d0e1fd; margin-top: 5px; font-size: 1rem; }

    .course-card {
        background-color: #ffffff;
        border-left: 5px solid #2a5298;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        color: #1f2937;
    }
    
    @media (prefers-color-scheme: dark) {
        .course-card {
            background-color: #1e293b;
            color: #f8fafc;
            border-left: 5px solid #60a5fa;
        }
    }

    .match-badge {
        background-color: #dbeafe;
        color: #1e40af;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.8rem;
        margin-bottom: 6px;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. CONFIG & CONSTANTS
# -----------------------------------------------------------------------------
GCP_PROJECT_ID = "project-3826e055-85ee-4d4f-a24"
DATASET_ID = "deb_bootcamp"
TABLE_ID = "courses"
KEYFILE = "../../00-bootcamp-project/cert/deb-dbt.json"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# -----------------------------------------------------------------------------
# 3. HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def get_embedding(client, model: str = "gemini-embedding-2", text: str = ""):
    result = client.models.embed_content(
        model=model,
        contents=text,
    )
    return result.embeddings[0]


def ask_gemini(client, model: str = "gemini-3.6-flash", prompt: str = ""):
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=[
                "You are an expert course recommender.",
                "Your mission is to recommend courses for people who want to upskill and switch careers based on the context provided.",
                "Respond in well-structured, friendly, and clear Thai markdown with actionable recommendations."
            ]
        ),
    )
    return response.text


def search_similar_texts(client, vec, top_k=3):
    query = f"""
        SELECT
            base.text,
            distance
        FROM
        VECTOR_SEARCH(
            TABLE `{DATASET_ID}.{TABLE_ID}`,
            'embedding',
            (select {vec} as embedding),
            top_k => {top_k},
            distance_type => 'EUCLIDEAN'
        )
    """
    query_job = client.query(query)
    results = query_job.result()

    similar_texts = []
    for row in results:
        # ตัดชื่อคอร์สสั้นๆ เอาไว้อ่านง่ายในกราฟ
        course_name = row.text.split(" - ")[0] if " - " in row.text else row.text[:25] + "..."
        similar_texts.append({
            "text": row.text,
            "course_name": course_name,
            "distance": round(row.distance, 4)
        })

    return similar_texts

# -----------------------------------------------------------------------------
# 4. MAIN APPLICATION
# -----------------------------------------------------------------------------
def main():
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/graduation-cap.png", width=60)
        st.title("⚙️ Model Settings")
        
        st.subheader("🤖 เลือก AI Model")
        selected_genai_model = st.selectbox(
            "Gemini Generative Model:",
            [
                "gemini-3.6-flash",
                "gemini-3.1-flash-lite",
                "gemini-3.5-pro"
            ],
            index=0
        )

        selected_embed_model = st.selectbox(
            "Embedding Model:",
            [
                "gemini-embedding-2",
                "text-embedding-004"
            ],
            index=0
        )

        st.divider()
        st.subheader("🎯 Search Config")
        top_k = st.slider("จำนวนคอร์สที่ต้องการค้นหา (Top-K):", min_value=1, max_value=5, value=3)

        st.divider()
        st.subheader("🔌 Connection Status")
        if GEMINI_API_KEY:
            st.success("API Key: Ready", icon="✅")
        else:
            st.error("API Key: Missing", icon="❌")

    st.markdown("""
    <div class="hero-banner">
        <h1>🎓 AI Course Recommender & Analytics</h1>
        <p>ระบบแนะนำคอร์สเรียนอัจฉริยะด้วย BigQuery Vector Search และ Google Gemini</p>
    </div>
    """, unsafe_allow_html=True)

    col_input, col_sample = st.columns([2.5, 1.5])
    
    with col_sample:
        preset_choice = st.selectbox(
            "💡 ตัวอย่างคำถามยอดนิยม:",
            [
                "-- เลือกคำถามตัวอย่าง --",
                "อยากทำสาย Data Engineer ควรเรียนคอร์สอะไรดี?",
                "อยากทำสาย Data Science ควรเรียนคอร์สอะไรดี?",
                "จบสายบริหารมา อยากเริ่มเรียน AI ควรเรียนอะไรดี?",
                "สนใจงานด้านการตลาดและเทคโนโลยี"
            ]
        )

    default_val = "" if preset_choice == "-- เลือกคำถามตัวอย่าง --" else preset_choice

    with col_input:
        user_question = st.text_input(
            "💬 พิมพ์คำถามหรือเป้าหมายอาชีพที่คุณสนใจ:",
            value=default_val,
            placeholder="เช่น อยากเริ่มต้นทำงานด้าน AI..."
        )

    if st.button("🚀 ค้นหาคำแนะนำคอร์สเรียน", type="primary", use_container_width=True):
        if not user_question.strip():
            st.warning("⚠️ กรุณาระบุคำถามก่อนค้นหาครับ")
            return
        
        if not GEMINI_API_KEY:
            st.error("🚨 ไม่พบ GEMINI_API_KEY ใน Environment Variables")
            return

        with st.spinner(f"🍳 กำลังวิเคราะห์ข้อมูลด้วย {selected_genai_model}..."):
            try:
                genai_client = genai.Client(api_key=GEMINI_API_KEY)
                service_account_info = json.load(open(KEYFILE))
                credentials = service_account.Credentials.from_service_account_info(service_account_info)
                bigquery_client = bigquery.Client(
                    project=GCP_PROJECT_ID,
                    credentials=credentials,
                )

                vec = get_embedding(genai_client, model=selected_embed_model, text=user_question).values
                similar_results = search_similar_texts(bigquery_client, vec, top_k=top_k)

                context = " / ".join([item["text"] for item in similar_results])
                prompt_with_context = f"""
                Context:
                {context}

                Question:
                {user_question}
                """
                response = ask_gemini(genai_client, model=selected_genai_model, prompt=prompt_with_context)

                st.divider()

                # --- ส่วนแสดงคำแนะนำจาก AI ---
                st.subheader("💡 คำแนะนำจาก AI Assistant")
                st.caption(f"ประมวลผลด้วยโมเดล: **{selected_genai_model}**")
                st.markdown(response)

                st.divider()

                # --- ส่วนแสดง Visual Chart & List ด้วย Streamlit Native Chart ---
                col_chart, col_cards = st.columns([1.2, 1])

                with col_chart:
                    st.subheader("📊 กราฟเปรียบเทียบความเกี่ยวข้อง (Vector Distance)")
                    st.caption("ยิ่งค่าน้อย (แท่งสั้น) หมายถึงเนื้อหาคอร์สยิ่งตรงกับคำถามมากที่สุด")
                    
                    # แปลงข้อมูลเตรียมไว้สำหรับ st.bar_chart
                    df_chart = pd.DataFrame(similar_results)
                    chart_data = df_chart.set_index("course_name")[["distance"]]
                    
                    # ใช้ st.bar_chart ในตัวของ Streamlit (แสดงผลแนวนอน)
                    st.bar_chart(chart_data, horizontal=True)

                with col_cards:
                    st.subheader("📌 คอร์สที่ดึงจาก BigQuery")
                    for idx, item in enumerate(similar_results, 1):
                        st.markdown(f"""
                        <div class="course-card">
                            <span class="match-badge">Match #{idx} (Distance: {item['distance']})</span>
                            <div style="font-size: 0.95rem;">{item['text']}</div>
                        </div>
                        """, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดในการประมวลผล: {e}")

if __name__ == "__main__":
    main()