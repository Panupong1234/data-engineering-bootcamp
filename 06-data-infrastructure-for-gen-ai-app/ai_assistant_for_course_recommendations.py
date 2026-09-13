import json
import os

import pandas as pd
from google import genai
from google.genai import types
from google.cloud import bigquery
from google.oauth2 import service_account


GCP_PROJECT_ID = "project-3826e055-85ee-4d4f-a24"
DATASET_ID = "deb_bootcamp"
TABLE_ID = "courses"
KEYFILE = "../00-bootcamp-project/cert/deb-dbt.json"
# api_key = os.environ.get("GEMINI_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")


def get_embedding(client, model: str = "gemini-embedding-2", text: str = ""):
    result = client.models.embed_content(
        model=model,
        contents=text,
    )
    return result.embeddings[0]


def ask_gemini(client, model: str = "gemini-3.1-flash-lite", prompt: str = ""):
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=[
                "You are a course recommender.",
                "Your mission is to recommend courses for people who want to upskill and switch careers."
            ]
        ),
    )
    return response.text


def load_data_to_bigquery(client, df):
    schema = [
        bigquery.SchemaField("text", "STRING"),
        bigquery.SchemaField("embedding", "FLOAT64", mode="REPEATED"),
    ]
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition="WRITE_TRUNCATE"
    )
    table_id = f"{GCP_PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    load_job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    load_job.result()

    print(f"Loaded {load_job.output_rows} rows into {table_id}")


def search_similar_texts(client, vec):
    query = f"""
        SELECT
            base.text,
            distance
        FROM
        VECTOR_SEARCH(
            TABLE `{DATASET_ID}.{TABLE_ID}`,
            'embedding',
            (select {vec} as embedding),
            top_k => 3,
            distance_type => 'EUCLIDEAN'
        )
    """

    # Run the query
    query_job = client.query(query)

    # Get the results
    results = query_job.result()

    # Print the results
    similar_texts = []
    for row in results:
        similar_texts.append(row.text)
        print(row.text)
        print(row.distance)

    return similar_texts


# Add more course data here
df = pd.DataFrame(data={
    "text": [
        "คอร์ส Probability for Data Science - ความน่าจะเป็นถูกนำมาใช้ในงาน Data Science ในงานด้านวิเคราะห์ข้อมูลและสร้างโมเดล เพื่อทำให้มั่นใจได้ว่าข้อมูลที่ได้มา มันมีความหมาย และมี Insight ถ้าคุณยังต้องนำข้อมูลไปทำโมเดลต่อ ไม่ว่าจะเป็นโมเดล Machine Learning หรือการทำนาย ล้วนก็มีงานใช้งานความน่าจะเป็นในการสร้างโมเดล ซึ่งคุณไม่มีทางจะหลีกเลี่ยงสิ่งนี้ได้ เพราะถ้าคุณไม่เข้าใจความน่าจะเป็นอย่างแท้จริง คุณอาจกำลังใช้โมเดล Machine Learning ที่จำลองสถานการณ์ผิดไปจากโจทย์ที่กำลังเผชิญอยู่ก็ได้! ข่าวดีคือ คุณไม่จำเป็นต้องเป็นอัจฉริยะด้านคณิตศาสตร์ก็สามารถเข้าใจความน่าจะเป็นได้!",
        "คอร์ส Data Pipelines with Airflow - คอร์สออนไลน์สำหรับ Data Engineer คอร์สแรกของไทยที่สอนการสร้าง End-to-End Data Pipelines ด้วย Airflow โดยเป็นคอร์สที่สอนการสร้าง Data Pipelines เพื่อจัดการข้อมูลขนาดใหญ่ (Big Data) แบบ Step by Step ตั้งแต่การอ่านข้อมูล ทำความสะอาด ปรับให้อยู่ในรูปแบบที่เหมาะสม สุดท้ายคือโหลดข้อมูลเข้า Data Lake/Data Warehouse แบบอัตโนมัติ เพื่อนำไปวิเคราะห์ข้อมูล และประกอบการตัดสินใจทางธุรกิจต่อไป",
        "คอร์ส Fundamentals of Data Analytics - เรียนรู้พื้นฐานการวิเคราะห์ข้อมูล",

        "คอร์ส Fundamentals of Artificial Intelligence - เรียนรู้พื้นฐานด้านปัญญาประดิษฐ์ หรือ AI",

        "คอร์ส n8n AI Automation Mastery - เรียนรู้การสร้างระบบงานอัตโนมัติด้วย AI และ n8n เพื่อใช้ในธุรกิจ",

        "คอร์ส How to Read Statistics as a PRO - เรียนรู้การตีความข้อมูลทางสถิติ กราฟ และตัวเลขอย่างถูกต้อง เพื่อช่วยในการตัดสินใจ",

        "คอร์ส Data Governance Essentials for Tourism - เรียนรู้การจัดการข้อมูลอย่างมีคุณภาพในธุรกิจท่องเที่ยว ครอบคลุม PDPA และการสร้างความเชื่อมั่นให้ลูกค้า",

        "คอร์ส AI Tools for Tourism: Customer Analytics - ใช้ AI วิเคราะห์พฤติกรรมนักท่องเที่ยว เพื่อเข้าใจลูกค้ามากขึ้น",

        "คอร์ส AI Tools for Tourism: Transforming Customer Experience - ใช้เครื่องมือ AI พัฒนาบริการท่องเที่ยวและสร้างประสบการณ์ที่ดีให้ลูกค้า",

        "คอร์ส Effective Storytelling with AI - ใช้ AI ช่วยพัฒนาทักษะการเล่าเรื่องให้ตอบโจทย์ผู้ฟัง",

        "คอร์ส Unlocking HR Value with AI - ใช้ AI เป็นผู้ช่วยงานทรัพยากรบุคคล ตั้งแต่การสรรหาจนถึงการรับพนักงานใหม่เข้าทำงาน",

        "คอร์ส Designing Your Own Testable Architecture - เรียนรู้การออกแบบสถาปัตยกรรมซอฟต์แวร์ที่พร้อมทดสอบได้ตั้งแต่เริ่มต้น",
    ]
})
print(df.head())

# Set up a Gemini client
genai_client = genai.Client(api_key=GEMINI_API_KEY)

# Set up a BigQuery client
service_account_info = json.load(open(KEYFILE))
credentials = service_account.Credentials.from_service_account_info(service_account_info)
bigquery_client = bigquery.Client(
    project=GCP_PROJECT_ID,
    credentials=credentials,
)

# Create the embeddings
df["embedding"] = df.text.map(lambda x: get_embedding(genai_client, text=x).values)
print(df.head())

# Store embeddings in BigQuery
load_data_to_bigquery(bigquery_client, df)

# Change your quesiton here
# question = "อยากทำสาย Data Engineer ควรเรียนคอร์สอะไรดี?"
question = "อยากทำสาย Data Science ควรเรียนคอร์สอะไรดี?"

vec = get_embedding(genai_client, text=question).values

similar_texts = search_similar_texts(bigquery_client, vec)

# Create context by gathering results together
context = " / ".join([each for each in similar_texts])

prompt_with_context = f"""
Context:
{context}

Question:
{question}
"""

response = ask_gemini(genai_client, prompt=prompt_with_context)
print(response)
