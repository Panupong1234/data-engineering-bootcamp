# แผนการปรับ dbt project (greenery) ให้ใช้กับ SQL Server ภายในองค์กร

สถานะปัจจุบัน: โปรเจกต์นี้รันบน BigQuery adapter (`dbt-bigquery`) เป้าหมาย: ย้าย/รองรับให้รันกับ SQL Server on-prem ได้ด้วย

## 1. ติดตั้ง adapter ใหม่

```bash
pip install dbt-sqlserver   # หรือ dbt-fabric ถ้าเป็น Microsoft Fabric / Synapse
```

## 2. เพิ่ม target ใหม่ใน `profiles.yml`

ไฟล์นี้อยู่นอก repo (`~/.dbt/profiles.yml`) ไม่ใช่ `dbt_project.yml` — เพิ่ม target ใหม่โดยไม่ต้องลบ target BigQuery เดิม จะได้สลับไปมาได้ด้วย `--target`:

```yaml
greenery:
  target: dev
  outputs:
    dev:                          # target เดิม (BigQuery)
      type: bigquery
      ...

    sqlserver_dev:                # target ใหม่
      type: sqlserver
      driver: 'ODBC Driver 18 for SQL Server'
      server: your-sqlserver-host.company.local
      port: 1433
      database: YourDatabase
      schema: dbo
      authentication: sql         # หรือ ActiveDirectoryIntegrated / ActiveDirectoryPassword
      user: your_user
      password: "{{ env_var('DBT_PASSWORD') }}"
      trust_cert: true            # กรณีใช้ self-signed cert ภายในองค์กร
```

รันทดสอบด้วย `dbt debug --target sqlserver_dev` ก่อนใช้งานจริง

## 3. สิ่งที่ใช้ต่อได้เลย ไม่ต้องแก้

- โครงสร้าง `models/*.sql`
- `_models.yml`, `_src.yml`
- generic tests ทั้งหมดที่ผูกกับคอลัมน์ผ่าน `data_tests:` — `not_null`, `unique`, `accepted_values`, `relationships` เป็น macro มาตรฐานของ dbt-core ทำงานข้าม adapter ได้อัตโนมัติ

## 4. สิ่งที่ต้องแก้ไข — singular tests ที่ใช้ syntax เฉพาะ BigQuery

| ไฟล์ | ปัญหา | ทางแก้สำหรับ SQL Server |
|---|---|---|
| `tests/assert_email_format_is_valid.sql` | ใช้ `regexp_contains(email, r'...')` | T-SQL ไม่มี regex เนทีฟ — ใช้ `LIKE` pattern แทน เช่น `email NOT LIKE '%_@_%.__%'` (ตรวจแบบหยาบกว่า) หรือใช้ CLR function ถ้าต้องการความแม่นยำระดับ regex |
| `tests/assert_phone_number_format_is_valid.sql` | ใช้ `regexp_contains(phone_number, r'^[0-9]{3}-[0-9]{3}-[0-9]{4}$')` | ใช้ `LIKE` กับ character class: `phone_number NOT LIKE '[0-9][0-9][0-9]-[0-9][0-9][0-9]-[0-9][0-9][0-9][0-9]'` (ต้องเขียน `[0-9]` ซ้ำเองเพราะ `LIKE` ไม่รองรับ `{n}`) |
| `tests/assert_timestamps_are_not_in_future.sql` | ใช้ `current_timestamp()` แบบ BigQuery function call | เปลี่ยนเป็น `GETDATE()` หรือ `SYSDATETIME()` หรือใช้ dbt cross-db macro `{{ dbt.current_timestamp() }}` เพื่อให้รันได้ทั้งสอง adapter โดยไม่ต้องมีไฟล์แยก |
| `tests/assert_updated_at_is_not_before_created_at.sql` | ไม่มีฟังก์ชันเฉพาะ BigQuery | ใช้ได้กับทั้งสอง adapter โดยไม่ต้องแก้ |

**แนวทางแนะนำ:** แก้ให้ใช้ dbt cross-database macro (`{{ dbt.current_timestamp() }}`) แทนการ hardcode ฟังก์ชันเฉพาะ adapter ในไฟล์ที่ยังพอทำได้ (เช่นไฟล์ timestamp) ส่วนไฟล์ regex (email/phone) อาจต้องแยกเป็นคนละ query ตาม adapter โดยใช้ `{% if target.type == 'bigquery' %} ... {% else %} ... {% endif %}` ภายในไฟล์เดียวกัน

## 5. ถ้าจะใช้ `dbt_expectations` เพิ่มเติม (ตามที่เริ่มใส่ใน `_models.yml`)

เพิ่ม `packages.yml`:
```yaml
packages:
  - package: calogica/dbt_expectations
    version: [">=0.10.0", "<0.11.0"]
```
แล้วรัน `dbt deps`

ข้อควรระวัง: macro ส่วนใหญ่ของ `dbt_expectations` dispatch ผ่าน adapter ได้ แต่บาง macro (โดยเฉพาะที่พึ่ง regex หรือ statistical function) อาจยังไม่รองรับ `sqlserver` adapter ครบ — ต้องรัน `dbt test --target sqlserver_dev` แล้วไล่ดู error ทีละตัวว่าอันไหน "not implemented for this adapter"

## 6. ขั้นตอนการทดสอบก่อนใช้งานจริง

1. `dbt debug --target sqlserver_dev` — เช็ค connection
2. `dbt run --target sqlserver_dev` — รัน models ทั้งหมด สร้างตารางบน SQL Server
3. `dbt test --target sqlserver_dev` — รัน generic tests ก่อน (ควรผ่านทันทีเพราะ adapter-agnostic)
4. แก้ singular tests ตามตารางข้อ 4 ทีละไฟล์ แล้วรันซ้ำเฉพาะไฟล์นั้นด้วย `dbt test --select assert_email_format_is_valid --target sqlserver_dev`
5. เทียบผลลัพธ์ pass/fail กับที่รันบน BigQuery ว่าตรงกัน (จำนวนแถวที่ fail ควรเท่ากันถ้าข้อมูลเหมือนกัน)

## 7. เรื่องอื่นที่ต้องพิจารณาเพิ่ม (นอกเหนือ tests)

- **Data type mapping**: BigQuery `TIMESTAMP` vs SQL Server `DATETIME2` — ตรวจสอบ precision/timezone handling ให้ตรงกัน
- **Materialization**: `dbt_project.yml` ตั้ง `+materialized: view` ไว้ — ตรวจสอบว่า SQL Server รองรับ view แบบเดียวกัน (ปกติรองรับ แต่ performance อาจต่างกัน ถ้าข้อมูลใหญ่ควรพิจารณาเปลี่ยนเป็น `table` หรือ `incremental`)
- **Case sensitivity**: SQL Server มักตั้งค่า collation แบบ case-insensitive โดย default ต่างจาก BigQuery ที่ case-sensitive — อาจกระทบผลของ test `unique`/`accepted_values` ถ้าข้อมูลมีตัวพิมพ์ใหญ่เล็กปนกัน
- **Credentials**: อย่า commit password ลง `profiles.yml` ตรงๆ — ใช้ `env_var()` ตามตัวอย่างข้างบน และตั้งค่า `DBT_PASSWORD` ผ่าน environment variable หรือ secret manager ขององค์กร
