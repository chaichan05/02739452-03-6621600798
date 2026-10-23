"""Create truthful visual evidence from PostgreSQL/Airflow metadata without a browser."""
import json
import os
from pathlib import Path

import psycopg2
from PIL import Image, ImageDraw, ImageFont

OUT = Path("/opt/airflow/output/screenshots")
DB = os.getenv("EARTHQUAKE_DB_URL")
BG, PANEL, GRID, WHITE, MUTED, TEAL, ORANGE, RED = "#07131f", "#102b3d", "#245a70", "#edf4f7", "#9db2c3", "#67d5c5", "#ffb45c", "#ff7a75"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def f(size, bold=False): return ImageFont.truetype(FONT_B if bold else FONT, size)


def rr(d, box, radius=18, fill=PANEL, outline=GRID, width=2):
    d.rounded_rectangle(box, radius, fill=fill, outline=outline, width=width)


def query():
    with psycopg2.connect(DB) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*),count(*) FILTER(WHERE is_in_thailand),max(magnitude),avg(depth_km) FROM earthquake_events")
        metrics = cur.fetchone()
        cur.execute("SELECT latitude,longitude,magnitude,depth_km FROM earthquake_events WHERE is_in_thailand")
        points = cur.fetchall()
        cur.execute("SELECT extract(year from occurred_at)::int,count(*) FROM earthquake_events GROUP BY 1 ORDER BY 1")
        years = cur.fetchall()
        cur.execute("SELECT run_id,status,source_status FROM pipeline_runs ORDER BY started_at DESC LIMIT 5")
        runs = cur.fetchall()
    return metrics, points, years, runs


def dashboard(metrics, points, years):
    im=Image.new("RGB",(1600,900),BG); d=ImageDraw.Draw(im)
    d.text((70,45),"THAILAND EARTHQUAKE OBSERVATORY",font=f(34,True),fill=WHITE)
    d.text((70,91),"Dashboard data preview · generated directly from PostgreSQL",font=f(18),fill=MUTED)
    labels=[("EVENTS",metrics[0]),("POLYGON VERIFIED",metrics[1]),("MAX MAG",f"{metrics[2]:.1f}"),("AVG DEPTH",f"{metrics[3]:.1f} km")]
    for i,(lab,val) in enumerate(labels):
        x=70+i*375; rr(d,(x,135,x+335,245)); d.text((x+24,158),lab,font=f(15,True),fill=TEAL); d.text((x+24,188),str(val),font=f(32,True),fill=ORANGE)
    rr(d,(70,280,960,825)); rr(d,(1000,280,1530,825))
    d.text((100,305),"Epicenters in Thailand bounding box",font=f(21,True),fill=WHITE)
    # geographic plot (lon 97.3..105.7, lat 5.5..20.6)
    x0,y0,x1,y1=105,350,925,780
    for lon in range(98,106,2):
        x=x0+(lon-97.3)/(105.7-97.3)*(x1-x0); d.line((x,y0,x,y1),fill=GRID)
    for lat in range(6,21,3):
        y=y1-(lat-5.5)/(20.6-5.5)*(y1-y0); d.line((x0,y,x1,y),fill=GRID)
    for lat,lon,mag,depth in points:
        x=x0+(lon-97.3)/(105.7-97.3)*(x1-x0); y=y1-(lat-5.5)/(20.6-5.5)*(y1-y0); r=max(2,min(10,int((mag or 1)*1.7)))
        d.ellipse((x-r,y-r,x+r,y+r),fill=ORANGE if (depth or 0)<20 else RED)
    d.text((1030,305),"Annual activity",font=f(21,True),fill=WHITE)
    recent=years or []; maxv=max([v for _,v in recent] or [1]); bw=420/max(len(recent),1)
    for i,(year,v) in enumerate(recent):
        h=380*v/maxv; x=1045+i*bw; d.rectangle((x,740-h,x+bw-3,740),fill=TEAL)
        d.text((x,755),str(year),font=f(11),fill=MUTED)
    d.text((1030,790),"Annual events · coordinates verified by ADM1 polygons",font=f(14),fill=MUTED)
    im.save(OUT/"dashboard.png")


def grid(runs):
    im=Image.new("RGB",(1600,900),BG); d=ImageDraw.Draw(im)
    d.text((70,45),"AIRFLOW RUN EVIDENCE",font=f(34,True),fill=WHITE)
    d.text((70,91),"Metadata snapshot from the latest pipeline runs",font=f(18),fill=MUTED)
    cols=["Run","TMD","USGS","GEOFON","Merge + DQ","Load","State"]
    widths=[430,150,150,150,210,150,190]; xs=[55]
    for w in widths: xs.append(xs[-1]+w)
    y=150
    for i,c in enumerate(cols):
        d.rectangle((xs[i],y,xs[i+1],y+60),fill=TEAL); d.text((xs[i]+12,y+18),c,font=f(16,True),fill=BG)
    for row,(run_id,status,source_status) in enumerate(runs):
        y=210+row*115; source_status=source_status if isinstance(source_status,dict) else json.loads(source_status)
        vals=[run_id.replace("manual__","").replace("scheduled__",""),
              "OK" if source_status.get("tmd",{}).get("ok") else "FAIL",
              "OK" if source_status.get("usgs",{}).get("ok") else "FAIL",
              "OK" if source_status.get("geofon",{}).get("ok") else "FAIL",
              "PASSED" if status in ("success","degraded") else "BLOCKED","UPSERTED" if status in ("success","degraded") else "SKIPPED",status.upper()]
        for i,val in enumerate(vals):
            fill=PANEL if row%2==0 else "#0c1e2d"; d.rectangle((xs[i],y,xs[i+1],y+100),fill=fill,outline=GRID,width=2)
            color=TEAL if val in ("OK","PASSED","UPSERTED","SUCCESS") else (RED if val in ("FAIL","BLOCKED") else WHITE)
            shown=str(val)[:34]; d.text((xs[i]+12,y+37),shown,font=f(14,i>0),fill=color)
    d.text((55,810),"This is a metadata-derived evidence panel, not a browser screenshot of Airflow Grid View.",font=f(15),fill=ORANGE)
    im.save(OUT/"airflow_grid.png")


if __name__ == "__main__":
    OUT.mkdir(parents=True,exist_ok=True)
    metrics,points,years,runs=query(); dashboard(metrics,points,years); grid(runs)
    print(OUT)

