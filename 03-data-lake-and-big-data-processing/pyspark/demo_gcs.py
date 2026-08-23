from pyspark.sql import SparkSession


KEYFILE_PATH = "/opt/spark/pyspark/cert/deb-uploading-files-to-gcs.json"
OUTPUT_PATH = "gs://deb_07/output/hello"

spark = SparkSession.builder.appName("demo_gcs") \
    .config("spark.jars", "/opt/spark/jars/gcs-connector-hadoop3-latest.jar") \
    .config("spark.memory.offHeap.enabled", "true") \
    .config("spark.memory.offHeap.size", "5g") \
    .config("fs.gs.impl", "com.google.cloud.hadoop.fs.gcs.GoogleHadoopFileSystem") \
    .config("google.cloud.auth.service.account.enable", "true") \
    .config("google.cloud.auth.service.account.json.keyfile", KEYFILE_PATH) \
    .getOrCreate()

data = [
    ("James", "", "Smith", "1991-04-01", "M", 3000),
    ("Michael", "Rose", "", "2000-05-19", "M", 4000),
    ("Maria", "Anne", "Jones", "1967-12-01", "F", 4000),
    ("Jen", "Mary", "Brown", "1980-02-17", "F", -1),
]
columns = ["firstname", "middlename", "lastname", "dob", "gender", "salary"]
df = spark.createDataFrame(data=data, schema=columns)
df.show()

df.createOrReplaceTempView("hello")

result = spark.sql("""
    select
        *

    from hello
""")

result.write.mode("overwrite").parquet(OUTPUT_PATH)