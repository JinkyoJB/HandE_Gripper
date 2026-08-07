# -*- coding: utf-8 -*-
"""파지력을 KS B ISO 18646-3 5.3.3 규정(로드셀 2개의 '합')으로 재산출.

시편은 Ø70 원통을 2분할해 로드셀 2EA를 축방향 1/3·2/3 지점에 매설한 구조이므로,
두 채널은 하나의 조임 하중을 나눠 받는다. 따라서 합이 파지력이다.
"""
import json, os, re
import numpy as np
from common import *
from sync import series

HERE = os.path.dirname(os.path.abspath(__file__))
FR = [64, 128, 192, 255]
SP = [32, 128, 192, 255]


def grip_force(d):
    """ISO 5.3.2 : 두 로드셀 값의 합. 압축을 양수로 하고 초기 구간으로 영점 보정."""
    i1 = d["hdr"].index("Force 500N #1[N]")
    i2 = d["hdr"].index("Force 500N #2[N]")
    F = -(d["a"][:, i1] + d["a"][:, i2])
    return F - np.median(F[:300])


d = series("R07")
off = json.load(open(os.path.join(HERE, "summary.json")))["offset"]["R07"]
F = grip_force(d)

# 각 파지는 0.4 s 남짓의 짧은 펄스다. 펄스 평탄역(양끝 3샘플 제외)의 평균을 값으로 쓴다.
ev = load_events(d["ev"][0])
obj = {}
for tt, n in ev:
    m = re.match(r"rFR(\d+)_rSP(\d+)_rep(\d+)_obj2", n)
    if m:
        key = (int(m.group(1)), int(m.group(2)))
        obj.setdefault(key, []).append((tt - d["t0"]).total_seconds() - off)

hi = np.where(F > 20)[0]
pulses = [g for g in np.split(hi, np.where(np.diff(hi) > 20)[0] + 1) if len(g) > 20]
print(f"파지 펄스 {len(pulses)}개 검출 (기대 32)")

grid = {}
for key in sorted(obj):
    vals = []
    for t in obj[key]:
        cand = [g for g in pulses if abs(d["tm"][g[0]] - t) < 0.5]
        if cand:
            g = cand[0][3:-3]                      # 상승·하강 에지 제외
            vals.append(float(np.mean(F[g])))
    if vals:
        grid[key] = vals

# 회귀 : F = c0 + c1·rFR + c2·rSP
X = np.array([[1, f, s] for (f, s) in grid for _ in grid[(f, s)]], dtype=float)
y = np.array([v for k in grid for v in grid[k]])
c, *_ = np.linalg.lstsq(X, y, rcond=None)
r2 = 1 - ((y - X @ c) ** 2).sum() / ((y - y.mean()) ** 2).sum()

print(f"시행 {len(y)}건   F = {c[0]:.1f} + {c[1]:.4f}*rFR + {c[2]:.4f}*rSP   R2={r2:.4f}")
print(f"실측 범위 {y.min():.1f} ~ {y.max():.1f} N,  피크 {F.max():.1f} N")
print()
print("      " + "".join(f"rSP={s:<7d}" for s in SP))
for f in FR:
    row = "".join(f"{np.mean(grid[(f, s)]):7.1f}    " if (f, s) in grid else "     -     "
                  for s in SP)
    print(f"rFR{f:4d} {row}")

print()
print(" rFR  사양식[N]  실측(rSP=128)  비")
for f in FR:
    sp = 20 + 165 * f / 255
    v = np.mean(grid[(f, 128)])
    print(f" {f:4d} {sp:8.1f} {v:13.1f} {v/sp:6.2f}")

json.dump({"grid": {f"{f}_{s}": [round(x, 2) for x in v] for (f, s), v in grid.items()},
           "coef": [round(float(x), 4) for x in c], "r2": round(float(r2), 4),
           "min": round(float(y.min()), 1), "max": round(float(y.max()), 1),
           "peak": round(float(F.max()), 1)},
          open(os.path.join(HERE, "force_sum.json"), "w"), ensure_ascii=False, indent=1)
