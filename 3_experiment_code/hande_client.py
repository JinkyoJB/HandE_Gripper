"""Robotiq Hand-E — URCap 소켓(63352) 클라이언트.

프로토콜: 개행 종단 텍스트 명령.
  SET <VAR> <val> [<VAR> <val> ...]  → "ack"
  GET <VAR>                          → "<VAR> <val>"
변수: ACT GTO ATR FOR SPE POS (쓰기) / STA PRE POS OBJ FLT (읽기).
전류(CUR)는 URCap 버전에 따라 미지원일 수 있어 probe()로 확인한다.
"""
import socket
import time

WRITE_VARS = ("ACT", "GTO", "ATR", "FOR", "SPE", "POS")
READ_VARS = ("STA", "PRE", "POS", "OBJ", "FLT")
OPTIONAL_VARS = ("CUR", "COU")   # 전류 후보 이름 — R01에서 지원 여부 확인


class HandE:
    def __init__(self, ip, port=63352, timeout=2.0):
        self.ip, self.port, self.timeout = ip, port, timeout
        self.sock = None
        self.cur_var = None      # probe() 결과: 전류 변수 이름 또는 None
        self._last_pos = 0       # 마지막 이동 명령 위치 (래치 확인용)

    # ------------------------------------------------------------ 연결 -----
    def connect(self):
        self.sock = socket.create_connection((self.ip, self.port), self.timeout)
        self.sock.settimeout(self.timeout)

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.close()

    # ------------------------------------------------------------ 저수준 -----
    def _send_recv(self, cmd):
        self.sock.sendall((cmd + "\n").encode("ascii"))
        return self.sock.recv(1024).decode("ascii").strip()

    def set_vars(self, **kwargs):
        """예: set_vars(POS=255, SPE=128, FOR=64, GTO=1)"""
        parts = []
        for k, v in kwargs.items():
            k = k.upper()
            if k not in WRITE_VARS:
                raise ValueError(f"쓰기 불가 변수: {k}")
            parts.append(f"{k} {int(v)}")
        resp = self._send_recv("SET " + " ".join(parts))
        if "ack" not in resp.lower():
            raise IOError(f"SET 응답 이상: {resp!r}")

    def get_var(self, name):
        name = name.upper()
        resp = self._send_recv(f"GET {name}")
        try:
            key, val = resp.split()
            if key.upper() != name:
                raise ValueError
            return int(val)
        except ValueError:
            raise IOError(f"GET {name} 응답 이상: {resp!r}")

    # ------------------------------------------------------------ 고수준 -----
    def probe(self):
        """읽기 변수 지원 여부 점검. {변수: 값 또는 None} 반환, 전류 변수 자동 감지."""
        result = {}
        for v in READ_VARS + OPTIONAL_VARS:
            try:
                result[v] = self.get_var(v)
            except (IOError, socket.timeout):
                result[v] = None
        for cand in OPTIONAL_VARS:
            if result.get(cand) is not None:
                self.cur_var = cand
                break
        return result

    def activate(self, wait=True):
        """rACT 0→1 재활성화(자가 캘리브레이션). gSTA=3까지 대기."""
        self.set_vars(ACT=0)
        time.sleep(0.5)
        self.set_vars(ACT=1)
        if wait:
            t0 = time.time()
            while self.get_var("STA") != 3:
                if time.time() - t0 > 15.0:
                    raise TimeoutError("활성화 실패: gSTA=3 도달 못 함")
                time.sleep(0.1)

    def move(self, pos, spe, force):
        """목표 이동 명령(비대기). pos/spe/force: 0~255."""
        self._last_pos = int(pos)
        self.set_vars(POS=pos, SPE=spe, FOR=force, GTO=1)

    def wait_latch(self, pos=None, timeout=2.0):
        """명령 접수 대기: gPR(PRE)이 명령값을 반향할 때까지.

        펌웨어는 새 go-to 명령을 접수하며 gOBJ를 0으로 리셋하므로,
        래치 확인 후에 읽히는 비제로 gOBJ만 종료 상태로 신뢰할 수 있다.
        """
        if pos is None:
            pos = self._last_pos
        t0 = time.time()
        while self.get_var("PRE") != int(pos):
            if time.time() - t0 > timeout:
                raise TimeoutError(f"명령 래치 실패: gPR != {pos}")
            time.sleep(0.005)

    def wait_arrival(self, timeout=8.0, poll=0.02):
        """이동 종료 대기(래치 확인 포함). 최종 gOBJ 반환 (2=파지, 3=도달, 1=열다 막힘)."""
        self.wait_latch()
        t0 = time.time()
        while True:
            obj = self.get_var("OBJ")
            if obj != 0:
                return obj
            if time.time() - t0 > timeout:
                return 0
            time.sleep(poll)

    def snapshot(self):
        """현재 상태 일괄 읽기."""
        s = {v: self.get_var(v) for v in READ_VARS}
        if self.cur_var:
            s["CUR"] = self.get_var(self.cur_var)
        return s
