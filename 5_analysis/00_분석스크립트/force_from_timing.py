# -*- coding: utf-8 -*-
"""힘 거동 절의 그래프 3종 생성 — 시편 파지 32회 시행 기준."""
import json, os, re, shutil
import numpy as np
from common import *
from sync import series
from svgchart import Chart, simplify

HERE = os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(OUT, "05_힘_거동")
R = json.load(open(os.path.join(HERE, "summary.json")))
GRAY = "#94a3b8"
COL = {32: "#bfdbfe", 128: "#60a5fa", 192: "#2563eb", 255: "#1e3a8a"}
COLFR = {64: "#dbeafe", 128: "#bfdbfe", 192: "#93c5fd", 255: "#60a5fa"}
# 파지력은 force_fix.py 가 로드셀 2채널의 '합'(ISO 18646-3 5.3.3)으로 산출한 값을 쓴다
FS = json.load(open(os.path.join(HERE, "force_sum.json")))
F16 = {tuple(int(x) for x in k.split("_")): float(np.mean(v)) for k, v in FS["grid"].items()}
FR = [64, 128, 192, 255]

# ── A. rFR 곡선 (rSP=128 대표) vs 사양식
c = Chart("05 · rFR별 파지력 (rSP=128)",
          "rFR [count]   ·   시편 A(Ø45 mm) 실제 파지, 각 2회",
          "파지력 [N]", (0, 270), (0, 220), note="로드셀 2채널 합 (KS B ISO 18646-3)")
c.line([0, 255], [20, 185], GRAY, 1.5, dash="6 4", label="Robotiq 사양식 (20~185 N)")
y = [F16[(f, 128)] for f in FR]
c.line(FR, y, "#dc2626", 2.0, label="실측 (rSP=128)")
c.scatter(FR, y, "#dc2626")
for f, v in zip(FR, y):
    c.text(f, v - 15, f"{v:.1f}", anchor="middle", color="#475569")
c.text(258, 190, "사양식 최대 185 N", anchor="end", color="#64748b")
c.text(258, 172, f"rSP=128 실측 {F16[(255,128)]:.0f} N (사양의 {F16[(255,128)]/185*100:.0f}%)", anchor="end", color="#b91c1c")
open(os.path.join(HERE, "svg/05_curve.svg"), "w", encoding="utf-8").write(c.render())

# ── B. rFR x rSP (16조합)
c = Chart("05 · rFR 와 rSP 의 영향 — 16조합",
          f"rFR [count]   ·   F = {FS['coef'][0]:.1f} + {FS['coef'][1]:.4f}·rFR + {FS['coef'][2]:.4f}·rSP  (R²={FS['r2']:.3f}, 각 조합 2회)",
          "파지력 [N]", (0, 270), (0, 220), note="속도 기여 > 힘 지령 기여")
c.line([0, 255], [20, 185], GRAY, 1.5, dash="6 4", label="Robotiq 사양식")
for sp in (255, 192, 128, 32):
    v = [F16[(f, sp)] for f in FR]
    c.line(FR, v, COL[sp], 1.9, label=f"rSP={sp}")
    c.scatter(FR, v, COL[sp], r=3.2)
c.text(258, 190, "사양식 최대 185 N", anchor="end", color="#64748b")
c.text(258, 208, f"실측 최대 {max(F16.values()):.0f} N", anchor="end", color="#1e3a8a")
c.text(66, 44, "같은 rFR 이라도 rSP 에 따라", color="#1e3a8a")
c.text(66, 30, f"최대 {max(F16[(f,255)]/F16[(f,32)] for f in FR):.2f}배 차이", color="#1e3a8a")
open(os.path.join(HERE, "svg/05_frsp.svg"), "w", encoding="utf-8").write(c.render())

# ── C. 힘 시계열 (07)
d = series("07"); off = R["offset"]["07"]
Fc = grip_force(d["hdr"], d["a"])
Fc -= np.median(Fc[:200])
ev = load_events(d["ev"][0])
gr = [(int(m.group(1)), (tt - d["t0"]).total_seconds() - off)
      for tt, n in ev if (m := re.match(r"rFR(\d+)_rSP\d+_rep\d+_cmd", n))]
LO = min(t for _, t in gr) - 1.5
HI = max(t for _, t in gr) + 2.0
m = (d["tm"] >= LO) & (d["tm"] <= HI)
x, y = simplify(d["tm"][m], Fc[m], 1.5)
c = Chart("05 · 파지력 시계열 — 32회 파지",
          f"측정장비 시간 [s]   ·   rFR 4단계 × rSP 4단계 × 2회, 제어 로그 -{off:.2f} s 정합",
          "파지력 [N]", (LO, HI), (-8, 262), note="rFR 구간을 색으로 구분")
for f in FR:
    ts = [t for fr_, t in gr if fr_ == f]
    a, b = min(ts) - 0.5, max(ts) + 1.2
    c.vband(a, b, COLFR[f], 0.55)
    c.text((a + b) / 2, 254, f"rFR={f}", anchor="middle", color="#1d4ed8")
    c.text((a + b) / 2, 240, f"평균 {np.mean([F16[(f,s)] for s in (32,128,192,255)]):.0f} N",
           anchor="middle", color="#475569")
c.line(x, y, "#dc2626", 1.2)
open(os.path.join(HERE, "svg/05_ts.svg"), "w", encoding="utf-8").write(c.render())

# ── 검증 + 복사
import xml.etree.ElementTree as ET


def wpx(t, px):
    return sum(px * (1.0 if ord(ch) > 0x1100 else 0.55) for ch in t)


for src, dst in (("05_curve.svg", "05_rFR별_파지력_곡선.svg"),
                 ("05_frsp.svg", "05_rFR_rSP_파지력.svg"),
                 ("05_ts.svg", "05_rFR별_파지력_시계열.svg")):
    p = os.path.join(HERE, "svg", src)
    ET.parse(p)
    s = open(p, encoding="utf-8").read()
    ti = re.search(r'<text class="t" x="(\d+)" y="\d+">([^<]*)</text>', s)
    no = re.search(r'<text class="a" x="(\d+)" y="\d+" text-anchor="end" fill="#64748b">([^<]*)</text>', s)
    gap = (int(no.group(1)) - wpx(no.group(2), 10.5)) - (int(ti.group(1)) + wpx(ti.group(2), 13)) if no else 999
    shutil.copy(p, os.path.join(DST, dst))
    print(f"{dst:32s} {os.path.getsize(p)/1024:5.1f} KiB  제목여유 {gap:5.0f}px  {'겹침!' if gap < 6 else 'ok'}")
