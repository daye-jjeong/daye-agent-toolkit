"""마비노기 데이터 플랫폼 — 공유 데이터 접근 (경로 해석).

모든 store의 위치를 여기 한 곳에서 정한다. 분석기·수집기는 경로를 하드코딩하지
말고 이 모듈을 쓴다. 스키마·버전 등 데이터 계약은 옆 ../../README.md.

데이터 홈
    기본 ``~/.mabi/``. 환경변수 ``MABI_HOME``으로 덮어쓴다(테스트·임시 실행용 —
    life-dashboard의 ``LIFE_DASHBOARD_DB`` 패턴). git 밖, 단일 store.

경로 해석 (구 경로 호환)
    "새 경로에 파일이 있으면 그것, 없으면 구 경로." 지금은(1단계) 수집기가 아직
    구 위치에 쓰므로 구 경로로 풀린다. 2·3단계에서 데이터가 새 홈으로 옮겨가면
    소비자 코드를 안 고쳐도 자동으로 새 경로를 쓴다.

계약 버전은 README.md의 '데이터 계약'과 맞춘다.
"""

import os
import pathlib

CONTRACT_VERSION = 1

# 구 위치 — 현재 writer들이 쓰는 곳(1단계 fallback).
_LEGACY_FARMING_LOG = (
    pathlib.Path.home()
    / "Library/Application Support/BackgroundAutomator/cycle-log.jsonl"
)
_LEGACY_PRICES_DB = pathlib.Path.home() / ".mabi-equipment-cost/data.db"


def home():
    """데이터 홈 디렉터리. MABI_HOME이 있으면 그것, 없으면 ~/.mabi."""
    env = os.environ.get("MABI_HOME")
    return pathlib.Path(env).expanduser() if env else pathlib.Path.home() / ".mabi"


def _resolve(new, legacy):
    """새 경로에 파일이 있으면 새것, 없으면 구 경로. 둘 다 없으면 새 경로(대상)."""
    if new.exists():
        return new
    if legacy.exists():
        return legacy
    return new


def farming_log():
    """파밍 사이클 로그 파일 (JSONL). automator가 매 판 append."""
    return _resolve(home() / "farming" / "cycle-log.jsonl", _LEGACY_FARMING_LOG)


def farming_log_dir():
    """파밍 로그가 있는 디렉터리(--dir 인자용)."""
    return farming_log().parent


def prices_db():
    """거래소 시세 DB. equipment-cost 수집기가 쓰고, 분석기가 읽기 전용으로 본다."""
    return _resolve(home() / "prices.db", _LEGACY_PRICES_DB)
