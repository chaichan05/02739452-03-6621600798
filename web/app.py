import os

import pandas as pd
import plotly.express as px
import psycopg2
import streamlit as st


st.set_page_config(
    page_title="ศูนย์ข้อมูลแผ่นดินไหวประเทศไทย",
    page_icon="🌏",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      :root { --ink:#172033; --muted:#64748b; --line:#dbe4ee; --teal:#087f8c; }
      .stApp { background:#f5f7fb; color:var(--ink); font-family:Tahoma,"Noto Sans Thai",Arial,sans-serif; }
      /* Keep the dashboard header compact; Streamlit's cloud controls are not needed here. */
      header[data-testid="stHeader"],
      [data-testid="stToolbar"],
      [data-testid="stDecoration"],
      .stDeployButton,
      #MainMenu { display:none !important; }
      [data-testid="stAppViewContainer"] { padding-top:0 !important; }
      .block-container { max-width:1480px; padding-top:1.15rem; padding-bottom:3rem; }
      [data-testid="stSidebar"] { background:#fff; border-right:1px solid var(--line); }
      h1,h2,h3 { color:var(--ink); letter-spacing:-.02em; }
      h1 { font-size:clamp(1.8rem,3vw,2.65rem)!important; line-height:1.18!important; margin:.1rem 0 .35rem!important; padding:0!important; }
      h2 { font-size:1.45rem!important; margin-top:.6rem!important; }
      .eyebrow,.section-kicker { color:var(--teal); font-weight:800; letter-spacing:.12em; font-size:.76rem; }
      .eyebrow { margin:0 0 .15rem; }
      .subtitle { color:var(--muted); max-width:920px; font-size:1.03rem; line-height:1.75; }
      .section-note { color:var(--muted); font-size:.9rem; margin-top:-.6rem; margin-bottom:.7rem; }
      .scope-note { padding:.8rem 1rem; background:#e9f8f6; color:#12635f; border:1px solid #b9e7e0; border-radius:12px; font-size:.88rem; line-height:1.55; }
      .result-line { display:inline-flex; margin:.45rem 0 1.1rem; padding:.48rem .8rem; background:#eef6ff; color:#315a7d; border:1px solid #d4e7f8; border-radius:999px; font-size:.86rem; font-weight:700; }
      [data-testid="stMetric"] { background:#fff; border:1px solid var(--line); border-radius:16px; padding:1rem 1.1rem; min-height:116px; box-shadow:0 5px 18px rgba(23,32,51,.045); }
      [data-testid="stMetricLabel"] { color:var(--muted); font-weight:700; }
      [data-testid="stMetricValue"] { color:var(--ink); font-size:1.75rem; font-weight:800; }
      [data-testid="stPlotlyChart"],[data-testid="stDataFrame"] { background:#fff; border:1px solid var(--line); border-radius:16px; padding:.45rem; overflow:hidden; box-shadow:0 5px 18px rgba(23,32,51,.04); }
      button[data-baseweb="tab"] { font-weight:700; font-size:.96rem; }
      .stAlert { border-radius:12px; }
      @media(max-width:900px){ .block-container{padding-top:.8rem} h1{font-size:1.85rem!important} [data-testid="stMetric"]{min-height:100px} }
    </style>
    """,
    unsafe_allow_html=True,
)

DB_URL = os.environ["EARTHQUAKE_DB_URL"]
SOURCE_LABELS = {"tmd": "กรมอุตุนิยมวิทยา (TMD)", "usgs": "USGS", "geofon": "GEOFON"}


@st.cache_data(ttl=60)
def load_data():
    with psycopg2.connect(DB_URL) as conn:
        events = pd.read_sql_query(
            """SELECT event_uid, occurred_at, latitude, longitude, depth_km, magnitude,
                      magnitude_type, place, province, is_in_thailand,
                      array_to_string(sources, ', ') AS sources, quality_score, updated_at
               FROM earthquake_events ORDER BY occurred_at DESC""",
            conn,
        )
        runs = pd.read_sql_query(
            """SELECT run_id, started_at, finished_at, status, extracted_count, valid_count,
                      rejected_count, duplicate_count, upserted_count, source_status, message
               FROM pipeline_runs ORDER BY started_at DESC LIMIT 30""",
            conn,
        )
    return events, runs


def section(kicker, title, note):
    st.markdown(f'<div class="section-kicker">{kicker}</div>', unsafe_allow_html=True)
    st.subheader(title)
    st.markdown(f'<div class="section-note">{note}</div>', unsafe_allow_html=True)


def chart_style(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#fff",
        font=dict(family="Tahoma, Arial, sans-serif", color="#334155", size=12),
        margin=dict(l=15, r=15, t=20, b=10),
        hoverlabel=dict(bgcolor="#172033", font_color="white", font_size=13),
    )
    fig.update_yaxes(gridcolor="#e8eef4", rangemode="tozero")
    return fig


st.markdown('<div class="eyebrow">BIG DATA PIPELINE · THAILAND</div>', unsafe_allow_html=True)
st.title("ศูนย์ข้อมูลแผ่นดินไหวประเทศไทย")
st.markdown(
    '<p class="subtitle">สำรวจเหตุการณ์แผ่นดินไหวที่มีจุดศูนย์กลางอยู่ภายในประเทศไทย '
    'จากกรมอุตุนิยมวิทยา USGS และ GEOFON ข้อมูลผ่านการตรวจพิกัดด้วยขอบเขตจังหวัดจริง '
    'รวมเป็นมาตรฐานเดียว และอ่านจาก PostgreSQL โดยตรง</p>', unsafe_allow_html=True,
)

try:
    events, runs = load_data()
except Exception as exc:
    st.error(f"ยังเชื่อมต่อ PostgreSQL ไม่ได้: {exc}")
    st.info("เริ่มระบบด้วย docker compose แล้ว Trigger DAG thailand_earthquake_etl ใน Airflow")
    st.stop()

if events.empty:
    st.warning("ฐานข้อมูลยังไม่มีเหตุการณ์ กรุณา Trigger DAG ใน Airflow ก่อน")
    st.stop()

events["occurred_at"] = pd.to_datetime(events["occurred_at"], utc=True)
min_date, max_date = events["occurred_at"].dt.date.min(), events["occurred_at"].dt.date.max()
mag_bounds = (float(events["magnitude"].min()), float(events["magnitude"].max()))

with st.sidebar:
    st.subheader("ตัวกรองข้อมูล")
    st.caption("ตัวกรองจะปรับตัวเลข กราฟ และตารางพร้อมกัน")
    date_range = st.date_input("ช่วงวันที่เกิดเหตุ", (min_date, max_date), min_date, max_date, format="DD/MM/YYYY")
    mag_range = st.slider("ขนาดแผ่นดินไหว", mag_bounds[0], mag_bounds[1], mag_bounds, 0.1)
    selected_sources = st.multiselect(
        "แหล่งข้อมูล", list(SOURCE_LABELS), list(SOURCE_LABELS),
        format_func=lambda source: SOURCE_LABELS[source],
    )
    st.divider()
    st.markdown(
        '<div class="scope-note"><b>ขอบเขตที่ตรวจแล้ว</b><br>ทุกจุดผ่านการตรวจ point-in-polygon '
        'ภายในขอบเขตจังหวัดของประเทศไทย</div>', unsafe_allow_html=True,
    )
    st.caption("ผู้จัดทำ: 6621600798 ชัยชาญ กลิ่นประเสริฐ · หมู่ 700")

start_date, end_date = date_range if len(date_range) == 2 else (date_range[0], date_range[0])
source_mask = events["sources"].fillna("").apply(
    lambda value: any(source in value.lower() for source in selected_sources)
)
filtered = events.loc[
    events["occurred_at"].dt.date.between(start_date, end_date)
    & events["magnitude"].between(*mag_range)
    & source_mask
].copy()

st.markdown(
    f'<div class="result-line">● พบ {len(filtered):,} เหตุการณ์ จากทั้งหมด {len(events):,} เหตุการณ์</div>',
    unsafe_allow_html=True,
)
section("OVERVIEW", "ภาพรวมเหตุการณ์", "ค่าสถิติคำนวณจากข้อมูลที่เลือกในตัวกรอง")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("จำนวนเหตุการณ์", f"{len(filtered):,}")
k2.metric("ขนาดต่ำสุด", f"{filtered['magnitude'].min():.1f}" if len(filtered) else "–")
k3.metric("ขนาดเฉลี่ย", f"{filtered['magnitude'].mean():.2f}" if len(filtered) else "–")
k4.metric("ขนาดสูงสุด", f"{filtered['magnitude'].max():.1f}" if len(filtered) else "–")
k5.metric("ความลึกเฉลี่ย", f"{filtered['depth_km'].mean():.1f} km" if len(filtered) else "–")

if filtered.empty:
    st.warning("ไม่พบข้อมูลตามเงื่อนไขนี้ ลองขยายช่วงวันที่ ขนาด หรือเลือกแหล่งข้อมูลเพิ่ม")
    st.stop()

st.write("")
section("LOCATION & TREND", "ตำแหน่งและแนวโน้ม", "ขนาดวงกลมแทนขนาดแผ่นดินไหว สีแทนความลึก")
map_col, trend_col = st.columns([1.45, 1], gap="large")
with map_col:
    st.markdown("#### แผนที่จุดศูนย์กลาง")
    map_fig = px.scatter_mapbox(
        filtered, lat="latitude", lon="longitude", size="magnitude", size_max=18,
        color="depth_km", hover_name="province",
        hover_data={"place": True, "magnitude": ":.1f", "depth_km": ":.1f", "occurred_at": True,
                    "sources": True, "latitude": ":.3f", "longitude": ":.3f"},
        labels={"place": "บริเวณ", "magnitude": "ขนาด", "depth_km": "ความลึก (กม.)",
                "occurred_at": "วันเวลา UTC", "sources": "แหล่งข้อมูล",
                "latitude": "ละติจูด", "longitude": "ลองจิจูด"},
        color_continuous_scale=["#f6bd60", "#e87924", "#b23a48"],
        zoom=4.25, center={"lat": 13.2, "lon": 101.0}, height=560,
    )
    map_fig.update_layout(
        # OpenStreetMap works without a Mapbox/CARTO API key, so the repo runs as-is.
        mapbox_style="open-street-map", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0), coloraxis_colorbar=dict(title="ลึก<br>(กม.)", thickness=12),
    )
    st.plotly_chart(
        map_fig,
        use_container_width=True,
        config={
            "scrollZoom": True,
            "displayModeBar": True,
            "displaylogo": False,
            "doubleClick": "reset",
            "responsive": True,
            "modeBarButtonsToRemove": ["select2d", "lasso2d"],
        },
    )
    st.caption("ซูมด้วยล้อเมาส์หรือทัชแพด · ลากเพื่อเลื่อนแผนที่ · ดับเบิลคลิกเพื่อกลับมุมมองเริ่มต้น")

with trend_col:
    st.markdown("#### จำนวนเหตุการณ์รายปี")
    annual = filtered.assign(year=filtered["occurred_at"].dt.year).groupby("year").size().rename("events").reset_index()
    annual_fig = px.bar(
        annual, x="year", y="events", text_auto=True, height=260,
        color_discrete_sequence=["#087f8c"], labels={"year": "ปี ค.ศ.", "events": "จำนวนเหตุการณ์"},
    )
    chart_style(annual_fig).update_layout(bargap=.35)
    annual_fig.update_xaxes(dtick=1, showgrid=False)
    st.plotly_chart(annual_fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("#### การกระจายของขนาด")
    magnitude_fig = px.histogram(
        filtered, x="magnitude", nbins=16, height=260, color_discrete_sequence=["#e87924"],
        labels={"magnitude": "ขนาดแผ่นดินไหว", "count": "จำนวนเหตุการณ์"},
    )
    chart_style(magnitude_fig).update_layout(bargap=.08)
    magnitude_fig.update_yaxes(title="จำนวนเหตุการณ์")
    st.plotly_chart(magnitude_fig, use_container_width=True, config={"displayModeBar": False})

st.write("")
section("DETAIL", "รายละเอียดข้อมูล", "เรียงเหตุการณ์ล่าสุดก่อน และจัดเรียงข้อมูลได้จากหัวตาราง")
event_tab, pipeline_tab = st.tabs(["รายการเหตุการณ์", "สถานะ Pipeline"])

with event_tab:
    display = filtered[["occurred_at", "province", "magnitude", "depth_km", "latitude", "longitude",
                        "place", "sources", "quality_score"]].copy()
    display["occurred_at"] = display["occurred_at"].dt.strftime("%d/%m/%Y %H:%M")
    st.dataframe(
        display, use_container_width=True, hide_index=True, height=470,
        column_config={
            "occurred_at": st.column_config.TextColumn("วันเวลา (UTC)", width="medium"),
            "province": st.column_config.TextColumn("จังหวัด", width="medium"),
            "magnitude": st.column_config.NumberColumn("ขนาด", format="%.1f"),
            "depth_km": st.column_config.NumberColumn("ลึก (กม.)", format="%.1f"),
            "latitude": st.column_config.NumberColumn("ละติจูด", format="%.3f"),
            "longitude": st.column_config.NumberColumn("ลองจิจูด", format="%.3f"),
            "place": st.column_config.TextColumn("บริเวณ", width="large"),
            "sources": st.column_config.TextColumn("แหล่งข้อมูล"),
            "quality_score": st.column_config.ProgressColumn("คุณภาพข้อมูล", min_value=0.0, max_value=1.0, format="%.2f"),
        },
    )
    st.caption(f"แสดง {len(display):,} รายการ · เวลาในตารางเป็น UTC")

with pipeline_tab:
    if runs.empty:
        st.info("ยังไม่มีประวัติการรัน Pipeline")
    else:
        latest = runs.iloc[0]
        status = str(latest["status"]).lower()
        status_text = {"success": "สำเร็จ", "degraded": "สำเร็จบางส่วน", "failed": "ไม่สำเร็จ"}.get(status, status)
        (st.success if status in ("success", "degraded") else st.error)(f"การรันล่าสุด: {status_text}")
        if latest["message"]:
            st.caption(str(latest["message"]))
        run_display = runs.drop(columns=["source_status"]).rename(columns={
            "run_id": "Run ID", "started_at": "เริ่มรัน", "finished_at": "สิ้นสุด", "status": "สถานะ",
            "extracted_count": "ดึงมา", "valid_count": "ผ่านตรวจ", "rejected_count": "ไม่ผ่าน",
            "duplicate_count": "ข้อมูลซ้ำ", "upserted_count": "บันทึก", "message": "รายละเอียด",
        })
        st.dataframe(run_display, use_container_width=True, hide_index=True, height=420)
