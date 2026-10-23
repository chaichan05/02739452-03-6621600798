# Thailand Earthquake Data Pipeline

โครงงานรายวิชา Big Data: รวบรวมเหตุการณ์แผ่นดินไหวจาก 3 แหล่ง เข้าสู่ PostgreSQL ด้วย Apache Airflow และแสดงผลด้วย Streamlit

**ผู้จัดทำ:** 6621600798 ชัยชาญ กลิ่นประเสริฐ · หมู่ 700

## สิ่งที่ทำได้ตามเกณฑ์

- ระดับ 1: ETL DAG, PostgreSQL, ตารางข้อมูล และกราฟ
- ระดับ 2: TMD + USGS + GEOFON รันขนานใน 3 TaskGroups, schema กลาง, UPSERT, KPI และตัวกรอง
- ระดับ 3: source isolation (แหล่งหนึ่งล่มอีกสองแหล่งยังทำต่อ), fuzzy dedup ข้ามแหล่ง, validation และ quality branch
- โบนัส: หน้า `สถานะ Pipeline` บน dashboard
- Web scraping: TMD HTML ด้วย Requests + BeautifulSoup เท่านั้น ไม่มี Selenium; ตรวจ `robots.txt` ก่อนทุกครั้ง จำกัด 5 หน้าและหน่วง 1 วินาทีระหว่าง request
- ไม่มีข้อมูลส่วนบุคคล ข้อมูลทั้งหมดเป็นข้อมูลเหตุการณ์สาธารณะ

## สถาปัตยกรรม

```text
TMD HTML ── extract ── transform ─┐
USGS API ─ extract ── transform ──┼─ validate ─ deduplicate ─ quality branch ─ UPSERT ─ PostgreSQL
GEOFON ─── extract ── transform ──┘                                      │
                                                                         └─ quarantine
                                                                                 │
PostgreSQL ─────────────────────────────────────────────────────────────── Streamlit
```

## เริ่มระบบ

1. คัดลอก `.env.example` เป็น `.env` (ค่าเริ่มต้นรันได้ทันที)
2. สั่ง:

```powershell
docker compose up -d --build
```

3. เปิด Airflow: <http://localhost:8080> ด้วยค่าจาก `AIRFLOW_ADMIN_USER` และ `AIRFLOW_ADMIN_PASSWORD` ใน `.env`
4. Trigger DAG `thailand_earthquake_etl` และรอให้เสร็จ
5. เปิด dashboard: <http://localhost:8501>

รอบแรกจะดาวน์โหลด image และใช้เวลาหลายนาที ข้อมูลถูกจำกัดช่วง 1 มกราคม 2564 ถึง 31 ธันวาคม 2569 และเก็บเฉพาะพิกัดที่ผ่าน point-in-polygon ภายในขอบเขตจังหวัดของประเทศไทย

## ตรวจสอบ

```powershell
docker compose config
docker compose run --rm airflow-scheduler pytest -q /opt/airflow/tests
docker compose exec airflow-scheduler python /opt/airflow/scripts/verify_scope.py
docker compose exec postgres psql -U earthquake -d earthquake -c "select count(*) from earthquake_events;"
```

ทดสอบ idempotency: Trigger DAG ซ้ำ แล้วตรวจ `count(*)` ซึ่งต้องไม่เพิ่มสำหรับเหตุการณ์เดิม เพราะ `event_uid` เป็น primary key และใช้ `ON CONFLICT DO UPDATE`

ทดสอบ source isolation: ปรับ URL ของ extractor หนึ่งแหล่งให้ผิดชั่วคราว แล้ว Trigger DAG; run จะเป็น `degraded` แต่ข้อมูลจากแหล่งที่เหลือยังผ่านขั้น merge/load ได้เมื่อเกณฑ์คุณภาพรวมผ่าน

## Schema กลาง

`event_uid, occurred_at, province, latitude, longitude, depth_km, magnitude, magnitude_type, place, is_in_thailand, sources[], source_ids(jsonb), quality_score`

การตัดสินว่าอยู่ในประเทศไทยไม่ใช้ข้อความสถานที่และไม่ใช้เพียง bounding box แต่ตรวจพิกัดกับ polygon ระดับจังหวัด (ADM1) จาก geoBoundaries แล้วใช้ polygon ที่ครอบจุดเป็นค่าจังหวัด ข้อมูลขอบเขตใช้สัญญาอนุญาต CC BY 4.0 และ cache ไว้ใน `data/thailand_adm1.geojson`

รายการซ้ำคือเหตุการณ์ที่เวลาห่างไม่เกิน 90 วินาทีและศูนย์กลางห่างไม่เกิน 25 กม. เลือกข้อมูลหลักตามลำดับ TMD > USGS > GEOFON แต่เก็บชื่อแหล่งและรหัสต้นทางทั้งหมดไว้

## หมายเหตุด้านจริยธรรม

- TMD ไม่มีข้อห้ามใน `robots.txt` ณ วันที่ตรวจ และหน้าเป้าหมายมี meta `robots=index,follow`; scraper ยังตรวจสิทธิ์ด้วย `RobotFileParser` ทุกครั้ง
- User-Agent ระบุว่าเป็นโครงงานวิชาการ, จำกัด 5 หน้า (สูงสุด 1,000 รายการ) และหน่วง 1 วินาทีระหว่างหน้า
- ไม่เก็บชื่อบุคคล อีเมล IP หรือข้อมูลที่เข้าข่าย PDPA
- เวลาในฐานข้อมูลเป็น UTC; dashboard แสดงป้ายกำกับชัดเจน

## แหล่งข้อมูล

- [กรมอุตุนิยมวิทยา](https://earthquake.tmd.go.th/inside.html)
- [USGS FDSN Event API](https://earthquake.usgs.gov/fdsnws/event/1/)
- [GEOFON FDSN Event API](https://geofon.gfz.de/fdsnws/event/1/)
- [geoBoundaries ADM1 API](https://www.geoboundaries.org/api/current/gbOpen/THA/ADM1/) — ขอบเขตจังหวัด, CC BY 4.0

