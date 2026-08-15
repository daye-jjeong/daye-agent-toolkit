"""새로고침 진행 상태.

페이지가 진행바를 그리려면 지금 몇 건까지 받았는지 알아야 한다. 총 건수는
받아 보기 전에는 모르므로, 직전 수집 건수를 추정치로 쓰고 넘으면 100%에서
멈춘다. 추정할 근거가 없으면 비율을 지어내지 않고 건수만 센다.
"""

import threading


class RefreshState:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = "idle"
        self._fetched = 0
        self._expected = 0
        self._as_of = None
        self._error = None

    def start(self, expected=0):
        """수집 시작. 이미 돌고 있으면 False — 두 번 눌러도 하나만 돈다."""
        with self._lock:
            if self._state == "running":
                return False
            self._state = "running"
            self._fetched = 0
            self._expected = expected or 0
            self._error = None
            return True

    def progress(self, fetched):
        with self._lock:
            self._fetched = fetched

    def done(self, as_of, count):
        with self._lock:
            self._state = "done"
            self._fetched = count
            self._as_of = as_of

    def fail(self, message):
        with self._lock:
            self._state = "error"
            self._error = str(message)

    def snapshot(self):
        with self._lock:
            if self._state == "done":
                percent = 100
            elif self._expected > 0:
                percent = min(100, round(self._fetched / self._expected * 100))
            else:
                percent = None
            return {
                "state": self._state,
                "fetched": self._fetched,
                "expected": self._expected,
                "percent": percent,
                "as_of": self._as_of,
                "error": self._error,
            }
