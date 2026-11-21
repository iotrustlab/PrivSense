#!/usr/bin/env python3
"""Render the conceptual PrivSense explainer using Pillow only.

Run from any directory: python3 docs/animation/generate.py
The renderer samples 300 frames at 100 ms: exactly 30 seconds per loop.
The GIF encoder may combine identical adjacent samples, preserving duration.
All waveforms, binary strings, and diagrams are synthetic illustrations.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH, HEIGHT = 960, 600
FPS = 10
DURATION = 30
SCALE = 2
OUT = Path(__file__).resolve().parents[1] / "assets"
BG = "#081321"
PANEL = "#102139"
EDGE = "#223c58"
WHITE = "#f1f6fe"
MUTED = "#90a8c5"
CYAN = "#57e0cf"
BLUE = "#7dcfff"
PURPLE = "#b9a2ff"
PEACH = "#ffd4a2"
PHASES = ["SENSORS", "CHANNEL", "AGENT", "INFERENCE", "EVIDENCE", "NEXT"]


def font(size: int, bold: bool = False):
    # Pillow resolves this portable font name; no workstation paths are stored.
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(name, round(size * SCALE))


FONTS = {(size, bold): font(size, bold) for size in [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 24, 25, 26, 28, 30, 32, 34, 38, 40, 42] for bold in [False, True]}


class Canvas:
    def __init__(self):
        self.image = Image.new("RGB", (WIDTH * SCALE, HEIGHT * SCALE), BG)
        self.d = ImageDraw.Draw(self.image)

    def rect(self, box, fill=PANEL, outline=None, radius=16, width=1):
        self.d.rounded_rectangle(tuple(round(x * SCALE) for x in box), radius=radius * SCALE, fill=fill, outline=outline, width=width * SCALE)

    def line(self, points, fill=CYAN, width=2):
        self.d.line([(round(x * SCALE), round(y * SCALE)) for x, y in points], fill=fill, width=width * SCALE, joint="curve")

    def circle(self, x, y, radius, fill, outline=None, width=1):
        self.d.ellipse(tuple(round(v * SCALE) for v in (x-radius, y-radius, x+radius, y+radius)), fill=fill, outline=outline, width=width*SCALE)

    def text(self, xy, value, size=20, fill=WHITE, bold=False, anchor=None):
        self.d.text(tuple(round(v * SCALE) for v in xy), value, font=FONTS[size, bold], fill=fill, anchor=anchor)

    def arrow(self, x1, y1, x2, y2, fill=CYAN, width=2):
        self.line([(x1,y1),(x2,y2)], fill, width)
        angle = math.atan2(y2-y1,x2-x1)
        back = angle + math.pi
        self.line([(x2+9*math.cos(back-.45), y2+9*math.sin(back-.45)),(x2,y2),(x2+9*math.cos(back+.45),y2+9*math.sin(back+.45))], fill, width)

    def pill(self, x, y, label, color=CYAN):
        length = self.d.textlength(label, font=FONTS[12,True])/SCALE+24
        self.rect((x,y,x+length,y+27), fill=PANEL, outline=EDGE, radius=13)
        self.text((x+12,y+6), label, 12, color, True)

    def wave(self, box, t=0, color=CYAN, kind="imu"):
        x1,y1,x2,y2 = box
        self.line([(x1,(y1+y2)/2),(x2,(y1+y2)/2)], EDGE, 1)
        points = []
        for i in range(round(x2-x1)+1):
            x=i/(x2-x1)
            phase=x*7*math.pi+t*1.3
            if kind == "audio":
                v=math.sin(phase*3.4)*(.2+.7*math.sin(x*math.pi)**2)
            else:
                v=.55*math.sin(phase)+.2*math.sin(phase*2.7)
            points.append((x1+i,(y1+y2)/2-v*(y2-y1)*.45))
        self.line(points,color,2)

    def binary(self, box, t=0, color=CYAN):
        x1,y1,x2,y2 = box
        pattern="000111111000001100011111000000111001100011110000"
        n=24
        offset=int(t*3)%len(pattern)
        step=(x2-x1)/n
        pts=[]
        for i in range(n):
            v=pattern[(i+offset)%len(pattern)] == "1"
            y=y1+8 if v else y2-8
            if i: pts.append((x1+i*step,y))
            pts.extend([(x1+i*step,y),(x1+(i+1)*step,y)])
        self.line(pts,color,3)

    def phone(self,x,y,t=0):
        self.rect((x,y,x+102,y+156), fill=BG, outline=BLUE, radius=17,width=2)
        self.line([(x+37,y+12),(x+65,y+12)], MUTED,2)
        self.wave((x+13,y+42,x+89,y+100),t,BLUE)
        self.circle(x+51,y+138,4,MUTED)

    def agent(self,x,y,color=PURPLE):
        self.rect((x-37,y-29,x+37,y+29),fill=BG,outline=color,radius=14,width=2)
        self.circle(x-13,y-4,4,color)
        self.circle(x+13,y-4,4,color)
        self.line([(x-12,y+13),(x+12,y+13)],color,2)
        self.line([(x,y-29),(x,y-40)],color,2)
        self.circle(x,y-44,4,color)


def frame_base(scene, t, title, subtitle):
    c=Canvas()
    c.rect((40,31,46,61),fill=CYAN,radius=3)
    c.text((60,29),"PRIVSENSE",24,WHITE,True)
    c.pill(684,32,"RESEARCH IN PROGRESS",PEACH)
    title_size = next(size for size in [34,32,30] if FONTS[size,True].getlength(title)/SCALE <= WIDTH-80)
    c.text((40,91),title,title_size,WHITE,True)
    c.text((41,141),subtitle,18,MUTED)
    c.rect((40,185,920,477),outline=EDGE,radius=20)
    c.text((41,497),"GENERAL-PURPOSE AGENTS  /  SENSOR PRIVACY",12,MUTED,True)
    for i,label in enumerate(PHASES):
        x=41+i*149
        c.rect((x,532,x+130,536),fill=EDGE,radius=2)
        if i < scene:
            c.rect((x,532,x+130,536),fill=CYAN,radius=2)
        elif i == scene:
            c.rect((x,532,x+max(3,130*t/5),536),fill=CYAN,radius=2)
        c.text((x,549),label,12,CYAN if i==scene else MUTED,True)
    c.text((917,497),"CONCEPTUAL • SYNTHETIC TRACES",12,MUTED,anchor="ra")
    return c


def sensor_scene(t):
    c=frame_base(0,t,"Everyday sensors capture private context.","Useful measurements can also reveal how people live.")
    # A walking figure, a sensor, and a context card.
    x,y=166,307
    swing=12*math.sin(t*3)
    c.circle(x,y-46,14,BLUE)
    c.line([(x,y-27),(x-8,y+12),(x+18,y+35)],BLUE,5)
    c.line([(x-8,y+12),(x-29,y+43+swing/3)],BLUE,5)
    c.line([(x-3,y-15),(x-29,y+1+swing/3)],BLUE,4)
    c.line([(x-3,y-15),(x+26,y-3-swing/3)],BLUE,4)
    c.text((166,387),"Everyday activity",17,WHITE,True,anchor="mm")
    c.arrow(250,310,312,310,BLUE)
    c.phone(360,227,t)
    c.text((412,410),"Sensor measurements",17,WHITE,True,anchor="mm")
    c.arrow(505,310,567,310,BLUE)
    c.rect((607,238,868,403),fill=BG,outline=EDGE,radius=14)
    c.text((629,259),"CONTEXT IN SIGNALS",13,CYAN,True)
    for i,label in enumerate(["Movement", "Routine", "Environment"]):
        c.circle(635,303+i*32,3,CYAN)
        c.text((649,291+i*32),label,19)
    return c


def channel_scene(t):
    c=frame_base(1,t,"Small outputs can carry hidden structure.","Current pilot: shake / no-shake bits from a restricted sensor interface.")
    c.text((74,214),"LOCAL SENSOR PROCESSING",13,BLUE,True)
    c.wave((75,260,281,331),t,BLUE)
    c.text((74,360),"Raw signal stays local",16,MUTED)
    c.arrow(307,303,359,303)
    c.rect((387,229,875,384),fill=BG,outline=EDGE,radius=14)
    c.text((410,249),"OBSERVABLE BINARY CHANNEL",13,CYAN,True)
    c.binary((412,288,849,342),t)
    c.text((412,353),"0 = no shake     1 = shake",14,MUTED)
    for x,label in [(387,"Duty cycle"),(558,"Transitions"),(735,"Temporal runs")]:
        c.pill(x,408,label,CYAN)
    return c


def agent_scene(t):
    c=frame_base(2,t,"The LLM investigates through bounded tools.","It chooses candidate analyses, reads feedback, and revises a hypothesis.")
    cards=[(75,226,"01", "Observe", "Read channel summaries",BLUE),
           (553,226,"02", "Hypothesize", "Propose a candidate",PURPLE),
           (553,362,"03", "Use tools", "Evaluate on validation",CYAN),
           (75,362,"04", "Revise", "Compare and refine",PEACH)]
    active=min(3,int(t/.95)%4)
    for i,(x,y,n,title,detail,color) in enumerate(cards):
        c.rect((x,y,x+331,y+86),fill=BG,outline=color if i==active else EDGE,radius=12,width=2 if i==active else 1)
        c.text((x+17,y+15),n,14,color,True)
        c.text((x+53,y+11),title,22,WHITE,True)
        c.text((x+53,y+47),detail,15,MUTED)
    c.arrow(423,268,536,268,PURPLE)
    c.arrow(719,323,719,350,CYAN)
    c.arrow(536,404,423,404,PEACH)
    c.arrow(240,351,240,323,BLUE)
    c.agent(479,337)
    return c


def inference_scene(t):
    c=frame_base(3,t,"Freeze a candidate. Evaluate independently.","Keep final test subjects outside the agent's feedback loop.")
    c.rect((72,224,358,435),fill=BG,outline=PURPLE,radius=14)
    c.text((95,246),"FROZEN CANDIDATE",13,PURPLE,True)
    c.text((95,287),"Selected features",20,WHITE,True)
    c.text((95,322),"+ classifier",20,WHITE,True)
    c.line([(95,365),(331,365)],EDGE,1)
    c.text((95,383),"No test feedback to agent",15,MUTED)
    c.arrow(379,329,440,329)
    c.rect((465,224,886,435),fill=BG,outline=EDGE,radius=14)
    c.text((488,246),"HELD-OUT EVALUATION",13,CYAN,True)
    items=[("Activity inference",BLUE),("Uncertainty and failures",PEACH),("Per-subject performance",CYAN)]
    for i,(label,col) in enumerate(items):
        y=294+45*i
        c.circle(495,y+8,4,col)
        c.text((512,y-4),label,19,WHITE,True)
    # A moving marker signals one-way evaluation, not a measured metric.
    c.circle(379+61*((t%1.6)/1.6),329,4,CYAN)
    return c


def evidence_scene(t):
    c=frame_base(4,t,"Measure leakage. Test the agent's value.","The research question needs controlled comparisons and reproducible evidence.")
    panels=[(72,220,"BASELINES", "Is the agent adding value?", BLUE),
            (492,220,"GENERALIZATION", "Does inference transfer?", CYAN),
            (72,347,"ABLATIONS", "Which knowledge matters?", PURPLE),
            (492,347,"PRIVACY AUDIT", "What can the channel reveal?", PEACH)]
    active=min(3,int(t/1.25))
    for i,(x,y,title,line,color) in enumerate(panels):
        c.rect((x,y,x+394,y+100),fill=BG,outline=color if i==active else EDGE,radius=12,width=2 if i==active else 1)
        c.rect((x+18,y+21,x+23,y+79),fill=color,radius=2)
        c.text((x+40,y+18),title,14,color,True)
        c.text((x+40,y+51),line,18,WHITE,True)
    return c


def next_scene(t):
    c=frame_base(5,t,"Next: agentic multimodal side-channel analysis.","Planned: compare multimodal agents, datasets, and observation budgets.")
    for i,(label,col) in enumerate([("Motion / IMU",BLUE),("Video",PURPLE),("Audio",CYAN)]):
        y=220+i*70
        c.rect((72,y,319,y+52),fill=BG,outline=EDGE,radius=10)
        c.circle(94,y+26,4,col)
        c.text((109,y+14),label,18,WHITE,True)
        c.arrow(333,y+26,412,316,col)
    c.agent(475,316)
    c.text((475,386),"Multimodal agent",17,WHITE,True,anchor="mm")
    c.arrow(532,316,589,316)
    c.rect((610,245,885,389),fill=BG,outline=CYAN,radius=14)
    c.text((632,268),"PRIVACY EVIDENCE",14,CYAN,True)
    c.text((632,307),"Discover · quantify",19,WHITE,True)
    c.text((632,341),"explain · reproduce",19,WHITE,True)
    c.text((480,443),"An open research direction. Experiments in progress.",17,PEACH,True,anchor="mm")
    return c


SCENES=[sensor_scene,channel_scene,agent_scene,inference_scene,evidence_scene,next_scene]


def poster():
    c=Canvas()
    c.rect((40,34,46,69),fill=CYAN,radius=3)
    c.text((61,30),"PRIVSENSE",30,WHITE,True)
    c.pill(684,37,"RESEARCH IN PROGRESS",PEACH)
    c.text((40,112),"Agentic Sensor Side-Channel Analysis",38,WHITE,True)
    c.text((41,171),"Can general-purpose agents turn limited sensor outputs",22,MUTED)
    c.text((41,204),"into evidence of privacy leakage?",22,MUTED)
    labels=[("SENSORS","Everyday context",BLUE),("CHANNEL","Restricted outputs",CYAN),("AGENT","Hypothesize + tools",PURPLE),("EVIDENCE","Inference + uncertainty",PEACH)]
    for i,(title,detail,col) in enumerate(labels):
        x=40+i*224
        c.rect((x,287,x+208,456),fill=PANEL,outline=EDGE,radius=15)
        c.text((x+18,307),title,14,col,True)
        if i==0:
            c.wave((x+20,349,x+187,389),0,BLUE)
        elif i==1:
            c.binary((x+20,349,x+187,389),0,CYAN)
        elif i==2:
            c.agent(x+104,371)
        else:
            for j in range(3):
                c.circle(x+27,350+j*18,3,col)
                c.line([(x+42,350+j*18),(x+176-j*16,350+j*18)],col,2)
        c.text((x+104,429),detail,15,WHITE,anchor="mm")
        if i<3:c.arrow(x+212,371,x+221,371,MUTED,1)
    c.text((40,494),"Observe → hypothesize → evaluate → revise → independently test",19,WHITE,True)
    c.text((40,539),"30-second conceptual explainer • Synthetic illustrations • Work in progress",15,MUTED)
    return c.image.resize((WIDTH,HEIGHT),Image.Resampling.LANCZOS)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    poster().save(OUT/"privsense-explainer-poster.png",optimize=True)
    # A single shared adaptive palette avoids flicker between adjacent frames.
    swatches=Image.new("RGB",(WIDTH,HEIGHT*6))
    for i,scene in enumerate(SCENES):
        sample=scene(2.5).image.resize((WIDTH,HEIGHT),Image.Resampling.LANCZOS)
        swatches.paste(sample,(0,i*HEIGHT))
    palette=swatches.quantize(colors=128,method=Image.Quantize.MEDIANCUT)
    frames=[]
    for index in range(FPS*DURATION):
        scene=index//(5*FPS)
        t=(index%(5*FPS))/FPS
        rgb=SCENES[scene](t).image.resize((WIDTH,HEIGHT),Image.Resampling.LANCZOS)
        frames.append(rgb.quantize(palette=palette,dither=Image.Dither.NONE))
    gif=OUT/"privsense-explainer.gif"
    frames[0].save(gif,save_all=True,append_images=frames[1:],duration=100,loop=0,optimize=True,disposal=1)
    with Image.open(gif) as check:
        total=0
        for index in range(check.n_frames):
            check.seek(index)
            total+=check.info["duration"]
        assert total==DURATION*1000,(check.n_frames,total)
        assert check.size==(WIDTH,HEIGHT)
        print(f"Rendered {gif.name}: {check.n_frames} frames, {total/1000:.1f} s, {WIDTH}×{HEIGHT}, {gif.stat().st_size:,} bytes")


if __name__=="__main__":
    main()
