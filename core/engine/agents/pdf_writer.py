import os
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT

class PDFWriter:
    def __init__(self):
        self.page_size = A4
        self.margins = 72

    def generate_court_pdf(self, layout_text: str, output_path: str):
        directory = os.path.dirname(output_path)
        if not os.path.exists(directory) and directory != "":
            os.makedirs(directory)

        doc = SimpleDocTemplate(
            output_path, pagesize=self.page_size,
            rightMargin=self.margins, leftMargin=self.margins,
            topMargin=self.margins, bottomMargin=self.margins
        )

        styles = getSampleStyleSheet()
        
        style_court = ParagraphStyle(
            'CourtBody',
            parent=styles['Normal'],
            fontName='Times-Roman',
            fontSize=12,
            leading=20,
            alignment=TA_JUSTIFY,
            spaceAfter=14
        )
        
        style_center = ParagraphStyle(
            'CourtCenter',
            parent=styles['Normal'],
            fontName='Times-Roman',
            fontSize=12,
            leading=20,
            alignment=TA_CENTER,
            spaceAfter=14
        )

        story = []
        # Splitting correctly into blocks
        paragraphs = layout_text.split('\n\n')
        
        for p_text in paragraphs:
            cleaned_text = p_text.strip()
            if not cleaned_text:
                continue
                
            # Replace actual newlines within a block with Platypus native <br/>
            cleaned_text = cleaned_text.replace('\n', '<br/>')
            
            try:
                # If block intends to be centered
                if "IN THE HON'BLE" in cleaned_text or "VERSUS" in cleaned_text or "----------" in cleaned_text or "APPLICATION FOR GRANT" in cleaned_text:
                    p = Paragraph(cleaned_text, style_center)
                elif "ADVOCATE_NAME" in cleaned_text or "ADVOCATE FOR APPLICANT" in cleaned_text:
                    # Align right explicitly for signatures via paragraph alignment override
                    style_right = ParagraphStyle('CourtRight', parent=style_court, alignment=2) # 2 = TA_RIGHT
                    p = Paragraph(cleaned_text, style_right)
                else:    
                    p = Paragraph(cleaned_text, style_court)
                
                story.append(p)
            except Exception as e:
                # Absolute fallback stripping raw HTML if ReportLab still panics
                fallback = cleaned_text.replace("<", "").replace(">", "")
                story.append(Paragraph(fallback, style_court))

        doc.build(story)
