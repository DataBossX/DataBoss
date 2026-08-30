import os
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor('#C00000'))
        
        # Mandatory Header: Top Right & Top Left
        self.drawString(36, 580, "FOR REVIEW — HOLD NO EXTERNAL RELEASE")
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor('#555555'))
        self.drawRightString(756, 580, "Section 32-11N-25W • Beckham County, OK • Challenger Report")
        
        # Mandatory Footer
        self.drawString(36, 25, "CONFIDENTIAL — ATTORNEY-CLIENT / EXAMINER WORK PRODUCT • DATA PRIVACY PROTECTED")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(756, 25, page_str)
        
        # Draw thin separator lines
        self.setStrokeColor(colors.HexColor('#CCCCCC'))
        self.setLineWidth(0.5)
        self.line(36, 574, 756, 574)
        self.line(36, 35, 756, 35)
        
        self.restoreState()

def create_full_internal_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=45,
        bottomMargin=45
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=16,
        textColor=colors.HexColor('#1F4E78')
    )
    
    hold_style = ParagraphStyle(
        'HoldHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        textColor=colors.HexColor('#C00000')
    )
    
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#1F4E78'),
        spaceBefore=8,
        spaceAfter=4
    )
    
    cell_bold = ParagraphStyle(
        'CellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9,
        textColor=colors.black
    )
    
    cell_regular = ParagraphStyle(
        'CellRegular',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=8.5,
        textColor=colors.black
    )
    
    cell_warning = ParagraphStyle(
        'CellWarning',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        leading=8.5,
        textColor=colors.HexColor('#B25900')
    )
    
    story = []
    
    # ---------------------------------------------------------
    # PAGE 1: TITLE & EXECUTIVE OVERVIEW
    # ---------------------------------------------------------
    story.append(Paragraph("SECTION 32-11N-25W, BECKHAM COUNTY, OKLAHOMA", title_style))
    story.append(Paragraph("INDEPENDENT AI CHALLENGER CURSORY TITLE REPORT — FULL INTERNAL AUDIT PACKAGE", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("FOR REVIEW — HOLD NO EXTERNAL RELEASE", hold_style))
    story.append(Spacer(1, 8))
    
    overview_meta = [
        [Paragraph("<b>Target Property:</b>", cell_bold), Paragraph("Section 32, Township 11 North, Range 25 West, Beckham County, OK (640.00 Gross Acres)", cell_regular),
         Paragraph("<b>Primary Interest:</b>", cell_bold), Paragraph("Diversified Production LLC / Predecessor Working Interest Chain", cell_regular)],
        [Paragraph("<b>Effective Date:</b>", cell_bold), Paragraph("August 6, 2026 (Forward record search cutoff March 2, 2023)", cell_regular),
         Paragraph("<b>Reviewing Model:</b>", cell_bold), Paragraph("Gemini 3.7 Flash (Cloud Agent Independent Challenger)", cell_regular)],
        [Paragraph("<b>Audit Method:</b>", cell_bold), Paragraph("Contradiction-First & Evidence-Grounded Reconciliation", cell_regular),
         Paragraph("<b>Curative Priority:</b>", cell_bold), Paragraph("Bk 2434/751 Teocalli Lead • Bk 1697/236 Ex. A • Index Pg 48", cell_regular)]
    ]
    t_meta = Table(overview_meta, colWidths=[90, 260, 90, 280])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F2F4F8')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#1F4E78')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D9D9D9')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 8))
    
    story.append(Paragraph("Executive Adjudication & Finding Status", section_heading))
    
    exec_table_data = [
        [Paragraph("Category", cell_bold), Paragraph("Legal / Title Finding", cell_bold), Paragraph("Evidence Status", cell_bold), Paragraph("Governing Rationale & Basis", cell_bold)],
        [Paragraph("ESTABLISHED", cell_bold), Paragraph("640.00 Nominal Gross Acre section geometry across 5 primary fee tracts.", cell_regular), Paragraph("PROVED", cell_bold), Paragraph("Patent 3/469 (NE/4) & Land Office Receiver Receipts 3894, 3895, Biggs.", cell_regular)],
        [Paragraph("ESTABLISHED", cell_bold), Paragraph("Diversified Production LLC is latest scheduled claimant for OK48147.001.1.", cell_regular), Paragraph("PROVED (Sched.)", cell_bold), Paragraph("Direct asset schedules at Bk 2400/Pg 566 and Bk 2395/Pg 462.", cell_regular)],
        [Paragraph("QUALIFIED", cell_bold), Paragraph("Estimated mineral title balances to 640.00 NMA on last-located basis.", cell_regular), Paragraph("ESTIMATED", cell_regular), Paragraph("Reconstructed ending schedules; arithmetic balance is NOT proof of current title.", cell_regular)],
        [Paragraph("QUALIFIED", cell_bold), Paragraph("14 Historical Oil & Gas Leases recorded between 1947 and 1979.", cell_regular), Paragraph("ESTIMATED", cell_regular), Paragraph("Primary terms extracted from direct faces; modern continuation is qualified.", cell_regular)],
        [Paragraph("NOT DETERMINED", cell_warning), Paragraph("Current section-wide Diversified Working Interest (WI), NRI, & ORRI.", cell_warning), Paragraph("UNPROVED", cell_warning), Paragraph("15.000875% and 51.25% leads lack unclouded 8/8 baseline & Tapstone bridge.", cell_regular)],
        [Paragraph("NOT DETERMINED", cell_warning), Paragraph("Current lease-by-lease HBP validity across all tracts and depths.", cell_warning), Paragraph("UNPROVED", cell_warning), Paragraph("Blanket section production does not prove tract/formation HBP.", cell_regular)],
        [Paragraph("NOT DETERMINED", cell_warning), Paragraph("Post-cutoff divestiture status under Bk 2434/Pg 751 (Teocalli).", cell_warning), Paragraph("CRITICAL OPEN", cell_warning), Paragraph("If Section 32 is included, Diversified interest was conveyed out.", cell_regular)]
    ]
    t_exec = Table(exec_table_data, colWidths=[90, 240, 90, 300])
    t_exec.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1F4E78')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#1F4E78')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D9D9D9')),
        ('BACKGROUND', (0,1), (0,2), colors.HexColor('#D9E1F2')),
        ('BACKGROUND', (0,3), (0,4), colors.HexColor('#F9FAFB')),
        ('BACKGROUND', (0,5), (0,7), colors.HexColor('#FFF2CC')),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(t_exec)
    
    # ---------------------------------------------------------
    # PAGE 2: TITLE SUMMARY BY TRACT
    # ---------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("ESTIMATED MINERAL TITLE SCHEDULE BY TRACT (640.00 GROSS ACRES)", title_style))
    story.append(Paragraph("FOR REVIEW — HOLD NO EXTERNAL RELEASE • Estimated Last-Located Record Owners (Not Confirmed Present Title)", hold_style))
    story.append(Spacer(1, 6))
    
    title_table_data = [
        [Paragraph("Tract", cell_bold), Paragraph("Estimated / Last-Located Record Owner", cell_bold), Paragraph("EST. NMA", cell_bold), Paragraph("Tract Ac", cell_bold), Paragraph("OGL Ref", cell_bold), Paragraph("Lease Status", cell_bold), Paragraph("Vesting Source & Assumptions", cell_bold)],
        # Tract 1
        [Paragraph("Tract 1 (NE/4)", cell_regular), Paragraph("Adolf Bollenbach Successors (WD 10/255)", cell_regular), Paragraph("65.000", cell_regular), Paragraph("160.00", cell_regular), Paragraph("None", cell_regular), Paragraph("Status Not Determined", cell_regular), Paragraph("Residual vests in 1910 deed; downstream chain breaks. Title OPEN.", cell_regular)],
        [Paragraph("Tract 1 (NE/4)", cell_regular), Paragraph("Charlie B. Crook Heirs (5 Co-owners @ 8 NMA)", cell_regular), Paragraph("40.000", cell_regular), Paragraph("160.00", cell_regular), Paragraph("OGL 2 (264/345)", cell_regular), Paragraph("1/8; Cursory Estimate", cell_regular), Paragraph("Vested: Final Decree 845/150-157 (1985). Forward title unconfirmed.", cell_regular)],
        [Paragraph("Tract 1 (NE/4)", cell_regular), Paragraph("F. L. & J. L. Randel (share & share alike)", cell_regular), Paragraph("3.000", cell_regular), Paragraph("160.00", cell_regular), Paragraph("OGL 9, 10", cell_regular), Paragraph("1/8; Cursory Estimate", cell_regular), Paragraph("Vested: MD 92/47 (1950). Forward record search cutoff 03/02/2023.", cell_regular)],
        [Paragraph("Tract 1 (NE/4)", cell_regular), Paragraph("Great Western Oil & Gas, Inc.", cell_regular), Paragraph("10.000", cell_regular), Paragraph("160.00", cell_regular), Paragraph("OGL 11 (376/369)", cell_regular), Paragraph("1/8; Cursory Estimate", cell_regular), Paragraph("Vested: MD 367/632 (1978). Corporate succession open.", cell_regular)],
        [Paragraph("Tract 1 (NE/4)", cell_regular), Paragraph("Jean J. Shearer, Florence J. Chunn, Wm. R. Jenkins", cell_regular), Paragraph("2.000", cell_regular), Paragraph("160.00", cell_regular), Paragraph("None", cell_regular), Paragraph("Unleased / Open", cell_regular), Paragraph("Vested: MD 250/26 (1970). Unleased mineral interest.", cell_regular)],
        [Paragraph("Tract 1 (NE/4)", cell_regular), Paragraph("Ellen W. Crook Probate Beneficiaries (83/259)", cell_regular), Paragraph("40.000", cell_regular), Paragraph("160.00", cell_regular), Paragraph("None", cell_regular), Paragraph("Status Not Determined", cell_regular), Paragraph("Collective vesting per decree; individual allocations unstated.", cell_regular)],
        # Tract 2
        [Paragraph("Tract 2 (N/2 NW/4)", cell_regular), Paragraph("B.E. Maddoux & D.H. Maddoux (10 NMA each)", cell_regular), Paragraph("20.000", cell_regular), Paragraph("80.00", cell_regular), Paragraph("None", cell_regular), Paragraph("No Active OGL", cell_regular), Paragraph("Vested: Stipulation 153/161-162 (1958). Current status open.", cell_regular)],
        [Paragraph("Tract 2 (N/2 NW/4)", cell_regular), Paragraph("George T. & Renata Harrison", cell_regular), Paragraph("20.000", cell_regular), Paragraph("80.00", cell_regular), Paragraph("OGL 6 (340/323)", cell_regular), Paragraph("1/8; Cursory Estimate", cell_regular), Paragraph("Vested: MD 92/47. Covers N/2 NW/4 and N/2 SW/4.", cell_regular)],
        [Paragraph("Tract 2 (N/2 NW/4)", cell_regular), Paragraph("Sanditen Parties (Edgar, Julius, Herman, Morris)", cell_regular), Paragraph("20.000", cell_regular), Paragraph("80.00", cell_regular), Paragraph("None", cell_regular), Paragraph("Status Not Determined", cell_regular), Paragraph("Vested: MD 85/363-366 (1950). Heirs & succession open.", cell_regular)],
        [Paragraph("Tract 2 (N/2 NW/4)", cell_regular), Paragraph("Ola Keathley Heirs / LeGrand Successors", cell_regular), Paragraph("20.000", cell_regular), Paragraph("80.00", cell_regular), Paragraph("None", cell_regular), Paragraph("Status Not Determined", cell_regular), Paragraph("Vested: Probate P-76-78. Final distribution decree incomplete.", cell_regular)],
        # Tract 3
        [Paragraph("Tract 3 (S/2 NW/4)", cell_regular), Paragraph("C. R. Bennett (Historic Mineral Grantee)", cell_regular), Paragraph("40.000", cell_regular), Paragraph("80.00", cell_regular), Paragraph("None", cell_regular), Paragraph("No Active OGL", cell_regular), Paragraph("Vested: MD 81/194 (1949). Forward record search cutoff 03/02/2023.", cell_regular)],
        [Paragraph("Tract 3 (S/2 NW/4)", cell_regular), Paragraph("Heller Company & Bettye Folmar Norris (20 NMA ea)", cell_regular), Paragraph("40.000", cell_regular), Paragraph("80.00", cell_regular), Paragraph("None", cell_regular), Paragraph("Status Not Determined", cell_regular), Paragraph("Vested: MD 85/222 & Decree 262/490. Entity/heir succession open.", cell_regular)],
        # Tract 4
        [Paragraph("Tract 4 (SW/4)", cell_regular), Paragraph("Gertrude L. LaFortune (N/2 SW/4)", cell_regular), Paragraph("40.000", cell_regular), Paragraph("160.00", cell_regular), Paragraph("OGL 4, 5", cell_regular), Paragraph("3/16; Cursory Estimate", cell_regular), Paragraph("Vested: MD 85/222. Overlapping N/2 SW/4 leasehold.", cell_regular)],
        [Paragraph("Tract 4 (SW/4)", cell_regular), Paragraph("Carol S. Leach & Cynthia S. Kruse (20 NMA ea)", cell_regular), Paragraph("40.000", cell_regular), Paragraph("160.00", cell_regular), Paragraph("OGL 7, 8", cell_regular), Paragraph("3/16; Cursory Estimate", cell_regular), Paragraph("Vested: Probate Decree. N/2 SW/4 leasehold.", cell_regular)],
        [Paragraph("Tract 4 (SW/4)", cell_regular), Paragraph("Cora B. LeGrand (S/2 SW/4)", cell_regular), Paragraph("80.000", cell_regular), Paragraph("160.00", cell_regular), Paragraph("OGL 3 (307/31)", cell_regular), Paragraph("1/8; Cursory Estimate", cell_regular), Paragraph("Vested: Patent/Deed chain. Covers S/2 SW/4 & W/2 SE/4.", cell_regular)],
        # Tract 5
        [Paragraph("Tract 5 (SE/4)", cell_regular), Paragraph("Cora B. & S. A. Garrett (E/2 SE/4)", cell_regular), Paragraph("80.000", cell_regular), Paragraph("160.00", cell_regular), Paragraph("OGL 1 (63/33)", cell_regular), Paragraph("1/8; Historical Lease", cell_regular), Paragraph("Vested: Biggs receiver receipt chain. E/2 SE/4 base lease.", cell_regular)],
        [Paragraph("Tract 5 (SE/4)", cell_regular), Paragraph("Cora B. LeGrand (W/2 SE/4)", cell_regular), Paragraph("80.000", cell_regular), Paragraph("160.00", cell_regular), Paragraph("OGL 3 (307/31)", cell_regular), Paragraph("1/8; Cursory Estimate", cell_regular), Paragraph("Vested: Deed 307/31 chain. Covers W/2 SE/4.", cell_regular)],
        # Total
        [Paragraph("TOTAL", cell_bold), Paragraph("ESTIMATED SECTION 32 RECORD RECONCILIATION TOTAL", cell_bold), Paragraph("640.000", cell_bold), Paragraph("640.00", cell_bold), Paragraph("—", cell_bold), Paragraph("—", cell_bold), Paragraph("Arithmetic closure represents record reconciliation, NOT confirmed marketable title.", cell_bold)]
    ]
    
    t_title = Table(title_table_data, colWidths=[75, 175, 45, 40, 65, 80, 240])
    t_title.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1F4E78')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#1F4E78')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D9D9D9')),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#D9E1F2')),
        ('TOPPADDING', (0,0), (-1,-1), 1.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
    ]))
    story.append(t_title)
    
    # ---------------------------------------------------------
    # PAGE 3: WORKING INTEREST & BURDENS (WI 1 & WI 2)
    # ---------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("WORKING INTEREST & BURDEN ADJUDICATION (WI 1 & WI 2)", title_style))
    story.append(Paragraph("FOR REVIEW — HOLD NO EXTERNAL RELEASE • Predecessor Asset Trace vs. Present Section-Wide Quantum", hold_style))
    story.append(Spacer(1, 6))
    
    story.append(Paragraph("Principal Modern Leasehold Chain (Staghorn -> Chesapeake -> Tapstone -> KL CHK -> Diversified)", section_heading))
    
    wi1_data = [
        [Paragraph("Step", cell_bold), Paragraph("Book / Page", cell_bold), Paragraph("Grantor -> Grantee", cell_bold), Paragraph("Transaction Branch", cell_bold), Paragraph("Adjudicated Title Status", cell_bold), Paragraph("Curative Requirement & Limitation", cell_bold)],
        [Paragraph("1", cell_regular), Paragraph("Bk 1697/Pg 236", cell_regular), Paragraph("Staghorn Resources -> Chesapeake Exploration", cell_regular), Paragraph("Unquantified", cell_regular), Paragraph("Scheduled Predecessor Lead", cell_bold), Paragraph("Full Exhibit A required to identify base leases.", cell_regular)],
        [Paragraph("2", cell_regular), Paragraph("Bk 2340/Pg 403", cell_regular), Paragraph("Chesapeake Affiliates -> Tapstone Energy LLC", cell_regular), Paragraph("Tapstone Branch", cell_regular), Paragraph("Parallel Tapstone Branch", cell_regular), Paragraph("Missing Tapstone asset schedule / bridge.", cell_regular)],
        [Paragraph("3", cell_regular), Paragraph("Bk 2340/Pg 490", cell_regular), Paragraph("Chesapeake Affiliates -> KL CHK SPV LLC", cell_regular), Paragraph("Restructuring", cell_regular), Paragraph("Principal Predecessor", cell_bold), Paragraph("Section 32 index scope; property exhibits absent.", cell_regular)],
        [Paragraph("4", cell_regular), Paragraph("Bk 2371/Pg 470", cell_regular), Paragraph("KL CHK SPV LLC -> Diversified (51.25%) & OCM Denali (48.75%)", cell_regular), Paragraph("51.25% / 48.75%", cell_regular), Paragraph("Transaction Split (Separate)", cell_bold), Paragraph("Do NOT report 51.25% as section-wide WI.", cell_regular)],
        [Paragraph("5", cell_regular), Paragraph("Bk 2389/Pg 500", cell_regular), Paragraph("Diversified / DP Merger Parties -> DP Legacy Tapstone", cell_regular), Paragraph("Merger", cell_regular), Paragraph("Merger Path Established", cell_regular), Paragraph("Merger certificate & asset schedules absent.", cell_regular)],
        [Paragraph("6", cell_regular), Paragraph("Bk 2395/Pg 415", cell_regular), Paragraph("DP Legacy Tapstone -> Diversified ABS VI & DP Sooner", cell_regular), Paragraph("OK48147.001.1", cell_regular), Paragraph("Asset Identity Supported", cell_bold), Paragraph("Estate quantum, net acres, and depths blank on schedule.", cell_regular)],
        [Paragraph("7", cell_regular), Paragraph("Bk 2400/Pg 551", cell_regular), Paragraph("DP Sooner HoldCo LLC -> Diversified Production LLC", cell_regular), Paragraph("OK48147.001.1", cell_regular), Paragraph("Last Supported Claimant", cell_bold), Paragraph("Supported through 03/02/2023; post-cutoff filings govern.", cell_regular)],
        [Paragraph("8", cell_regular), Paragraph("Bk 2434/Pg 751", cell_regular), Paragraph("Diversified Production LLC -> Teocalli Exploration LLC", cell_regular), Paragraph("Post-Cutoff Lead", cell_regular), Paragraph("Potential Divestiture Out", cell_warning), Paragraph("CRITICAL P0: Read complete instrument & schedule.", cell_regular)]
    ]
    t_wi1 = Table(wi1_data, colWidths=[25, 65, 175, 80, 115, 260])
    t_wi1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1F4E78')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#1F4E78')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D9D9D9')),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(t_wi1)
    story.append(Spacer(1, 6))
    
    story.append(Paragraph("Adjudicated Working Interest, NRI, & ORRI Summary Table", section_heading))
    
    wi_sum_data = [
        [Paragraph("Component", cell_bold), Paragraph("Reported / Stated Value", cell_bold), Paragraph("Adjudicated Status", cell_bold), Paragraph("Governing Epistemic Rule & Examiner Rationale", cell_bold)],
        [Paragraph("Diversified Transaction Branch", cell_bold), Paragraph("51.25%", cell_regular), Paragraph("Branch Context Only", cell_regular), Paragraph("Represents share of acquired KL CHK assets; cannot be applied as 8/8 section WI.", cell_regular)],
        [Paragraph("OCM Denali Parallel Branch", cell_bold), Paragraph("48.75%", cell_regular), Paragraph("Separate Claimant", cell_regular), Paragraph("Must remain strictly segregated; not an interest of Diversified Production LLC.", cell_regular)],
        [Paragraph("Predecessor Product (15.000875%)", cell_bold), Paragraph("15.000875%", cell_regular), Paragraph("REPORTED_UNVERIFIED", cell_warning), Paragraph("29.27% × 51.25% arithmetic product; unproved baseline. NOT CURRENT WI.", cell_regular)],
        [Paragraph("Current Gross Working Interest (WI)", cell_bold), Paragraph("NOT DETERMINED", cell_warning), Paragraph("UNPROVED / OPEN", cell_warning), Paragraph("Asset schedule quantum is blank; Teocalli post-cutoff lead unreviewed.", cell_regular)],
        [Paragraph("Current Net Revenue Interest (NRI)", cell_bold), Paragraph("NOT DETERMINED", cell_warning), Paragraph("UNPROVED / OPEN", cell_warning), Paragraph("Historic ORRIs (Union 1/8 & 1/16) and JOA burdens lack modern payout/reversion proof.", cell_regular)],
        [Paragraph("Current Overriding Royalty (ORRI)", cell_bold), Paragraph("NOT DETERMINED", cell_warning), Paragraph("UNPROVED / OPEN", cell_warning), Paragraph("Carried read-only from Bk 502/267 and Bk 872/279 for audit tracking.", cell_regular)]
    ]
    t_wisum = Table(wi_sum_data, colWidths=[130, 80, 95, 415])
    t_wisum.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#595959')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#595959')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D9D9D9')),
        ('BACKGROUND', (0,3), (-1,6), colors.HexColor('#FFF2CC')),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(t_wisum)
    
    # ---------------------------------------------------------
    # PAGE 4: OGL SCHEDULE & REGULATORY WELL CONTEXT
    # ---------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("OIL & GAS LEASES & REGULATORY WELL CONTEXT", title_style))
    story.append(Paragraph("FOR REVIEW — HOLD NO EXTERNAL RELEASE • Lease Terms Extracted from Faces; Production Does Not Prove Blanket HBP", hold_style))
    story.append(Spacer(1, 6))
    
    story.append(Paragraph("Master Oil & Gas Lease (OGL) Schedule", section_heading))
    
    ogl_data_pdf = [
        [Paragraph("OGL #", cell_bold), Paragraph("Bk / Pg", cell_bold), Paragraph("Lease Date", cell_bold), Paragraph("Lessor", cell_bold), Paragraph("Original Lessee", cell_bold), Paragraph("Tract / Coverage", cell_bold), Paragraph("Gross Ac", cell_bold), Paragraph("Royalty", cell_bold), Paragraph("Primary Exp.", cell_bold), Paragraph("Current Qualified Status", cell_bold)],
        [Paragraph("1", cell_regular), Paragraph("63/33", cell_regular), Paragraph("1947-11-13", cell_regular), Paragraph("Cora B. & S.A. Garrett", cell_regular), Paragraph("C.E. McKinley", cell_regular), Paragraph("E/2 SE/4 (Tract 5)", cell_regular), Paragraph("80.0", cell_regular), Paragraph("1/8", cell_regular), Paragraph("1957-11-13", cell_regular), Paragraph("HBP Unconfirmed", cell_regular)],
        [Paragraph("2", cell_regular), Paragraph("264/345", cell_regular), Paragraph("1972-02-05", cell_regular), Paragraph("Charlie B. & Ima Crook", cell_regular), Paragraph("Union Oil Co.", cell_regular), Paragraph("NE/4 (Tract 1)", cell_regular), Paragraph("160.0", cell_regular), Paragraph("1/8", cell_regular), Paragraph("1977-02-05", cell_regular), Paragraph("HBP Unconfirmed", cell_regular)],
        [Paragraph("3", cell_regular), Paragraph("307/31", cell_regular), Paragraph("1976-04-29", cell_regular), Paragraph("Cora B. LeGrand", cell_regular), Paragraph("Union Oil Co.", cell_regular), Paragraph("W/2 SE/4 & S/2 SW/4", cell_regular), Paragraph("160.0", cell_regular), Paragraph("1/8", cell_regular), Paragraph("1979-04-29", cell_regular), Paragraph("HBP Unconfirmed", cell_regular)],
        [Paragraph("4, 5", cell_regular), Paragraph("340/302, 304", cell_regular), Paragraph("1977-10-14", cell_regular), Paragraph("Gertrude L. LaFortune", cell_regular), Paragraph("Union Oil Co.", cell_regular), Paragraph("N/2 SW/4 (Tract 4)", cell_regular), Paragraph("80.0", cell_regular), Paragraph("3/16", cell_regular), Paragraph("1980-10-14", cell_regular), Paragraph("HBP Unconfirmed", cell_regular)],
        [Paragraph("6", cell_regular), Paragraph("340/323", cell_regular), Paragraph("1977-09-29", cell_regular), Paragraph("George T. & Renata Harrison", cell_regular), Paragraph("Union Oil Co.", cell_regular), Paragraph("N/2 NW/4 & N/2 SW/4", cell_regular), Paragraph("160.0", cell_regular), Paragraph("1/8", cell_regular), Paragraph("1980-09-29", cell_regular), Paragraph("HBP Unconfirmed", cell_regular)],
        [Paragraph("7, 8", cell_regular), Paragraph("342/564, 566", cell_regular), Paragraph("1977-09-29", cell_regular), Paragraph("Leach & Kruse", cell_regular), Paragraph("Union Oil Co.", cell_regular), Paragraph("N/2 SW/4 (Tract 4)", cell_regular), Paragraph("80.0", cell_regular), Paragraph("3/16", cell_regular), Paragraph("1980-09-29", cell_regular), Paragraph("HBP Unconfirmed", cell_regular)],
        [Paragraph("9, 10", cell_regular), Paragraph("352/719, 721", cell_regular), Paragraph("1978-05-16", cell_regular), Paragraph("F.L. & J.L. Randel", cell_regular), Paragraph("Union Oil Co.", cell_regular), Paragraph("Part NE/4 (Tract 1)", cell_regular), Paragraph("3.0", cell_regular), Paragraph("1/8", cell_regular), Paragraph("1981-05-16", cell_regular), Paragraph("HBP Unconfirmed", cell_regular)],
        [Paragraph("11", cell_regular), Paragraph("376/369", cell_regular), Paragraph("1979-03-21", cell_regular), Paragraph("Great Western Oil & Gas", cell_regular), Paragraph("Union Oil Co.", cell_regular), Paragraph("Part NE/4 (Tract 1)", cell_regular), Paragraph("10.0", cell_regular), Paragraph("1/8", cell_regular), Paragraph("1982-03-21", cell_regular), Paragraph("HBP Unconfirmed", cell_regular)],
        [Paragraph("12", cell_regular), Paragraph("332/74", cell_regular), Paragraph("1977-08-01", cell_regular), Paragraph("Ralph W. Viersen Jr. et al.", cell_regular), Paragraph("Leede Exploration", cell_regular), Paragraph("NW/4 & SW/4", cell_regular), Paragraph("320.0", cell_regular), Paragraph("3/16", cell_regular), Paragraph("1980-08-01", cell_regular), Paragraph("Owner Coverage Defect", cell_warning)]
    ]
    t_ogl = Table(ogl_data_pdf, colWidths=[30, 55, 50, 105, 85, 95, 35, 30, 50, 185])
    t_ogl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1F4E78')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#1F4E78')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D9D9D9')),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(t_ogl)
    story.append(Spacer(1, 6))
    
    story.append(Paragraph("Regulatory Well & Unit Context (OCC Order 156126 & OTC Records)", section_heading))
    
    well_data_pdf = [
        [Paragraph("Well Name", cell_bold), Paragraph("API #", cell_bold), Paragraph("Current Operator", cell_bold), Paragraph("Formation / Interval", cell_bold), Paragraph("Location", cell_bold), Paragraph("Spud Date", cell_bold), Paragraph("Regulatory Significance", cell_bold)],
        [Paragraph("Crook 1-32", cell_regular), Paragraph("35-009-20312", cell_regular), Paragraph("Complete Oil & Gas Services LLC", cell_regular), Paragraph("Granite Wash (13,348-13,595')", cell_regular), Paragraph("NE/4 (Tract 1)", cell_regular), Paragraph("1980-01-26", cell_regular), Paragraph("Historic Granite Wash producer; wellbore burdens apply.", cell_regular)],
        [Paragraph("Twin 1-32", cell_regular), Paragraph("35-009-21391", cell_regular), Paragraph("BCE-Mach II LLC", cell_regular), Paragraph("Granite Wash (12,548-12,604')", cell_regular), Paragraph("NE/4 (Tract 1)", cell_regular), Paragraph("2004-07-15", cell_regular), Paragraph("Active BCE-Mach II operating unit context.", cell_regular)],
        [Paragraph("Carlson 12H", cell_regular), Paragraph("35-009-21893", cell_regular), Paragraph("Latigo Petroleum, LLC", cell_regular), Paragraph("Granite Wash Upper (Missourian)", cell_regular), Paragraph("Section 32 PUN", cell_regular), Paragraph("2014-05-10", cell_regular), Paragraph("Horizontal unit well; section-wide spacing order applies.", cell_regular)],
        [Paragraph("Carlson 7H", cell_regular), Paragraph("35-009-21923", cell_regular), Paragraph("Latigo Petroleum, LLC", cell_regular), Paragraph("Missourian", cell_regular), Paragraph("Section 32 PUN", cell_regular), Paragraph("2014-09-18", cell_regular), Paragraph("Wellbore carveout to Linn/FourPoint; excluded from Diversified.", cell_regular)],
        [Paragraph("Carlson 10H", cell_regular), Paragraph("35-009-21933", cell_regular), Paragraph("Latigo Petroleum, LLC", cell_regular), Paragraph("Missourian", cell_regular), Paragraph("Section 32 PUN", cell_regular), Paragraph("2015-01-22", cell_regular), Paragraph("Horizontal unit well; section-wide spacing order applies.", cell_regular)]
    ]
    t_well = Table(well_data_pdf, colWidths=[80, 65, 120, 120, 75, 55, 205])
    t_well.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#595959')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#595959')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D9D9D9')),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(t_well)
    
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Full Internal PDF generated at: {output_path}")

def create_boss_review_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=45,
        bottomMargin=45
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=15,
        textColor=colors.HexColor('#1F4E78')
    )
    
    hold_style = ParagraphStyle(
        'HoldHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=11.5,
        textColor=colors.HexColor('#C00000')
    )
    
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        textColor=colors.HexColor('#1F4E78'),
        spaceBefore=6,
        spaceAfter=3
    )
    
    cell_bold = ParagraphStyle(
        'CellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        leading=8.5,
        textColor=colors.black
    )
    
    cell_regular = ParagraphStyle(
        'CellRegular',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=6.5,
        leading=8,
        textColor=colors.black
    )
    
    cell_warning = ParagraphStyle(
        'CellWarning',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor('#B25900')
    )
    
    story = []
    
    # EXACT 1-PAGE BOSS REVIEW
    story.append(Paragraph("SECTION 32-11N-25W, BECKHAM COUNTY, OKLAHOMA — BOSS REVIEW SUMMARY", title_style))
    story.append(Paragraph("FOR REVIEW — HOLD NO EXTERNAL RELEASE • EXECUTIVE DECISION BRIEFING", hold_style))
    story.append(Spacer(1, 4))
    
    # Meta Summary Box
    meta_data = [
        [Paragraph("<b>Target Property:</b>", cell_bold), Paragraph("Section 32-11N-25W, Beckham Co., OK (640.00 Gross Ac)", cell_regular),
         Paragraph("<b>Primary Entity:</b>", cell_bold), Paragraph("Diversified Production LLC (Predecessor Chain)", cell_regular)],
        [Paragraph("<b>Effective Date:</b>", cell_bold), Paragraph("August 6, 2026 (Search cutoff March 2, 2023)", cell_regular),
         Paragraph("<b>Examiner:</b>", cell_bold), Paragraph("Gemini 3.7 Flash Challenger (Contradiction-First)", cell_regular)]
    ]
    t_meta = Table(meta_data, colWidths=[80, 270, 80, 290])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F2F4F8')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#1F4E78')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D9D9D9')),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 4))
    
    story.append(Paragraph("1. Primary Title & Working Interest Findings", section_heading))
    findings_data = [
        [Paragraph("Core Dimension", cell_bold), Paragraph("Adjudicated Conclusion", cell_bold), Paragraph("Evidence Status", cell_bold), Paragraph("Governing Constraint / Risk Disclosure", cell_bold)],
        [Paragraph("Diversified Working Interest (WI)", cell_bold), Paragraph("NOT DETERMINED (Blank on Schedule)", cell_warning), Paragraph("UNPROVED", cell_warning), Paragraph("Latest schedule at Bk 2400/566 proves asset identity (OK48147.001.1) but leaves estate quantum blank. Lacks 8/8 baseline.", cell_regular)],
        [Paragraph("Predecessor Product (15.000875%)", cell_bold), Paragraph("REPORTED_UNVERIFIED Lead Only", cell_regular), Paragraph("UNPROVED", cell_regular), Paragraph("Derived as 29.27% × 51.25% transaction branch; lacks unclouded 8/8 source title. MUST NOT BE REPORTED AS PRESENT WI.", cell_regular)],
        [Paragraph("OCM Denali Parallel Branch", cell_bold), Paragraph("48.75% Transaction Branch", cell_regular), Paragraph("PROVED (Branch)", cell_regular), Paragraph("Created under Bk 2371/470; belongs to OCM Denali and must remain strictly separate from Diversified.", cell_regular)],
        [Paragraph("Teocalli Divestiture Risk", cell_bold), Paragraph("CRITICAL OPEN ITEM (Bk 2434/751)", cell_warning), Paragraph("CURATIVE", cell_warning), Paragraph("Post-cutoff assignment from Diversified/DP to Teocalli. If Section 32 is included, Diversified interest was conveyed out.", cell_regular)],
        [Paragraph("Mineral Estate Reconciliation", cell_bold), Paragraph("640.00 NMA Last-Located Estimate", cell_regular), Paragraph("ESTIMATED", cell_regular), Paragraph("Reconstructed across 5 tracts (T1 160ac, T2 80ac, T3 80ac, T4 160ac, T5 160ac). Arithmetic balance is NOT present title proof.", cell_regular)],
        [Paragraph("Leasehold & HBP Continuation", cell_bold), Paragraph("Historical Leases (14 OGLs Qualified)", cell_regular), Paragraph("ESTIMATED", cell_regular), Paragraph("Creating terms extracted from faces; modern HBP is qualified. Blanket section production does not prove tract/formation HBP.", cell_regular)]
    ]
    t_find = Table(findings_data, colWidths=[120, 130, 70, 400])
    t_find.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1F4E78')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#1F4E78')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D9D9D9')),
        ('TOPPADDING', (0,0), (-1,-1), 1.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
    ]))
    story.append(t_find)
    story.append(Spacer(1, 4))
    
    story.append(Paragraph("2. Top Curative Actions Required Prior to Transaction Execution", section_heading))
    curative_data = [
        [Paragraph("Priority", cell_bold), Paragraph("Target Instrument / Source", cell_bold), Paragraph("Defect / Gap Addressed", cell_bold), Paragraph("Required Action & Deliverable", cell_bold)],
        [Paragraph("P0 — CRITICAL", cell_warning), Paragraph("Bk 2434/Pg 751 (Teocalli Assignment)", cell_bold), Paragraph("Potential total divestiture of Diversified Section 32 interest.", cell_regular), Paragraph("Order complete recorded instrument and legal exhibit from Beckham County clerk.", cell_regular)],
        [Paragraph("P0 — CRITICAL", cell_warning), Paragraph("Bk 1697/Pg 236 Exhibit A (Staghorn/CHK)", cell_bold), Paragraph("Missing base lease crosswalk to modern Chesapeake leasehold.", cell_regular), Paragraph("Retrieve complete unredacted Exhibit A schedule.", cell_regular)],
        [Paragraph("P1 — HIGH", cell_bold), Paragraph("Beckham County Index Logical Page 48", cell_bold), Paragraph("1,981-entry index reconciliation blocked; sequence gap.", cell_regular), Paragraph("Obtain certified index copy of missing Page 48 and resolve disordered Page 54.", cell_regular)],
        [Paragraph("P1 — HIGH", cell_bold), Paragraph("Crook Probates (83/259 & 845/150-157)", cell_bold), Paragraph("Tract 1 mineral heir vesting incomplete (105 NMA affected).", cell_regular), Paragraph("Examine complete court decrees and probate packets in Beckham County District Court.", cell_regular)],
        [Paragraph("P2 — MEDIUM", cell_bold), Paragraph("Bk 2340/403 & 2340/490 Schedules", cell_bold), Paragraph("Tapstone and KL CHK property schedules missing.", cell_regular), Paragraph("Acquire underlying bankruptcy/restructuring conveyance exhibits.", cell_regular)]
    ]
    t_cur = Table(curative_data, colWidths=[70, 140, 180, 330])
    t_cur.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#595959')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#595959')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D9D9D9')),
        ('BACKGROUND', (0,1), (0,2), colors.HexColor('#FFF2CC')),
        ('TOPPADDING', (0,0), (-1,-1), 1.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
    ]))
    story.append(t_cur)
    
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Boss Review PDF generated at: {output_path}")

if __name__ == '__main__':
    create_full_internal_pdf('/workspace/SECTION32_GEMINI37_FULL_INTERNAL_20260830.pdf')
    create_boss_review_pdf('/workspace/SECTION32_GEMINI37_BOSS_REVIEW_20260830.pdf')
