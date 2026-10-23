import os

import pandas as pd
import plotly.express as px
import psycopg2
import streamlit as st

st.set_page_config(page_title="Thailand Earthquake Observatory", page_icon="🌏", layout="wide")
st.markdown("""
<style>
  .stApp { background: #07131f; color: #e9f1f7; }
  [data-testid="stSidebar"] { background: #0c1e2d; }
  [data-testid="stMetric"] { background: linear-gradient(135deg,#102b3d,#12394a); border:1px solid #245a70; padding:18px; border-radius:14px; }
  [data-testid="stMetricValue"] { color:#ffb45c; }
  h1,h2,h3 { font-family: "Arial", sans-serif; letter-spacing:-.02em; }
  .eyebrow { color:#67d5c5; font-weight:700; letter-spacing:.14em; font-size:.8rem; }
  .subtitle { color:#9db2c3; max-width:850px; }
  .status-ok { color:#67d5c5; } .status-bad { color:#ff7a75; }
</style>
""", unsafe_allow_html=True)

DB_URL = os.environ["EARTHQUAKE_DB_URL"]


@st.cache_data(ttl=60)
def load_data():
    with psycopg2.connect(DB_URL) as conn:
        events = pd.read_sql_query("""
          SELECT event_uid, occurred_at, latitude, longitude, depth_km, magnitude,
                 magnitude_type, place, province, is_in_thailand, array_to_string(sources, ', ') AS sources,
                 quality_score, updated_at
          FROM earthquake_events ORDER BY occurred_at DESC
        """, conn)
        runs = pd.read_sql_query("""
          SELECT run_id, started_at, finished_at, status, extracted_count, valid_count,
                 rejected_count, duplicate_count, upserted_count, source_status, message
          FROM pipeline_runs ORDER BY started_at DESC LIMIT 30
        """, conn)
    return events, runs


st.markdown('<div class="eyebrow">BIG DATA PIPELINE · THAILAND</div>', unsafe_allow_html=True)
st.title("Thailand Earthquake Observatory")
st.markdown('<p class="subtitle">ข้อมูลแผ่นดินไหวจาก TMD, USGS และ GEOFON รวมเป็น schema เดียว ตรวจคุณภาพ ตัดรายการซ้ำ และอ่านจาก PostgreSQL โดยตรง</p>', unsafe_allow_html=True)

try:
    events, runs = load_data()
except Exception as exc:
    st.error(f"ยังเชื่อมต่อ PostgreSQL ไม่ได้: {exc}")
    st.info("เริ่มระบบด้วย `docker compose up -d --build` แล้ว Trigger DAG `thailand_earthquake_etl` ที่ Airflow")
    st.stop()

if events.empty:
    st.warning("ฐานข้อมูลยังไม่มีเหตุการณ์ กรุณา Trigger DAG ใน Airflow ก่อน")
    st.stop()

events["occurred_at"] = pd.to_datetime(events["occurred_at"], utc=True)
min_date, max_date = events["occurred_at"].dt.date.min(), events["occurred_at"].dt.date.max()

with st.sidebar:
    st.header("ตัวกรองข้อมูล")
    date_range = st.date_input("ช่วงวันที่", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    mag_bounds = (float(events["magnitude"].min()), float(events["magnitude"].max()))
    mag_range = st.slider("ขนาดแผ่นดินไหว", mag_bounds[0], mag_bounds[1], mag_bounds, 0.1)
    source_values = ["tmd", "usgs", "geofon"]
    selected_sources = st.multiselect("แหล่งข้อมูล", source_values, default=source_values)
    st.success("ทุกจุดผ่านการตรวจ point-in-polygon ภายในขอบเขตจังหวัดของประเทศไทย")
    st.caption("ผู้จัดทำ: 6621600798 ชัยชาญ กลิ่นประเสริฐ · หมู่ 700")

start_date, end_date = (date_range if len(date_range) == 2 else (date_range[0], date_range[0]))
mask = (
    events["occurred_at"].dt.date.between(start_date, end_date)
    & events["magnitude"].between(*mag_range)
    & events["sources"].fillna("").apply(lambda s: any(src in s for src in selected_sources))
)
filtered = events[mask].copy()

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("เหตุการณ์", f"{len(filtered):,}")
k2.metric("ขนาดต่ำสุด", f"{filtered['magnitude'].min():.1f}" if len(filtered) else "-")
k3.metric("ขนาดเฉลี่ย", f"{filtered['magnitude'].mean():.2f}" if len(filtered) else "-")
k4.metric("ขนาดสูงสุด", f"{filtered['magnitude'].max():.1f}" if len(filtered) else "-")
k5.metric("ความลึกเฉลี่ย", f"{filtered['depth_km'].mean():.1f} km" if len(filtered) else "-")

left, right = st.columns([1.35, 1])
with left:
    st.subheader("ตำแหน่งศูนย์กลาง")
    if len(filtered):
        fig = px.scatter_mapbox(
            filtered, lat="latitude", lon="longitude", size="magnitude", color="depth_km",
            hover_name="place", hover_data={"occurred_at": True, "sources": True, "latitude": ":.3f", "longitude": ":.3f"},
            color_continuous_scale=["#ffb45c", "#e65b5b", "#542c74"], zoom=4.1, height=500,
        )
        fig.update_layout(mapbox_style="carto-darkmatter", margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="#07131f")
        st.plotly_chart(fig, use_container_width=True)
with right:
    st.subheader("จำนวนเหตุการณ์รายปี")
    annual = filtered.assign(year=filtered["occurred_at"].dt.year).groupby("year").size().rename("events").reset_index()
    fig2 = px.bar(annual, x="year", y="events", height=235, color_discrete_sequence=["#67d5c5"], text_auto=True)
    fig2.update_layout(paper_bgcolor="#07131f", plot_bgcolor="#0c1e2d", xaxis_title="ปี ค.ศ.", yaxis_title="เหตุการณ์", margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig2, use_container_width=True)
    st.subheader("การกระจายขนาดแผ่นดินไหว")
    fig3 = px.histogram(filtered, x="magnitude", nbins=18, height=235, color_discrete_sequence=["#ffb45c"])
    fig3.update_layout(paper_bgcolor="#07131f", plot_bgcolor="#0c1e2d", xaxis_title="ขนาด", yaxis_title="จำนวน", margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig3, use_container_width=True)

tab1, tab2 = st.tabs(["ตารางเหตุการณ์", "สถานะ Pipeline"])
with tab1:
    st.dataframe(
        filtered[["occurred_at", "province", "magnitude", "depth_km", "latitude", "longitude", "place", "sources", "quality_score"]],
        use_container_width=True, hide_index=True,
        column_config={"occurred_at": "วันเวลา (UTC)", "province": "จังหวัด", "magnitude": "ขนาด", "depth_km": "ลึก (km)", "place": "บริเวณ", "sources": "แหล่ง"},
    )
with tab2:
    if runs.empty:
        st.info("ยังไม่มีประวัติการรัน")
    else:
        last = runs.iloc[0]
        cls = "status-ok" if last["status"] in ("success", "degraded") else "status-bad"
        st.markdown(f'<h3 class="{cls}">Latest run: {last["status"].upper()}</h3>', unsafe_allow_html=True)
        st.caption(str(last["message"] or ""))
        st.dataframe(runs.drop(columns=["source_status"]), use_container_width=True, hide_index=True)

