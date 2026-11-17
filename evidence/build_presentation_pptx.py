"""Build the 10-slide, editable project presentation using python-pptx."""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
OUT = ROOT / "Hotel_Overbooking_Optimization_Presentation_Readable.pptx"
W, H = 13.333, 7.5
COL = {
    "bg":"F7F9FC", "ink":"102033", "muted":"5E6B7D", "blue":"255B8E",
    "teal":"0C8F88", "gold":"D8941A", "red":"B8483D", "line":"D9E1EA",
    "white":"FFFFFF", "pale":"EAF3F5", "palegold":"FFF3DB", "soft":"EEF2F7"
}

def rgb(name):
    h=COL.get(name,name).lstrip("#")
    return RGBColor(int(h[0:2],16),int(h[2:4],16),int(h[4:6],16))

prs=Presentation()
prs.slide_width=Inches(W); prs.slide_height=Inches(H)
blank=prs.slide_layouts[6]

def rect(slide,x,y,w,h,color,rounded=False):
    shape=slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
                                 Inches(x),Inches(y),Inches(w),Inches(h))
    shape.fill.solid(); shape.fill.fore_color.rgb=rgb(color)
    shape.line.fill.background()
    if rounded:
        try: shape.adjustments[0]=0.08
        except Exception: pass
    return shape

def line(slide,x1,y1,x2,y2,color="line",width=1):
    shape=slide.shapes.add_connector(1,Inches(x1),Inches(y1),Inches(x2),Inches(y2))
    shape.line.color.rgb=rgb(color); shape.line.width=Pt(width)
    return shape

def text(slide,txt,x,y,w,h,size=14,color="ink",bold=False,font="Aptos",align="left",valign="mid"):
    sh=slide.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h))
    tf=sh.text_frame; tf.clear(); tf.word_wrap=True
    tf.margin_left=Pt(0); tf.margin_right=Pt(0); tf.margin_top=Pt(0); tf.margin_bottom=Pt(0)
    tf.vertical_anchor={"mid":MSO_ANCHOR.MIDDLE,"top":MSO_ANCHOR.TOP,"bottom":MSO_ANCHOR.BOTTOM}[valign]
    for i,part in enumerate(str(txt).split("\n")):
        p=tf.paragraphs[0] if i==0 else tf.add_paragraph()
        p.alignment={"left":PP_ALIGN.LEFT,"center":PP_ALIGN.CENTER,"right":PP_ALIGN.RIGHT}[align]
        p.space_before=Pt(0); p.space_after=Pt(0)
        r=p.add_run(); r.text=part
        r.font.name=font; r.font.size=Pt(size); r.font.bold=bold; r.font.color.rgb=rgb(color)
    return sh

def slide_base(title,owner,source,n):
    s=prs.slides.add_slide(blank)
    fill=s.background.fill; fill.solid(); fill.fore_color.rgb=rgb("bg")
    text(s,"HOTEL OVERBOOKING  •  BUILD 2",.58,.30,8,.22,10,"teal",True)
    text(s,title,.58,.66,12.15,.62,25,"ink",True)
    line(s,.58,1.38,12.75,1.38)
    line(s,.58,7.05,12.75,7.05,width=.8)
    text(s,"OWNER  "+owner,.58,7.13,3.25,.20,8.5,"muted",True)
    text(s,source,3.85,7.13,8.85,.20,9,"muted")
    text(s,f"{n:02d}",12.2,.31,.55,.20,9,"muted",True,align="right")
    return s

def table(slide,x,y,widths,rows,row_h,header=False,font_size=11,highlight_row=None):
    for ri,row in enumerate(rows):
        yy=y+ri*row_h
        if header and ri==0:
            bg="ink"; fg="white"; isbold=True
        else:
            data_i=ri-1 if header else ri
            bg=("pale" if data_i==highlight_row else ("white" if ri%2==0 else "bg"))
            fg="ink"; isbold=(data_i==highlight_row)
        xx=x
        for ci,(val,cw) in enumerate(zip(row,widths)):
            rect(slide,xx,yy,cw,row_h,bg)
            clr=fg
            if not header and highlight_row is not None and data_i==highlight_row and ci==len(row)-1: clr="teal"
            text(slide,str(val),xx+.10,yy+.02,cw-.20,row_h-.04,font_size,clr,isbold,
                 align="left" if ci==0 else "right")
            xx+=cw

# 1 — answer and 14-night historical demonstration.
s=slide_base("What should the revenue manager do tomorrow night?","Sagar • Client Lead",
             "Evidence: src/nightly.py • evidence/presentation_nightly_recommendations.csv",1)
text(s,"Use the frozen model to estimate cancellations by hotel-night, then subtract the choose-period buffer.",.68,1.62,11.95,.38,15)
text(s,"HISTORICAL DEMONSTRATION  ·  18–31 AUG 2017  ·  28 HOTEL-NIGHT ROWS",.70,2.11,11.8,.23,9.5,"muted",True)
with (EVIDENCE/"presentation_nightly_recommendations.csv").open(newline="",encoding="utf-8") as f:
    raw=list(csv.DictReader(f))
dates=sorted({r["arrival_date"] for r in raw})
vals={d:{"City":"—","Resort":"—"} for d in dates}
for r in raw: vals[r["arrival_date"]]["City" if r["hotel"]=="City Hotel" else "Resort"]=str(int(float(r["oversell"])))
rows=[["ARRIVAL NIGHT","CITY HOTEL","RESORT HOTEL"]]
for d in dates: rows.append([date.fromisoformat(d).strftime("%d %b"),vals[d]["City"],vals[d]["Resort"]])
table(s,.72,2.48,[4.60,3.25,4.03],rows,.285,header=True,font_size=10.5)
text(s,"The supplied file contains final historical bookings; this demonstrates the workflow, not a live forward forecast.",.72,6.82,11.9,.16,8.3,"muted")

# 2 — decision and loss function.
s=slide_base("What is decided, and what does a wrong call cost?","Sagar • Client Lead",
             "Evidence: Client Brief • docs/CHARTER.md • src/contract.py",2)
text(s,"DECISION UNIT",.78,1.78,2.8,.25,10,"teal",True)
text(s,"One hotel × one arrival night",.78,2.13,5.5,.65,24,"ink",True)
text(s,"Choose how many rooms to sell beyond capacity.",.78,2.88,5.5,.42,14,"muted")
line(s,6.55,1.75,6.55,5.85)
text(s,"COST OF AN EMPTY ROOM",7.05,1.78,4.8,.25,10,"blue",True)
text(s,"Booked ADR × nights",7.05,2.12,5,.45,19,"ink",True)
text(s,"COST OF WALKING A GUEST",7.05,3.18,4.8,.25,10,"red",True)
text(s,"€300 per guest",7.05,3.52,4.8,.48,21,"ink",True)
rect(s,.78,4.22,11.75,1.15,"pale",True)
text(s,"GUARDRAIL",1.05,4.47,1.6,.22,10,"teal",True)
text(s,"≤ 10 walks per 1,000 arrivals",2.75,4.37,6.8,.42,21,"ink",True)
text(s,"A cheaper rule is rejected if it breaks this ceiling.",2.75,4.84,7.8,.28,12,"muted")
text(s,"North star: minimize empty-room and walking costs, subject to the walk ceiling.",.8,5.76,11.7,.48,15,"ink",True)

# 3 — checked brief number plus segment rate-versus-volume view.
s=slide_base("What did the data say that the brief did not?","Sagar + Nitish • Client + Data Leads",
             "Evidence: notebooks/01_Data_profiling.ipynb • docs/DECISIONS.md • cleaned segment summary",3)
text(s,"CANCELLATION RATE",.78,1.72,3.5,.22,9.5,"muted",True)
text(s,"37.0%",.78,2.00,3.2,.75,37,"blue",True)
text(s,"observed in raw data",.82,2.78,3.4,.25,12,"muted")
text(s,"Brief estimate: about 1 in 4",.82,3.12,4.2,.30,13)
text(s,"Cleaning removed 827 of 119,390 rows; 118,563 remain.",.82,3.72,4.05,.68,14,"ink",True)
text(s,"RATE BY PERIOD",.82,4.74,3.2,.22,9.5,"muted",True)
text(s,"Train 36.0%  →  Choose 37.1%  →  Proof 38.8%",.82,5.07,4.45,.36,12,"ink",True)
text(s,"The rise makes a chronological holdout matter.",.82,5.53,4.35,.42,11,"muted")
line(s,5.22,1.72,5.22,6.48)
text(s,"TRAVEL-PARTNER VIEW  ·  RATE AGAINST VOLUME",5.62,1.72,6.8,.22,9.5,"muted",True)
segments=[("Online TA","56,129",36.92),("Offline TA / TO","24,048",34.51),("Groups","19,758",61.21),("Direct","12,449",15.50),("Corporate","5,231",18.91)]
for i,(name,count,rate) in enumerate(segments):
    y=2.14+i*.79
    text(s,name,5.62,y,2.15,.23,12,"ink",True)
    text(s,"n="+count,5.62,y+.28,1.75,.20,9,"muted")
    rect(s,7.78,y+.08,3.35,.22,"soft")
    rect(s,7.78,y+.08,max(.08,3.35*rate/70),.22,"gold" if name=="Groups" else "teal")
    text(s,f"{rate:.1f}%",11.30,y+.02,.82,.28,12,"ink",True,align="right")
text(s,"Groups: highest rate among large segments. Online TA: largest volume. Association is not causation.",5.62,6.20,6.65,.42,10.5,"muted")

# 4 — nine inputs and timing AUC evidence.
s=slide_base("Which columns were safe to keep, and what did timing change?","Nitish • Data Lead",
             "Evidence: docs/COLUMNS.md • evidence/feature_timing_eda.png • evidence/feature_timing_eda.md",4)
text(s,"APPROVED MODEL INPUTS",.72,1.62,4.55,.22,10,"teal",True)
text(s,"9 Bin 1 features",.72,1.94,4.6,.45,22,"ink",True)
feature_names=["hotel","market_segment","distribution_channel","is_repeated_guest","previous_cancellations",
               "previous_bookings_not_canceled","agent","company","customer_type"]
for i,name in enumerate(feature_names): text(s,name,.80,2.53+i*.33,4.5,.25,11.1,"ink",False,"Cascadia Code")
rect(s,.72,5.78,4.65,.72,"palegold",True)
text(s,"Higher AUC is not enough if a field was unavailable at booking.",.92,5.97,4.22,.36,11.2,"ink",True)
text(s,"CHRONOLOGICAL PROOF AUC",5.62,1.62,6.8,.24,10,"muted",True)
text(s,"Same frozen XGBoost settings  ·  higher ranks cancellations better",5.62,1.92,6.8,.27,11,"ink")
plot_x=7.62; plot_w=3.42; plot_top=2.42; plot_bottom=4.64
for tick,label in enumerate(["0.70","0.75","0.80","0.85"]):
    xx=plot_x+plot_w*tick/3
    line(s,xx,plot_top-.10,xx,plot_bottom,"line",.7)
    text(s,label,xx-.28,plot_bottom+.08,.56,.22,9.5,"muted",align="center")
auc_rows=[("9 · Bin 1",.7543,"blue"),("16 · +7 Bin 2",.7833,"gold"),("17 · +country",.8315,"red")]
for i,(label,value,color) in enumerate(auc_rows):
    yy=2.55+i*.72
    text(s,label,5.62,yy,1.82,.28,11.5,"ink",True)
    width=plot_w*(value-.70)/.15
    rect(s,plot_x,yy+.035,width,.22,color)
    text(s,f"{value:.4f}",11.25,yy-.005,1.15,.30,14,color,True)
text(s,"+7 Bin 2 fields   Δ AUC +0.0290   ·   95% CI +0.0264 to +0.0322",5.62,4.98,6.8,.26,10.2,"ink",True)
text(s,"+country (Bin 3)   Δ AUC +0.0482   ·   95% CI +0.0437 to +0.0523",5.62,5.35,6.8,.26,10.2,"ink",True)
text(s,"Total 17 vs 9: +0.0772   ·   95% CI +0.0731 to +0.0817",5.62,5.72,6.8,.26,10.2,"teal",True)
text(s,"Run C: 9-feature random split AUC 0.8046; not a proof result. Historical 17 adds amendable fields and after-the-fact country. The CSV is not a booking-day snapshot.",5.62,6.10,6.85,.55,9.5,"muted")

# 5 — proof-period results.
s=slide_base("Which method won on the proof period?","Devyanshi • Model Lead",
             "Evidence: docs/PRD.md • docs/DECISIONS.md • recorded backtest, 17 Nov 2026",5)
text(s,"FROZEN PROOF RESULTS  ·  JAN–AUG 2017  ·  486 HOTEL-NIGHTS",.78,1.70,9,.24,10,"muted",True)
heads=["RULE","EMPTY ROOMS","WALKS","WALKS / 1,000","COST"]
data=[["Client flat rule","8,141","154","6.21","€3,929,135"],["XGBoost · 9 features · buffer 4","5,607","57","2.30","€2,722,668"]]
table(s,.78,2.14,[4.05,1.80,1.70,1.88,2.22],[heads]+data,.64,header=True,font_size=10.5,highlight_row=1)
text(s,"€1.206M",.84,4.31,3.65,.77,34,"teal",True)
text(s,"lower proof cost vs flat rule",.87,5.08,4.8,.28,13,"ink",True)
text(s,"Walk ceiling: 10 / 1,000",6.30,4.43,4,.38,17,"ink",True)
text(s,"Both met it on proof. The model had 97 fewer walks and 2,534 fewer empty rooms.",6.30,4.95,5.15,.76,13,"muted")
text(s,"Filtered population: 118,563 prepared bookings, not all 119,390 source rows.",.84,6.18,11.4,.33,10.5,"muted")

# 6 — choice and sensitivity.
s=slide_base("What would make us change the chosen buffer?","Devyanshi • Model Lead",
             "Evidence: docs/DECISIONS.md • docs/PRD.md",6)
text(s,"CHOOSE PERIOD  ·  JUL–DEC 2016",.82,1.78,5.2,.24,10,"muted",True)
text(s,"k = 4 rooms",.82,2.10,5,.66,34,"blue",True)
text(s,"Chosen on choose, then frozen before proof.",.84,2.89,5.2,.34,14)
line(s,6.38,1.78,6.38,5.95)
text(s,"9.82",.82,3.64,2,.65,32,"teal",True)
text(s,"walks / 1,000 on choose",2.64,3.85,3.35,.30,13,"muted")
text(s,"≤ 10",.82,4.48,2,.52,25,"ink",True)
text(s,"client ceiling",2.64,4.59,3.1,.30,13,"muted")
text(s,"WHAT WOULD FLIP IT?",6.94,1.82,4.7,.25,10,"gold",True)
text(s,"If walking a guest costs more than €300, re-select the buffer on choose.",6.94,2.22,5.05,.96,21,"ink",True)
text(s,"Freeze that choice and evaluate once on a future holdout. Do not tune from proof.",6.94,3.43,4.9,.77,13,"muted")
rect(s,6.94,4.64,5.05,.83,"palegold",True)
text(s,"The €1,000 case is a sensitivity to test, not a measured result.",7.17,4.87,4.58,.37,12,"ink",True)

# 7 — working command and pipeline.
s=slide_base("Does the MVP run without retraining?","Sharad • Build Lead",
             "Evidence: src/nightly.py • models/chosen_policy.joblib • evidence/presentation_nightly_recommendations.csv",7)
text(s,"ONE COMMAND",.78,1.67,2.2,.22,9.5,"teal",True)
rect(s,.78,2,11.8,.65,"ink",True)
text(s,"python src/nightly.py --from 2017-08-18 --nights 14",1,2.20,11.3,.25,15,"white",True,"Cascadia Code")
steps=[("Bookings CSV","historical input","blue"),("Prepare","approved filters","teal"),("Frozen model","9 inputs + k=4","blue"),("Hotel-night","sum probabilities","teal"),("CSV table","28 rows","gold")]
for i,(title,desc,color) in enumerate(steps):
    x=.82+i*2.43
    rect(s,x,3.34,2.10,1.05,"white",True); rect(s,x,3.34,2.10,.08,color)
    text(s,title,x+.12,3.58,1.90,.27,13,"ink",True); text(s,desc,x+.12,3.98,1.90,.24,10.5,"muted")
    if i<4:text(s,"→",x+2.14,3.70,.38,.28,18,"muted",True)
text(s,"Verified: 28 recommendations printed and written. The saved predictor and buffer load; nightly.py does not train.",.84,4.82,11.7,.60,14,"ink",True)
text(s,"Integration limit: historical preparation still requires is_canceled. A live target-free input path is a production task.",.84,5.75,11.7,.55,12,"red",True)

# 8 — actual integration checks, not invented grill-log excerpts.
s=slide_base("What must be true before anyone trusts the output?","Sharad • Build Lead",
             "Evidence: docs/PRD.md • src/nightly.py • docs/COLUMNS.md",8)
checks=[("01","Are these values available at booking?","Nine Bin 1 fields are used. The CSV lacks original booking-time snapshots.","teal"),
        ("02","Does the live command leak the outcome?","is_canceled is not a model input. A target-free preparation path is still needed.","blue"),
        ("03","Does the demo prove a future forecast?","No. It replays final historical bookings; it proves the pipeline and output format.","gold")]
for i,(number,question,answer,color) in enumerate(checks):
    y=1.83+i*1.48
    text(s,number,.84,y,.58,.42,20,color,True); text(s,question,1.65,y,10.7,.36,17,"ink",True)
    text(s,answer,1.65,y+.46,10.8,.52,12.5,"muted"); line(s,.84,y+1.20,12.38,y+1.20,width=.7)
text(s,"Grill logs are blank; these are integration checks, not claimed chat-log questions.",.84,6.40,11.6,.28,10,"red",True)

# 9 — scope boundaries.
s=slide_base("What is outside the MVP?","Sharad • Build Lead",
             "Evidence: docs/PRD.md • docs/ROADMAP.md • team scope decision",9)
outs=[("LIVE PMS","No hotel-system export, authentication, audit trail or override workflow.","blue"),
      ("ROOM CAPACITY","No capacity field; recommendations are extra rooms to sell, not inventory caps.","gold"),
      ("LIVE SNAPSHOTS","No point-in-time, target-free feed; historical values may include later amendments.","red"),
      ("AI BENCHMARK","Excluded from team scope; it is not an MVP dependency.","teal")]
for i,(label,desc,color) in enumerate(outs):
    y=1.84+i*1.12
    rect(s,.85,y,.13,.71,color); text(s,label,1.17,y,2.85,.25,10,color,True)
    text(s,desc,4,y-.02,8.2,.65,15); line(s,1.17,y+.88,12.35,y+.88,width=.65)
text(s,"Full-night recommendations need capacity and a live booking snapshot. Neither is in this dataset.",.85,6.48,11.4,.30,11,"muted",True)

# 10 — next steps.
s=slide_base("What should we do next?","Sagar • Client Lead",
             "Evidence: docs/ROADMAP.md • hours are planning estimates, not measured effort",10)
heads=["WHEN","DELIVERABLE","ACCEPTANCE TARGET","OWNER","PLAN"]
xs=[.82,2,6.32,9.2,11.15]; ws=[1,4.1,2.7,1.8,1.25]
for i,label in enumerate(heads): text(s,label,xs[i],1.79,ws[i],.23,9,"muted",True)
weeks=[("WEEK 7","Build a timestamped, target-free booking snapshot","0 Bin 2 / Bin 3 inputs","Data + Build","16h","teal"),
       ("WEEK 8","Shadow-run both hotels against the flat rule","≤ 10 walks / 1,000","Model + Client","20h","blue"),
       ("WEEK 9","Add PMS import, override log, monitoring and rollback","Alert before ceiling breach","Build + Model","24h","gold")]
for i,(week,work,target,owner,hours,color) in enumerate(weeks):
    y=2.25+i*1.21
    rect(s,.82,y,11.72,1.03,"white",True); rect(s,.82,y,.09,1.03,color)
    text(s,week,1.05,y+.32,.82,.24,10,color,True); text(s,work,2,y+.18,4.04,.66,13,"ink",True)
    text(s,target,6.32,y+.28,2.68,.45,11.5,"ink",True); text(s,owner,9.2,y+.28,1.8,.45,10.5,"muted")
    text(s,hours,11.15,y+.28,1.05,.45,11,"ink",True)
rect(s,.84,6.14,11.70,.57,"pale",True)
text(s,"Keep the 9-feature prototype. Gate a shadow pilot on point-in-time data and room capacity.",1.05,6.30,11.25,.27,12,"ink",True)

prs.save(OUT)
print(f"Created {OUT} ({len(prs.slides)} slides, {OUT.stat().st_size:,} bytes)")
