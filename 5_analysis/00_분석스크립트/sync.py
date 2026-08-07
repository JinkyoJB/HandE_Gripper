import numpy as np
from common import *


def onsets(t, v, thr=5.0, min_gap=0.30):
    d = np.abs(np.gradient(v, t))
    m = d > thr
    idx = np.where(m[1:] & ~m[:-1])[0] + 1
    out = []
    for i in idx:
        if not out or t[i] - out[-1] > min_gap:
            out.append(t[i])
    return np.array(out)


def series(run, cidx=0, ridx=0):
    meas, raw, ev, res = find_files(run)
    iv, hdr, a, t0 = load_clavis(meas[cidx])
    L1, L2, bad = clavis_opening(hdr, a)
    s = -(L1 + L2)
    s = np.where(np.isnan(s), np.nanmedian(s), s)
    tm = np.arange(len(a)) * iv
    c = load_ctrl(raw[ridx])
    tc = np.array([(x - t0).total_seconds() for x in c["t"]])
    return dict(iv=iv, hdr=hdr, a=a, t0=t0, L1=L1, L2=L2, bad=bad,
                tm=tm, sm=s, ctrl=c, tc=tc, meas=meas[cidx], raw=raw[ridx],
                ev=ev, res=res)


def estimate_offset(d, lo=60.0, hi=120.0, step=0.01):
    """제어 로그 시각 = clavis 시각 + offset. onset 패턴 매칭으로 추정."""
    om = onsets(d["tm"], d["sm"])
    oc = onsets(d["tc"], mm_from_gpo(d["ctrl"]["POS"]))
    if len(om) < 3 or len(oc) < 3:
        return None, None, (om, oc)
    best, bs = None, 1e18
    for off in np.arange(lo, hi, step):
        cand = oc - off                      # clavis 시간축으로 환산
        sel = cand[(cand >= om[0] - 1) & (cand <= om[-1] + 1)]
        if len(sel) < 3:
            continue
        dist = np.abs(sel[:, None] - om[None, :]).min(axis=1)
        sc = np.median(np.minimum(dist, 0.5)) + 0.002 * (len(oc) - len(sel))
        if sc < bs:
            bs, best = sc, off
    return best, bs, (om, oc)


def aligned(d, off):
    """clavis 시간축 기준으로 정합된 제어 신호 반환"""
    tc_al = d["tc"] - off
    return tc_al
