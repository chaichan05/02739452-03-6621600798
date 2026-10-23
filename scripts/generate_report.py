"""สร้างรายงานสรุปโครงงานภาษาไทย ความยาว 3 หน้า"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle


OUT = Path("/opt/airflow/output/pdf")
SHOTS = Path("/opt/airflow/output/screenshots")
FONT_DIR = Path("/opt/airflow/scripts/fonts")
PDF = OUT / "03_6621600798_summary.pdf"
REPOSITORY_URL = "https://github.com/chaichan05/02739452-03-6621600798"

PAGE = landscape(A4)
W, H = PAGE
NAVY = colors.HexColor("#07131f")
TEAL = colors.HexColor("#2ab7a9")
ORANGE = colors.HexColor("#f4a259")
PALE = colors.HexColor("#edf4f7")
MUTED = colors.HexColor("#9db2c3")
PANEL = colors.HexColor("#0c1e2d")
LINE = colors.HexColor("#245a70")


def register_fonts():
    pdfmetrics.registerFont(TTFont("Sarabun", FONT_DIR / "Sarabun-Regular.ttf"))
    pdfmetrics.registerFont(TTFont("Sarabun-Semibold", FONT_DIR / "Sarabun-SemiBold.ttf"))
    pdfmetrics.registerFontFamily(
        "Sarabun",
        normal="Sarabun",
        bold="Sarabun-Semibold",
        italic="Sarabun",
        boldItalic="Sarabun-Semibold",
    )


def paragraph_style(name, size=9, color=colors.white, leading=12, bold=False, align=0):
    return ParagraphStyle(
        name,
        fontName="Sarabun-Semibold" if bold else "Sarabun",
        fontSize=size,
        leading=leading,
        textColor=color,
        alignment=align,
        wordWrap="CJK",
    )


def header(c, page, title):
    c.setFillColor(NAVY)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(TEAL)
    c.rect(0, H - 8 * mm, W, 8 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Sarabun-Semibold", 18)
    c.drawString(15 * mm, H - 20 * mm, title)
    c.setFillColor(MUTED)
    c.setFont("Sarabun", 8)
    c.drawRightString(
        W - 15 * mm,
        9 * mm,
        f"6621600798 - ชัยชาญ กลิ่นประเสริฐ - หมู่ 700  |  หน้า {page}/3",
    )


def draw_paragraph(c, text, x, y, width, size=9, color=colors.white, leading=12, bold=False):
    style = paragraph_style(f"p-{x}-{y}-{size}", size, color, leading, bold)
    para = Paragraph(text, style)
    _, height = para.wrap(width, 100 * mm)
    para.drawOn(c, x, y - height)
    return y - height


def image_card(c, filename, label, x, y, width, height):
    c.setStrokeColor(LINE)
    c.roundRect(x, y, width, height, 4 * mm, stroke=1, fill=0)
    c.setFillColor(PANEL)
    c.roundRect(x + 1 * mm, y + 1 * mm, width - 2 * mm, height - 2 * mm, 3 * mm, fill=1, stroke=0)
    c.setFillColor(TEAL)
    c.setFont("Sarabun-Semibold", 9)
    c.drawString(x + 4 * mm, y + height - 7 * mm, label)
    path = SHOTS / filename
    if path.exists():
        c.drawImage(
            str(path),
            x + 3 * mm,
            y + 3 * mm,
            width - 6 * mm,
            height - 13 * mm,
            preserveAspectRatio=True,
            anchor="c",
        )
    else:
        c.setFillColor(ORANGE)
        c.setFont("Sarabun-Semibold", 11)
        c.drawCentredString(x + width / 2, y + height / 2, "เพิ่มภาพหลังเริ่มระบบ Docker")


def build():
    register_fonts()
    OUT.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(PDF), pagesize=PAGE)
    c.setTitle("ระบบข้อมูลแผ่นดินไหวในประเทศไทย - 6621600798")
    c.setAuthor("ชัยชาญ กลิ่นประเสริฐ")

    # หน้า 1: ภาพรวมและหลักฐานการทำงาน
    header(c, 1, "ระบบข้อมูลแผ่นดินไหวในประเทศไทย - ภาพรวมโครงงาน")
    y = H - 30 * mm
    y = draw_paragraph(
        c,
        "<b>ระดับที่ทำได้: ระดับ 3 และโบนัส</b> รวบรวมข้อมูลย้อนหลัง พ.ศ. 2564-2569 จากกรมอุตุนิยมวิทยา USGS และ GEOFON "
        "กรองเฉพาะพิกัดที่อยู่ภายในขอบเขตจังหวัดของประเทศไทยด้วย point-in-polygon ปรับเป็น schema เดียว "
        "ตัดข้อมูลซ้ำ ตรวจคุณภาพ และบันทึกแบบ UPSERT โดยหน้า Dashboard อ่านข้อมูลจาก PostgreSQL โดยตรง",
        15 * mm,
        y,
        W - 30 * mm,
        10,
        PALE,
        14,
    )
    y = draw_paragraph(
        c,
        f"<b>GitHub Repository:</b> {REPOSITORY_URL}",
        15 * mm,
        y - 2 * mm,
        W - 30 * mm,
        8,
        TEAL,
        11,
    )
    gap = 5 * mm
    box_width = (W - 30 * mm - 2 * gap) / 3
    box_height = 75 * mm
    box_y = 22 * mm
    image_card(c, "airflow_graph.png", "ภาพที่ 1: Graph View ของ DAG", 15 * mm, box_y, box_width, box_height)
    image_card(c, "airflow_grid.png", "ภาพที่ 2: Grid View และผลการรัน", 15 * mm + box_width + gap, box_y, box_width, box_height)
    image_card(c, "dashboard.png", "ภาพที่ 3: หน้า Dashboard", 15 * mm + 2 * (box_width + gap), box_y, box_width, box_height)
    c.showPage()

    # หน้า 2: ปัญหาและวิธีแก้
    header(c, 2, "ปัญหาที่พบ วิธีหาสาเหตุ และวิธีแก้ไข")
    rows = [
        ["ปัญหาและอาการ", "วิธีหาสาเหตุ", "วิธีแก้ไข"],
        [
            "หน้าเว็บ TMD ไม่มี API และมีทั้งเวลาไทยกับเวลา UTC",
            "ตรวจโครงสร้าง HTML จริง พบเลขเหตุการณ์และเวลาชุดที่ระบุ UTC แยกจากกัน",
            "ใช้ Requests และ BeautifulSoup โดยไม่ใช้ Selenium เลือกเวลา UTC ตรวจ robots.txt จำกัด 5 หน้า และหน่วง request 1 วินาที",
        ],
        [
            "การกรองด้วยชื่อสถานที่หรือกรอบสี่เหลี่ยมทำให้มีเหตุการณ์นอกประเทศไทย",
            "พล็อตพิกัดบริเวณขอบประเทศ พบจุดในเมียนมา ลาว มาเลเซีย และอ่าวไทย",
            "ใช้ point-in-polygon กับขอบเขต ADM1 เก็บเฉพาะจุดที่ตรงกับ polygon และใช้ชื่อ polygon เป็นจังหวัด",
        ],
        [
            "หากแหล่งข้อมูลหนึ่งล่ม DAG เดิมอาจหยุดทั้งหมด",
            "ตรวจเส้นทางการส่งต่อ failure จากงาน extract แบบขนานไปยังขั้น merge",
            "แยกจับข้อผิดพลาดของแต่ละแหล่งเป็น status record แล้วให้ merge ทำงานต่อ พร้อมระบุสถานะ degraded",
        ],
        [
            "การรันซ้ำอาจทำให้จำนวนแถวเพิ่มขึ้น",
            "ทดสอบ INSERT แบบปกติ พบว่าเหตุการณ์เดิมถูกบันทึกซ้ำในแต่ละรอบ",
            "สร้าง event fingerprint เป็น primary key และใช้ ON CONFLICT DO UPDATE รวม source และรหัสเหตุการณ์เดิม",
        ],
    ]
    head_style = paragraph_style("table-head", 8.5, NAVY, 10, True)
    cell_style = paragraph_style("table-cell", 8.2, PALE, 11)
    data = [
        [Paragraph(str(value), head_style if row_index == 0 else cell_style) for value in row]
        for row_index, row in enumerate(rows)
    ]
    table = Table(data, colWidths=[82 * mm, 92 * mm, 92 * mm], rowHeights=[12 * mm, 30 * mm, 30 * mm, 30 * mm, 30 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), TEAL),
                ("BACKGROUND", (0, 1), (-1, -1), PANEL),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    table.wrapOn(c, W, H)
    table.drawOn(c, 15 * mm, H - 174 * mm)
    c.showPage()

    # หน้า 3: แผนและการจัดลำดับงาน
    header(c, 3, "การวางแผน การจัดลำดับงาน และขอบเขตที่ตัดออก")
    timeline = [
        ("1 - วางรากฐาน", "20%", "ตรวจเงื่อนไขแหล่งข้อมูล robots.txt ขอบเขตปี และ polygon จังหวัด"),
        ("2 - สร้าง ETL", "40%", "พัฒนา TaskGroup แบบขนาน การกรองพิกัด validation dedup และ UPSERT"),
        ("3 - สร้าง Dashboard", "25%", "ทำแผนที่ กราฟรายปี สถิติขนาด ตัวกรอง ตาราง และหน้าสถานะ"),
        ("4 - ตรวจหลักฐาน", "15%", "รันซ้ำ ตรวจข้อมูล 3 แหล่งและ 100+ แถว แล้วจัดทำรายงานสรุป"),
    ]
    y = H - 38 * mm
    for index, (name, percent, description) in enumerate(timeline):
        x = 18 * mm + index * 68 * mm
        c.setFillColor(colors.HexColor("#102b3d"))
        c.roundRect(x, y - 65 * mm, 61 * mm, 62 * mm, 4 * mm, fill=1, stroke=0)
        c.setFillColor(ORANGE)
        c.setFont("Sarabun-Semibold", 18)
        c.drawString(x + 6 * mm, y - 13 * mm, percent)
        c.setFillColor(colors.white)
        c.setFont("Sarabun-Semibold", 10)
        c.drawString(x + 6 * mm, y - 23 * mm, name)
        draw_paragraph(c, description, x + 6 * mm, y - 29 * mm, 49 * mm, 8.2, PALE, 11)

    draw_paragraph(
        c,
        "<b>งานที่ตัดออก:</b> ไม่ใช้ Selenium ตามข้อกำหนด ไม่เก็บข้อมูลผู้รายงานหรือข้อมูลส่วนบุคคลเพื่อลดความเสี่ยงด้าน PDPA "
        "ไม่สร้างแบบจำลองพยากรณ์ และไม่เก็บเหตุการณ์ที่เพียงมีคำว่า Thailand แต่พิกัดอยู่นอก polygon ประเทศไทย "
        "โดยให้ความสำคัญกับความถูกต้องของพื้นที่ การรันซ้ำได้ ความทนทานเมื่อแหล่งข้อมูลล่ม และคุณภาพข้อมูล",
        18 * mm,
        43 * mm,
        W - 36 * mm,
        9.5,
        PALE,
        14,
    )
    draw_paragraph(
        c,
        "<b>ผลตรวจสุดท้าย:</b> ฐานข้อมูล 134 รายการ - ครบ 3 แหล่ง - ปี พ.ศ. 2564-2569 - ผ่านการตรวจ polygon - รันซ้ำแล้วจำนวนแถวไม่เพิ่ม - PDF 3 หน้า",
        18 * mm,
        22 * mm,
        W - 36 * mm,
        9,
        TEAL,
        12,
    )
    c.save()
    print(PDF)


if __name__ == "__main__":
    build()
