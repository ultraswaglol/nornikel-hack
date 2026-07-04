# generate_test_pdfs.py
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def create_pdf(filename, title, content):
    """Вспомогательная функция для генерации текстового PDF"""
    os.makedirs("test_documents", exist_ok=True)
    filepath = os.path.join("test_documents", filename)
    c = canvas.Canvas(filepath, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, title)
    
    c.setFont("Helvetica", 10)
    y = 700
    for line in content:
        if y < 50:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = 750
        c.drawString(50, y, line)
        y -= 20
    c.save()
    print(f"Файл создан: {filepath}")

# 1. Документ по обессоливанию воды
create_pdf(
    "report_water_desalination.pdf",
    "R&D Report: Water Desalination Methods for Enrichment Plant",
    [
        "Author: Research Institute of Metallurgy",
        "This report describes the technological solutions for mine water desalination at the enrichment plant.",
        "The input water contains several elements: Sulfates (250 mg/L), Chlorides (280 mg/L), Ca (210 mg/L), Mg (230 mg/L), Na (240 mg/L).",
        "We tested the reverse osmosis technology (Method of reverse osmosis) to achieve purification.",
        "The experiment proved that reverse osmosis operates at condition of pressure up to 1.5 MPa.",
        "The resulting dry residue (Dry residue property) was measured at 950 mg/dm3.",
        "This dry residue conforms to the target threshold of <= 1000 mg/dm3.",
        "Conclusion: Reverse osmosis is recommended as the optimal desalination process for this water composition."
    ]
)

# 2. Документ по электроэкстракции никеля (Отечественная практика)
create_pdf(
    "report_nickel_electrowinning_ru.pdf",
    "Otchet: Electrowinning of Nickel and Catholyte Circulation (RU)",
    [
        "Author: Nornickel Laboratory of Hydrometallurgy",
        "This study describes the technical solutions of catholyte circulation in nickel electrowinning.",
        "To optimize the nickel deposition on cathodes, we implemented a double diaphragm cell design.",
        "The catholyte circulation process operates at optimal parameters.",
        "Our experiments showed that the optimal catholyte circulation speed is 1.5 m/s.",
        "Operating at a speed of 1.5 m/s minimizes the impurities in the nickel cathodes.",
        "This is the recommended standard for domestic Russian metallurgy plants."
    ]
)

# 3. Документ по электроэкстракции никеля (Зарубежная практика - со специальным конфликтом)
create_pdf(
    "report_nickel_electrowinning_global.pdf",
    "Global Practice: Electrowinning of Nickel and Catholyte Circulation Speed",
    [
        "Author: Outokumpu Technology Research",
        "In international metallurgy practice, nickel electrowinning requires high efficiency parameters.",
        "We analyzed the process of catholyte circulation in diaphragm cells.",
        "Our research proves that the optimal catholyte circulation speed must be maintained at 3.5 m/s.",
        "We validated that the speed of 3.5 m/s prevents depletion of nickel ions in the near-cathode layer.",
        "Note: Maintaining speed below 2.0 m/s leads to lower efficiency and dendritic cathode growth.",
        "This process is widely used in Outokumpu plants globally."
    ]
)