from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase.pdfmetrics import stringWidth
from pathlib import Path

OUT=Path(__file__).resolve().parent/'slides.pdf'
W,H=landscape(letter)
NAVY=HexColor('#102A43'); BLUE=HexColor('#176B87'); TEAL=HexColor('#2A9D8F'); GOLD=HexColor('#E9A23B'); RED=HexColor('#C44536'); PALE=HexColor('#F3F7FA'); MUTED=HexColor('#526777'); INK=HexColor('#172B3A')
c=canvas.Canvas(str(OUT),pagesize=(W,H))
c.setTitle('Indus Weave Textiles | Overtime CFO Briefing')

def base(num,title,sub=None):
    c.setFillColor(PALE); c.rect(0,0,W,H,fill=1,stroke=0)
    c.setFillColor(NAVY); c.rect(0,H-82,W,82,fill=1,stroke=0)
    c.setFillColor(white); c.setFont('Helvetica-Bold',23); c.drawString(42,H-48,title)
    if sub:
        c.setFillColor(HexColor('#D4E3EC')); c.setFont('Helvetica',10.5); c.drawString(44,H-68,sub)
    c.setFillColor(MUTED); c.setFont('Helvetica',8); c.drawString(42,20,'INDUS WEAVE TEXTILES  |  SYNTHETIC CASE DATA  |  APR-SEP 2026')
    c.drawRightString(W-40,20,f'{num} / 5')

def wrap(text,x,y,width,font='Helvetica',size=12,leading=17,color=INK):
    c.setFillColor(color); c.setFont(font,size)
    words=text.split(); line=''; yy=y
    for word in words:
        test=(line+' '+word).strip()
        if stringWidth(test,font,size)>width and line:
            c.drawString(x,yy,line); yy-=leading; line=word
        else: line=test
    if line: c.drawString(x,yy,line); yy-=leading
    return yy

def card(x,y,w,h,label,value,detail,color=BLUE):
    c.setFillColor(white); c.roundRect(x,y,w,h,10,fill=1,stroke=0)
    c.setFillColor(color); c.roundRect(x,y+h-6,w,6,3,fill=1,stroke=0)
    c.setFillColor(MUTED); c.setFont('Helvetica-Bold',9); c.drawString(x+16,y+h-28,label.upper())
    c.setFillColor(INK); c.setFont('Helvetica-Bold',24); c.drawString(x+16,y+h-62,value)
    c.setFillColor(MUTED); c.setFont('Helvetica',9); c.drawString(x+16,y+16,detail)

def bullet(text,x,y,w,color=BLUE):
    c.setFillColor(color); c.circle(x+4,y-4,3,fill=1,stroke=0)
    return wrap(text,x+17,y,w-17,size=11,leading=16)

# Slide 1
base(1,'The overtime bill is rising','The punch record alone does not explain the increase.')
c.setFillColor(TEAL); c.setFont('Helvetica-Bold',12); c.drawString(62,333,'THE SIX-MONTH SIGNAL')
c.setFont('Helvetica-Bold',44); c.drawString(60,267,'+23.5%')
c.setFillColor(MUTED); c.setFont('Helvetica',13); c.drawString(62,241,'overtime earnings, April to September')
c.setStrokeColor(HexColor('#AFC5CE')); c.setLineWidth(1); c.line(62,218,324,218)
c.setFillColor(INK); c.setFont('Helvetica-Bold',14); c.drawString(62,187,'Punch overtime fell')
c.setFillColor(RED); c.setFont('Helvetica-Bold',30); c.drawString(62,145,'-23.8%')
c.setFillColor(MUTED); c.setFont('Helvetica',10); c.drawString(62,122,'Corrected punches vs payroll overtime units')
wrap("Indus Weave's HR, attendance, overtime approvals, and payroll exports tell different stories. This review reconciles them into a daily attendance model and compares punch-computed overtime with what was approved and paid.",370,334,370,size=15,leading=23)
c.setFillColor(BLUE); c.setFont('Helvetica-Bold',10); c.drawString(370,188,'DECISION FOR THE CFO')
wrap('Introduce a monthly exception review before payroll close, then investigate the departments with the largest approval-to-punch gaps.',370,166,340,size=13,leading=20)
c.showPage()

# Slide 2
base(2,'We rebuilt the trail from source to payroll','Every correction is in code; original exports remain unchanged.')
steps=[('01','Raw exports','12 files | 345k punches'),('02','Clean + reconcile','device mapping | dates | duplicates'),('03','Daily attendance','rosters | shifts | leave | holidays'),('04','Warehouse + SQL','10 business answers | DQ checks')]
for i,(n,t,d) in enumerate(steps):
    x=44+i*183
    c.setFillColor(TEAL if i<3 else BLUE); c.setFont('Helvetica-Bold',12); c.drawString(x+5,330,n)
    c.setFillColor(INK); c.setFont('Helvetica-Bold',11); c.drawString(x+18,300,t)
    wrap(d,x+18,282,130,size=8.7,leading=12,color=MUTED)
    if i<3:
        c.setStrokeColor(HexColor('#A7BDCA')); c.setLineWidth(2); c.line(x+162,306,x+178,306)
c.setStrokeColor(HexColor('#AFC5CE')); c.line(278,108,278,211); c.line(524,108,524,211)
c.setFillColor(MUTED); c.setFont('Helvetica-Bold',9); c.drawString(54,190,'ATTENDANCE ROWS')
c.setFillColor(INK); c.setFont('Helvetica-Bold',26); c.drawString(54,151,'217,584')
c.setFillColor(MUTED); c.setFont('Helvetica',9); c.drawString(54,125,'1,266 deduplicated employees')
c.setFillColor(MUTED); c.setFont('Helvetica-Bold',9); c.drawString(301,190,'UNMAPPED PUNCHES')
c.setFillColor(INK); c.setFont('Helvetica-Bold',26); c.drawString(301,151,'6,962')
c.setFillColor(MUTED); c.setFont('Helvetica',9); c.drawString(301,125,'kept with a rejection reason')
c.setFillColor(MUTED); c.setFont('Helvetica-Bold',9); c.drawString(547,190,'DEVICE CLOCK CORRECTION')
c.setFillColor(INK); c.setFont('Helvetica-Bold',26); c.drawString(547,151,'-60 min')
c.setFillColor(MUTED); c.setFont('Helvetica',9); c.drawString(547,125,'DEV-SITE-01 clock was +60 min')
c.setFillColor(MUTED); c.setFont('Helvetica',9); c.drawString(45,75,'Quality checks passed: raw load counts | keys | status values | referential lookups | reconciliation | SCD2 ranges')
c.showPage()

# Slide 3
base(3,'Paid overtime grew as recorded overtime fell','Monthly overtime hours from corrected attendance and payroll units.')
months=['Apr','May','Jun','Jul','Aug','Sep']; paid=[5525.5,5806.5,5889,6249,6513,6418.5]; worked=[7829.5,8990,7711.5,6228,6274.5,5963.5]
chart_x,chart_y,chart_w,chart_h=82,118,620,246
maxv=10000
for tick in [0,2500,5000,7500]:
    yy=chart_y+chart_h*tick/maxv
    c.setStrokeColor(HexColor('#DDE6EC')); c.setLineWidth(.6); c.line(chart_x,yy,chart_x+chart_w,yy)
    c.setFillColor(MUTED); c.setFont('Helvetica',8); c.drawRightString(chart_x-10,yy-3,str(tick))
for i,m in enumerate(months):
    gx=chart_x+35+i*98
    for val,dx,col in [(worked[i],0,BLUE),(paid[i],32,GOLD)]:
        bh=chart_h*val/maxv
        c.setFillColor(col); c.roundRect(gx+dx,chart_y,25,bh,4,fill=1,stroke=0)
    c.setFillColor(MUTED); c.setFont('Helvetica',9); c.drawCentredString(gx+28,chart_y-18,m)
c.setFillColor(BLUE); c.rect(532,390,11,11,fill=1,stroke=0); c.setFillColor(INK); c.setFont('Helvetica',9); c.drawString(549,392,'Punch-computed')
c.setFillColor(GOLD); c.rect(640,390,11,11,fill=1,stroke=0); c.setFillColor(INK); c.drawString(657,392,'Paid')
c.setFillColor(INK); c.setFont('Helvetica-Bold',11); c.drawString(82,78,'Overtime earnings: PKR 2.81m to PKR 3.48m  |  +23.5%')
wrap('Punch-computed overtime dropped 23.8% from April to September, while paid overtime hours rose 16.2%. The gap widened in the final three months.',82,58,620,size=10.5,leading=14,color=MUTED)
c.showPage()

# Slide 4
base(4,'Stitching is the clearest place to start','Six-month total: 7,659 paid hours vs 4,830 punch-computed hours.')
c.setStrokeColor(HexColor('#AFC5CE')); c.line(286,267,286,371); c.line(528,267,528,371)
c.setFillColor(MUTED); c.setFont('Helvetica-Bold',9); c.drawString(64,348,'PUNCH-COMPUTED')
c.setFillColor(INK); c.setFont('Helvetica-Bold',26); c.drawString(64,310,'4,830 h')
c.setFillColor(MUTED); c.setFont('Helvetica',9); c.drawString(64,285,'after clock and punch corrections')
c.setFillColor(MUTED); c.setFont('Helvetica-Bold',9); c.drawString(310,348,'APPROVED + PAID')
c.setFillColor(INK); c.setFont('Helvetica-Bold',26); c.drawString(310,310,'7,659 h')
c.setFillColor(MUTED); c.setFont('Helvetica',9); c.drawString(310,285,'approval hours equal payroll units')
c.setFillColor(MUTED); c.setFont('Helvetica-Bold',9); c.drawString(552,348,'THE GAP')
c.setFillColor(RED); c.setFont('Helvetica-Bold',26); c.drawString(552,310,'2,829 h')
c.setFillColor(MUTED); c.setFont('Helvetica',9); c.drawString(552,285,'paid hours are 58.6% higher')
c.setFillColor(INK); c.setFont('Helvetica-Bold',12); c.drawString(68,228,'What to check in Stitching')
y=200
for txt in ['Match approved requests to corrected punch pairs and the rostered shift end.','Look for recurring requests, approvals that exceed observed work, and staffing patterns.','Five Stitching department-months exceed the 15% threshold; the gap reaches 141.3% in September.']:
    y=bullet(txt,70,y,640,RED if '141.3%' in txt else BLUE)-8
c.showPage()

# Slide 5
base(5,'Put a reconciliation gate before payroll close','A practical response that preserves operations and improves trust in the numbers.')
actions=[('1','Reconcile monthly','Compare computed, approved, and paid overtime by plant and department.'),('2','Escalate exceptions','Require a reason and secondary approval when paid exceeds computed by >15%.'),('3','Review Stitching first','Sample requests and punch pairs, then check staffing and shift coverage.'),('4','Track the trend','Report hours, PKR, exception count, and resolution each month.')]
for i,(n,title,desc) in enumerate(actions):
    y=331-i*64
    c.setFillColor(TEAL if i<3 else BLUE); c.setFont('Helvetica-Bold',14); c.drawString(66,y-4,n)
    c.setFillColor(INK); c.setFont('Helvetica-Bold',13); c.drawString(100,y+3,title)
    wrap(desc,270,y+3,445,size=10.5,leading=14,color=MUTED)
c.setStrokeColor(HexColor('#AFC5CE')); c.line(46,124,746,124)
c.setFillColor(INK); c.setFont('Helvetica-Bold',12); c.drawString(66,99,'Recommended next step: pilot the exception gate with Stitching in the next payroll cycle.')
c.setFillColor(MUTED); c.setFont('Helvetica',9); c.drawString(66,80,'All figures are synthetic case-study outputs; confirm the assumptions during Q&A.')
c.showPage(); c.save()
print(OUT)

