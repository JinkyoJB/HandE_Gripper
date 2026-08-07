"""경량 SVG 차트 생성기 (파일당 수 KB)."""
import re
import numpy as np

W, H = 640, 300
ML, MR, MT, MB = 62, 16, 34, 46

STYLE = ("<style>text{font-family:system-ui,'Malgun Gothic','Noto Sans KR',sans-serif;fill:#334155}"
         ".t{font-size:13px;font-weight:600;fill:#0f172a}.a{font-size:10.5px}.l{font-size:10.5px}"
         ".ax{stroke:#94a3b8;stroke-width:1;fill:none}.gr{stroke:#e2e8f0;stroke-width:1;fill:none}"
         "path.s{fill:none;stroke-width:1.5;stroke-linejoin:round;stroke-linecap:round}</style>")


def _xml_safe(svg):
    """<text> 내용의 & 를 XML 엔티티로 바꾼다. 안 하면 SVG 파일이 열리지 않는다."""
    return re.sub(r">([^<>]*)</text>",
                  lambda m: ">" + m.group(1).replace("&", "&amp;") + "</text>", svg)


def _f(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


class Chart:
    def __init__(self, title, xlabel, ylabel, xlim, ylim, w=W, h=H, ml=ML, note=None):
        self.w, self.h, self.ml = w, h, ml
        self.x0, self.x1 = xlim
        self.y0, self.y1 = ylim
        self.parts = []
        self.title, self.xlabel, self.ylabel, self.note = title, xlabel, ylabel, note
        self.legend = []

    def px(self, x):
        return self.ml + (np.asarray(x, float) - self.x0) / (self.x1 - self.x0) * (self.w - self.ml - MR)

    def py(self, y):
        return self.h - MB - (np.asarray(y, float) - self.y0) / (self.y1 - self.y0) * (self.h - MT - MB)

    def line(self, x, y, color, width=1.5, dash=None, label=None):
        X, Y = self.px(x), self.py(y)
        d = "M" + " L".join(f"{a:.1f},{b:.1f}" for a, b in zip(X, Y))
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(f'<path class="s" d="{d}" stroke="{color}" stroke-width="{width}"{da}/>')
        if label:
            self.legend.append((label, color, dash))

    def scatter(self, x, y, color, r=3.4, label=None, fill=True):
        X, Y = self.px(x), self.py(y)
        f = color if fill else "#fff"
        self.parts.append("".join(
            f'<circle cx="{a:.1f}" cy="{b:.1f}" r="{r}" fill="{f}" stroke="{color}" stroke-width="1.2"/>'
            for a, b in zip(X, Y)))
        if label:
            self.legend.append((label, color, None))

    def bars(self, cats, vals, color, err=None, labels=True, fmt="{:.0f}"):
        n = len(cats)
        span = (self.w - self.ml - MR) / n
        base = self.py(max(self.y0, 0))
        for i, (c, v) in enumerate(zip(cats, vals)):
            cx = self.ml + span * (i + 0.5)
            bw = span * 0.5
            top = self.py(v)
            self.parts.append(f'<rect x="{cx-bw/2:.1f}" y="{top:.1f}" width="{bw:.1f}" '
                              f'height="{abs(base-top):.1f}" fill="{color}" rx="2"/>')
            if err is not None and err[i]:
                e0, e1 = self.py(v - err[i]), self.py(v + err[i])
                self.parts.append(f'<path class="ax" stroke="#475569" d="M{cx:.1f},{e0:.1f} L{cx:.1f},{e1:.1f} '
                                  f'M{cx-4:.1f},{e0:.1f} L{cx+4:.1f},{e0:.1f} '
                                  f'M{cx-4:.1f},{e1:.1f} L{cx+4:.1f},{e1:.1f}"/>')
            if labels:
                self.parts.append(f'<text class="a" x="{cx:.1f}" y="{top-6:.1f}" text-anchor="middle">'
                                  f'{fmt.format(v)}</text>')
            self.parts.append(f'<text class="a" x="{cx:.1f}" y="{self.h-MB+16:.1f}" '
                              f'text-anchor="middle">{c}</text>')

    def band(self, y0, y1, color="#10b981", op=0.10, text=None):
        a, b = self.py(y1), self.py(y0)
        self.parts.insert(0, f'<rect x="{self.ml}" y="{a:.1f}" width="{self.w-self.ml-MR:.1f}" '
                             f'height="{abs(b-a):.1f}" fill="{color}" opacity="{op}"/>')
        if text:
            self.parts.append(f'<text class="a" x="{self.ml+6}" y="{a-4:.1f}" fill="#059669">{text}</text>')

    def vband(self, x0, x1, color="#3b82f6", op=0.10):
        a, b = self.px(x0), self.px(x1)
        self.parts.insert(0, f'<rect x="{a:.1f}" y="{MT}" width="{max(b-a,0.6):.1f}" '
                             f'height="{self.h-MT-MB}" fill="{color}" opacity="{op}"/>')

    def hline(self, y, color="#64748b", dash="4 3"):
        p = self.py(y)
        self.parts.append(f'<path class="ax" stroke="{color}" stroke-dasharray="{dash}" '
                          f'd="M{self.ml},{p:.1f} L{self.w-MR},{p:.1f}"/>')

    def text(self, x, y, s, anchor="start", cls="a", color=None):
        c = f' fill="{color}"' if color else ""
        self.parts.append(f'<text class="{cls}" x="{self.px(x):.1f}" y="{self.py(y):.1f}" '
                          f'text-anchor="{anchor}"{c}>{s}</text>')

    def render(self, xticks=None, yticks=None, xcat=False):
        g = []
        if yticks is None:
            yticks = np.linspace(self.y0, self.y1, 5)
        if xticks is None and not xcat:
            xticks = np.linspace(self.x0, self.x1, 6)
        for t in yticks:
            p = self.py(t)
            g.append(f'<path class="gr" d="M{self.ml},{p:.1f} L{self.w-MR},{p:.1f}"/>')
            g.append(f'<text class="a" x="{self.ml-7}" y="{p+3.5:.1f}" text-anchor="end">{_f(t)}</text>')
        if not xcat:
            for t in xticks:
                p = self.px(t)
                g.append(f'<text class="a" x="{p:.1f}" y="{self.h-MB+16:.1f}" text-anchor="middle">{_f(t)}</text>')
        g.append(f'<path class="ax" d="M{self.ml},{MT} L{self.ml},{self.h-MB} L{self.w-MR},{self.h-MB}"/>')
        leg = []
        if self.legend:
            lx, ly = self.ml + 10, MT + 12
            for i, (lab, col, dash) in enumerate(self.legend):
                y = ly + i * 15
                da = f' stroke-dasharray="{dash}"' if dash else ""
                leg.append(f'<path class="s" stroke="{col}" stroke-width="2"{da} d="M{lx},{y-4} L{lx+18},{y-4}"/>')
                leg.append(f'<text class="l" x="{lx+24}" y="{y}">{lab}</text>')
        note = (f'<text class="a" x="{self.w-MR}" y="{MT-9}" text-anchor="end" fill="#64748b">{self.note}</text>'
                if self.note else "")
        out = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
                f'width="{self.w}" height="{self.h}">{STYLE}'
                f'<rect width="{self.w}" height="{self.h}" fill="#fff"/>'
                f'<text class="t" x="{self.ml}" y="{MT-13}">{self.title}</text>{note}'
                + "".join(g) + "".join(self.parts) + "".join(leg)
                + f'<text class="a" x="{(self.ml+self.w-MR)/2:.0f}" y="{self.h-8}" '
                  f'text-anchor="middle">{self.xlabel}</text>'
                + f'<text class="a" x="{-((self.h-MT-MB)/2+MT):.0f}" y="14" transform="rotate(-90)" '
                  f'text-anchor="middle">{self.ylabel}</text></svg>')
        return _xml_safe(out)


def decimate(x, y, n=420):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) <= n:
        return x, y
    idx = np.linspace(0, len(x) - 1, n).astype(int)
    return x[idx], y[idx]


def simplify(x, y, tol):
    """계단/펄스 신호용 단순화: 값 변화가 tol 이상일 때만 점을 유지."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    keep = [0]
    last = y[0]
    for i in range(1, len(y) - 1):
        if abs(y[i] - last) > tol:
            if keep[-1] != i - 1:
                keep.append(i - 1)
            keep.append(i)
            last = y[i]
    keep.append(len(y) - 1)
    k = np.array(sorted(set(keep)))
    return x[k], y[k]
