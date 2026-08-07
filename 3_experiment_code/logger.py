"""고속 폴링 로거 — 별도 소켓 연결로 gPO/gOBJ/gSTA/gFLT(+CUR)를 최대 속도로 CSV 기록.

명령용 연결과 분리된 두 번째 소켓을 쓰므로 명령 지연이 폴링 주기에 섞이지 않는다.
이벤트 마커(mark)로 명령 시점을 같은 시간축(t_perf)에 남겨 분석 시 정렬한다.
"""
import csv
import os
import threading
import time
from datetime import datetime

from hande_client import HandE


def timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M")


class PollLogger:
    def __init__(self, ip, port, out_dir, run_name, poll_vars=("POS", "OBJ", "STA", "FLT"),
                 min_interval=0.002):
        os.makedirs(out_dir, exist_ok=True)
        base = f"handE_{run_name}_{timestamp()}"
        self.log_path = os.path.join(out_dir, base + ".csv")
        self.event_path = os.path.join(out_dir, base + "_events.csv")
        self.ip, self.port = ip, port
        self.poll_vars = list(poll_vars)
        self.min_interval = min_interval
        self._stop = threading.Event()
        self._thread = None
        self.n_samples = 0
        self.mean_period_ms = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()

    def start(self):
        self._event_fp = open(self.event_path, "w", newline="", encoding="utf-8-sig")
        self._event_writer = csv.writer(self._event_fp)
        self._event_writer.writerow(["t_perf", "wall_time", "event"])
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def mark(self, event):
        """이벤트 마커 기록 (명령 직전/직후 호출)."""
        self._event_writer.writerow([f"{time.perf_counter():.6f}",
                                     datetime.now().isoformat(timespec="milliseconds"), event])
        self._event_fp.flush()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3.0)
        self._event_fp.close()

    def _loop(self):
        gr = HandE(self.ip, self.port)
        gr.connect()
        gr.probe()
        cols = list(self.poll_vars)
        if gr.cur_var:
            cols.append("CUR")
        periods = []
        with open(self.log_path, "w", newline="", encoding="utf-8-sig") as fp:
            w = csv.writer(fp)
            w.writerow(["t_perf", "wall_time"] + cols)
            t_prev = None
            while not self._stop.is_set():
                t = time.perf_counter()
                row = [f"{t:.6f}", datetime.now().isoformat(timespec="milliseconds")]
                try:
                    for v in self.poll_vars:
                        row.append(gr.get_var(v))
                    if gr.cur_var:
                        row.append(gr.get_var(gr.cur_var))
                except IOError:
                    continue
                w.writerow(row)
                self.n_samples += 1
                if t_prev is not None:
                    periods.append(t - t_prev)
                t_prev = t
                elapsed = time.perf_counter() - t
                if elapsed < self.min_interval:
                    time.sleep(self.min_interval - elapsed)
        gr.close()
        if periods:
            self.mean_period_ms = 1000.0 * sum(periods) / len(periods)
