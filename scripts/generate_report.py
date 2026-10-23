"""Generate a concise 3-page PDF. Optional screenshots are loaded from output/screenshots/."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

OUT = Path("/opt/airflow/output/pdf")
SHOTS = Path("/opt/airflow/output/screenshots")
PDF = OUT / "earthquake_project_summary_6621600798.pdf"
PAGE = landscape(A4)
W, H = PAGE
NAVY, TEAL, ORANGE, PALE = colors.HexColor("#07131f"), colors.HexColor("#2ab7a9"), colors.HexColor("#f4a259"), colors.HexColor("#edf4f7")


def header(c, page, title):
    c.setFillColor(NAVY); c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(TEAL); c.rect(0, H - 8*mm, W, 8*mm, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 18); c.drawString(15*mm, H-20*mm, title)
    c.setFillColor(colors.HexColor("#9db2c3")); c.setFont("Helvetica", 8)
    c.drawRightString(W-15*mm, 9*mm, f"6621600798 · Chaiyachan Klinprasert · Section 700  |  {page}/3")


def p(c, text, x, y, width, size=9, color=colors.white, leading=12):
    style = ParagraphStyle("p", fontName="Helvetica", fontSize=size, leading=leading, textColor=color)
    para = Paragraph(text, style); _, h = para.wrap(width, 100*mm); para.drawOn(c, x, y-h); return y-h


def screenshot_or_placeholder(c, filename, label, x, y, w, h):
    path = SHOTS / filename
    c.setStrokeColor(colors.HexColor("#245a70")); c.roundRect(x, y, w, h, 4*mm, stroke=1, fill=0)
    if path.exists():
        c.drawImage(str(path), x+2*mm, y+2*mm, w-4*mm, h-4*mm, preserveAspectRatio=True, anchor="c")
    else:
        c.setFillColor(colors.HexColor("#102b3d")); c.roundRect(x+1*mm, y+1*mm, w-2*mm, h-2*mm, 3*mm, fill=1, stroke=0)
        c.setFillColor(ORANGE); c.setFont("Helvetica-Bold", 11); c.drawCentredString(x+w/2, y+h/2+2*mm, label)
        c.setFillColor(colors.HexColor("#9db2c3")); c.setFont("Helvetica", 7); c.drawCentredString(x+w/2, y+h/2-3*mm, "Live screenshot is regenerated after Docker startup")


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(PDF), pagesize=PAGE)
    c.setTitle("Thailand Earthquake Pipeline - 6621600798")
    c.setAuthor("Chaiyachan Klinprasert")
    header(c, 1, "Thailand Earthquake Pipeline · Project overview")
    y = H-30*mm
    y = p(c, "<b>Achievement: Level 3 + bonus.</b> Events from 2021-2026 are retained only when their coordinates fall inside a real Thailand ADM1 polygon; the matching polygon supplies the province. Three sources are normalized, deduplicated, quality-checked, and idempotently upserted. The dashboard reads PostgreSQL directly.", 15*mm, y, W-30*mm, 10, PALE, 14)
    gap=5*mm; boxw=(W-30*mm-2*gap)/3; boxh=73*mm; by=24*mm
    screenshot_or_placeholder(c,"airflow_graph.png","AIRFLOW · GRAPH VIEW",15*mm,by,boxw,boxh)
    screenshot_or_placeholder(c,"airflow_grid.png","AIRFLOW · GRID VIEW",15*mm+boxw+gap,by,boxw,boxh)
    screenshot_or_placeholder(c,"dashboard.png","STREAMLIT · DASHBOARD",15*mm+2*(boxw+gap),by,boxw,boxh)
    c.showPage()

    header(c, 2, "Problems found, diagnosis, and resolution")
    raw_data = [
        ["Problem / symptom", "How the cause was identified", "Resolution"],
        ["TMD has no machine API and the page mixes Thai local time with UTC.", "Inspected the real HTML: event rows have EQ IDs and a second timestamp explicitly marked UTC.", "Requests + BeautifulSoup only; parse UTC, honor robots.txt, limit to 5 pages with a 1-second delay, and detect schema drift when zero rows are found."],
        ["A place name or rectangular bounding box includes events outside Thailand.", "Plotted edge coordinates and found points in Myanmar, Laos, Malaysia, and the Gulf despite matching the rough box.", "Use point-in-polygon against geoBoundaries ADM1 geometry; keep only a matching polygon and use its name as the province."],
        ["A source outage could fail the entire scheduled DAG.", "Failure propagation from parallel extraction tasks would block the downstream merge.", "Catch source-level network errors into status records; merge always runs and labels the batch degraded. Quality still controls loading."],
        ["Repeated runs could inflate the database.", "A plain INSERT treats the same catalog event as new on every schedule.", "Stable event fingerprint + PostgreSQL primary key + ON CONFLICT DO UPDATE; source arrays and IDs are merged."],
    ]
    cell_style = ParagraphStyle("cell", fontName="Helvetica", fontSize=7.5, leading=9.5, textColor=PALE)
    head_style = ParagraphStyle("head", fontName="Helvetica-Bold", fontSize=8, leading=9.5, textColor=NAVY)
    data = [[Paragraph(str(value), head_style if row == 0 else cell_style) for value in values]
            for row, values in enumerate(raw_data)]
    table=Table(data, colWidths=[82*mm,92*mm,92*mm], rowHeights=[10*mm,30*mm,30*mm,30*mm,30*mm])
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),TEAL),("TEXTCOLOR",(0,0),(-1,0),NAVY),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTNAME",(0,1),(-1,-1),"Helvetica"),("FONTSIZE",(0,0),(-1,-1),8),("LEADING",(0,0),(-1,-1),10),("TEXTCOLOR",(0,1),(-1,-1),PALE),("GRID",(0,0),(-1,-1),.4,colors.HexColor("#245a70")),("VALIGN",(0,0),(-1,-1),"TOP"),("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#0c1e2d")),("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),("TOPPADDING",(0,0),(-1,-1),6)]))
    table.wrapOn(c,W,H); table.drawOn(c,15*mm,H-169*mm)
    c.showPage()

    header(c, 3, "Planning, prioritization, and scope decisions")
    timeline=[("1 · Foundation","20%","Confirm source contracts, robots/PDPA, 2021-2026 scope, and province polygons."),("2 · Reliable ETL","40%","Build parallel TaskGroups, polygon filtering, validation, dedup, and UPSERT tests."),("3 · User experience","25%","Create point map, annual counts, magnitude statistics, filters, and status view."),("4 · Evidence","15%","Run twice, verify 3-source counts and 100+ exact-scope rows, then finalize report.")]
    y=H-38*mm
    for i,(name,pct,desc) in enumerate(timeline):
        x=18*mm+i*68*mm
        c.setFillColor(colors.HexColor("#102b3d")); c.roundRect(x,y-65*mm,61*mm,62*mm,4*mm,fill=1,stroke=0)
        c.setFillColor(ORANGE); c.setFont("Helvetica-Bold",18); c.drawString(x+6*mm,y-13*mm,pct)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold",10); c.drawString(x+6*mm,y-23*mm,name)
        p(c,desc,x+6*mm,y-29*mm,49*mm,8,PALE,11)
    p(c,"<b>Deliberately excluded:</b> Selenium (explicitly prohibited), personal or felt-report respondent data (PDPA risk), predictive claims, and events that merely contain the word Thailand while their coordinates fall outside the country polygons. Priority was given to reproducibility, geographic correctness, failure tolerance, data quality, and idempotency.",18*mm,42*mm,W-36*mm,10,PALE,14)
    p(c,"<b>Submission checklist:</b> 100+ database rows · run DAG twice · capture live Graph/Grid/dashboard images · confirm second count is unchanged · export this PDF (maximum 3 pages).",18*mm,22*mm,W-36*mm,9,TEAL,12)
    c.save()
    print(PDF)


if __name__ == "__main__":
    build()

