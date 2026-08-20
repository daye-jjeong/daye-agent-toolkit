#!/usr/bin/env python3
"""집계 함수(이음새)의 done 기준 테스트.

웹 화면은 결과를 그리기만 하므로 테스트하지 않는다. 로그 레코드를 넣으면
던전 × 입장 방식 × 아이템 표가 나오는 지점만 검증한다.

    python3 test_analyze_logs.py
"""

import importlib.util
import pathlib
import unittest

# 파일명이 하이픈이라 일반 import가 안 된다. 경로로 로드한다.
_spec = importlib.util.spec_from_file_location(
    "analyze_logs", pathlib.Path(__file__).with_name("analyze-logs.py")
)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


# 테스트는 실제 JSON 파일에 의존하지 않게 사전을 직접 넣는다.
CORR = {
    "오독": {"마울": "마물", "버닝 워크": "버닝 위크"},
    "조각": {"미지의": "미지의 소울 조각", "소울 조각": "미지의 소울 조각"},
    "제외": ["버닝 위크", "초심자 동행"],
    "제외_접두": ["비상 탈출", "던전 탐험을 계속"],
    "분리": {"미지의 소울 조각갱신권": ["미지의 소울 조각", "갱신권"]},
}


def cyc(at, dungeon="룬다 1층 2구역", items=None, entry=None, quantities=None):
    r = {"at": at, "dungeon": dungeon, "items": items or []}
    if entry is not None:
        r["entry"] = entry
    if quantities is not None:
        r["quantities"] = quantities
    return r


class ResolveEntry(unittest.TestCase):
    def test_기록된_입장방식은_그대로_쓴다(self):
        self.assertEqual(
            mod.resolve_entry({"entry": "coin", "items": []})[0], "은동전 씀"
        )
        self.assertEqual(
            mod.resolve_entry({"entry": "free", "items": []})[0], "임무 해제"
        )
        # 기록이 있으면 칸 수와 무관하게 추정이 아니다.
        _, est = mod.resolve_entry({"entry": "coin", "items": ["a"] * 4})
        self.assertFalse(est)

    def test_기록_없으면_칸수로_세갈래_판정(self):
        재화, e1 = mod.resolve_entry({"items": ["x"] * 15})
        무료, e2 = mod.resolve_entry({"items": ["x"] * 6})
        불가, e3 = mod.resolve_entry({"items": ["x"] * 10})
        self.assertIn("재화", 재화)
        self.assertIn("무료", 무료)
        self.assertEqual(불가, "판정 불가")
        self.assertTrue(e1 and e2 and e3)  # 셋 다 추정 표시


class Aggregate(unittest.TestCase):
    def base(self, n=25, step=110, entry="free", **kw):
        """같은 던전으로 n판. step초 간격. 기본은 무료 입장."""
        from datetime import datetime, timedelta, timezone

        t0 = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
        out = []
        for i in range(n):
            at = (t0 + timedelta(seconds=step * i)).strftime("%Y-%m-%dT%H:%M:%SZ")
            out.append(cyc(at, entry=entry, **kw))
        return out

    def test_붙은_문자열이_각_아이템으로_갈린다(self):
        cs = self.base(items=["미지의 소울 조각갱신권"])
        r = mod.aggregate_farming(cs, CORR)
        items = r["dungeons"]["룬다 1층 2구역"]["임무 해제"]["items"]
        self.assertIn("미지의 소울 조각", items)
        self.assertIn("갱신권", items)

    def test_같은_던전_다른_표기가_한줄로_합쳐진다(self):
        cs = self.base(items=["미지의 소울 조각"])
        cs += self.base(dungeon="룬다. 1층 2구역", items=["미지의 소울 조각"])
        r = mod.aggregate_farming(cs, CORR)
        # 표기 흔들려도 던전 키가 하나로 묶여야 한다.
        keys = list(r["dungeons"])
        self.assertEqual(len(keys), 1, f"던전이 쪼개짐: {keys}")

    def test_5분_넘는_간격은_판당소요에서_빠진다(self):
        from datetime import datetime, timedelta, timezone

        t0 = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
        offsets = [0, 110, 220, 330]  # 110초 간격 3개
        offsets += [330 + 600]  # 10분(자리 비움) 간격 1개
        offsets += [330 + 600 + 110]  # 다시 110초
        cs = [
            cyc(
                (t0 + timedelta(seconds=o)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                items=["미지의 소울 조각"],
                entry="free",
            )
            for o in offsets
        ]
        r = mod.aggregate_farming(cs, CORR)
        gph = r["dungeons"]["룬다 1층 2구역"]["임무 해제"]["games_per_hour"]
        # 110초 = 시간당 ~32.7판. 600초가 섞였으면 확 낮아진다.
        self.assertGreater(gph, 30)

    def test_판정불가는_어느쪽에도_안_섞인다(self):
        cs = self.base(n=3, items=["x"] * 10, entry=None)  # 7~14칸
        cs += self.base(n=3, items=["미지의 소울 조각"], entry="free")
        r = mod.aggregate_farming(cs, CORR)
        entries = r["dungeons"]["룬다 1층 2구역"]
        self.assertIn("판정 불가", entries)
        self.assertNotIn("미지의 소울 조각", entries["판정 불가"]["items"])

    def test_사전에_없는_문자열이_미인식으로_세어진다(self):
        # 한글이 안 남는 OCR 잡음 = 미인식(조용히 버리지 않고 센다).
        cs = self.base(items=["미지의 소울 조각", "★☆:*10"])
        r = mod.aggregate_farming(cs, CORR)
        self.assertTrue(r["unrecognized"], "미인식이 비었다")
        self.assertIn("★☆:*10", r["unrecognized"])

    def test_제외사전_문자열은_미인식이_아니다(self):
        cs = self.base(items=["미지의 소울 조각", "버닝 위크", "비상 탈출! 리"])
        r = mod.aggregate_farming(cs, CORR)
        self.assertNotIn("버닝 위크", r["unrecognized"])
        self.assertFalse(any("비상" in k for k in r["unrecognized"]))
        items = r["dungeons"]["룬다 1층 2구역"]["임무 해제"]["items"]
        self.assertNotIn("버닝 위크", items)

    def test_뱃지_없는_아이템은_1개로_세어진다(self):
        cs = self.base(items=["갱신권"])  # quantities 없음
        r = mod.aggregate_farming(cs, CORR)
        it = r["dungeons"]["룬다 1층 2구역"]["임무 해제"]["items"]["갱신권"]
        # 25판 모두 1개씩 → 판당 1.0
        self.assertAlmostEqual(it["per_game"], 1.0, places=3)

    def test_뱃지_있으면_그_수량을_쓴다(self):
        cs = self.base(items=["미지의 소울 조각"], quantities={"미지의 소울 조각": 2})
        r = mod.aggregate_farming(cs, CORR)
        it = r["dungeons"]["룬다 1층 2구역"]["임무 해제"]["items"]["미지의 소울 조각"]
        self.assertAlmostEqual(it["per_game"], 2.0, places=3)

    def test_아이템별_시간당_획득이_나온다(self):
        cs = self.base(items=["미지의 소울 조각"])
        r = mod.aggregate_farming(cs, CORR)
        it = r["dungeons"]["룬다 1층 2구역"]["임무 해제"]["items"]["미지의 소울 조각"]
        # 판당 1개 × 시간당 ~32판 ≈ 32/시간
        self.assertGreater(it["per_hour"], 25)

    def test_표본이_적으면_시간당_대신_표본수(self):
        cs = self.base(n=5, items=["미지의 소울 조각"])  # MIN_SAMPLES 미만
        r = mod.aggregate_farming(cs, CORR)
        it = r["dungeons"]["룬다 1층 2구역"]["임무 해제"]["items"]["미지의 소울 조각"]
        self.assertIsNone(it["per_hour"])
        self.assertEqual(it["sample"], 5)


# 영혼석 화이트리스트: 어간 → 캐논 이름. 시세는 캐논 이름으로 조인한다.
SOUL_WL = {
    "망령": "망령의 영혼석",
    "야생": "야생의 영혼석",
    "공명": "공명의 영혼석",
    "원념": "원념의 영혼석",
    "파동": "파동의 영혼석",
}
SOUL_PRICE = {
    "망령의 영혼석": 105,
    "야생의 영혼석": 40,
    "공명의 영혼석": 38,
    "원념의 영혼석": 111,
    "파동의 영혼석": 32,
}


class MatchSoulStone(unittest.TestCase):
    def m(self, text):
        return mod.match_soul_stone(text, SOUL_WL)

    def test_캐논은_그대로_잡힌다(self):
        self.assertEqual(self.m("망령의 영혼석"), ("soul", "망령"))

    def test_OCR변종은_어간_근사로_캐논에_붙는다(self):
        # 망경 → 망령 (한 글자 오독)
        self.assertEqual(self.m("망경의 영혼석"), ("soul", "망령"))
        # 0생 → 야생 (숫자로 흘려 읽음)
        self.assertEqual(self.m("0생의 영혼석"), ("soul", "야생"))

    def test_조인_문자열_속_영혼석도_잡힌다(self):
        self.assertEqual(self.m("마물 퇴치 증표 망령의 영혼석"), ("soul", "망령"))
        self.assertEqual(self.m("{ 야생의 영혼석"), ("soul", "야생"))

    def test_어간_못_가르면_종류_불명(self):
        # '생'만 남아 어느 캐논인지 못 가른다.
        self.assertEqual(self.m("생의 영혼석"), ("unknown", None))

    def test_영혼석_아니면_None(self):
        self.assertEqual(self.m("모험가 포인트"), (None, None))
        self.assertEqual(self.m("☆7 영혼의 스톤애쉬 블레이드Z"), (None, None))


class CanonicalDungeon(unittest.TestCase):
    def test_스펠링_변종이_한_canonical로_병합(self):
        self.assertEqual(
            mod.canonical_dungeon("페카고는 실증 1층 2구역"), "페카 고분 심층 1층 2구역"
        )
        self.assertEqual(mod.canonical_dungeon("피오도 1층 2구역"), "피오드 1층 2구역")
        self.assertEqual(mod.canonical_dungeon("로다 1층 2구역"), "룬다 1층 2구역")
        self.assertEqual(
            mod.canonical_dungeon("페카 고분 심증 2층 1구역"),
            "페카 고분 심층 2층 1구역",
        )

    def test_비심층은_심층_안붙는다(self):
        self.assertNotIn("심층", mod.canonical_dungeon("룬다 1층 2구역"))
        self.assertNotIn("심층", mod.canonical_dungeon("피오드 1층 2구역"))

    def test_미상은_기타던전(self):
        self.assertEqual(mod.canonical_dungeon("허상의 정박지"), "기타 던전")
        self.assertEqual(mod.canonical_dungeon("2구역"), "기타 던전")
        self.assertEqual(mod.canonical_dungeon("처치 완료"), "기타 던전")

    def test_is_deep_OCR변종도_잡는다(self):
        self.assertTrue(mod.is_deep_dungeon("페카 고분 심증 1층 2구역"))  # 심증
        self.assertTrue(mod.is_deep_dungeon("북쪽 폐허 실층 2층 3구역"))  # 실층
        self.assertFalse(mod.is_deep_dungeon("룬다 1층 2구역"))


class SoulRanking(unittest.TestCase):
    def base(
        self,
        n=25,
        step=110,
        dungeon="페카 고분 심층 1층 2구역",
        entry="free",
        start_hours=0,
        **kw,
    ):
        from datetime import datetime, timedelta, timezone

        # 던전을 여럿 섞을 땐 start_hours로 시간대를 갈라 타임스탬프가 겹치지
        # 않게 한다(겹치면 cycle_durations가 엉킨다).
        t0 = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc) + timedelta(
            hours=start_hours
        )
        out = []
        for i in range(n):
            at = (t0 + timedelta(seconds=step * i)).strftime("%Y-%m-%dT%H:%M:%SZ")
            out.append(cyc(at, dungeon=dungeon, entry=entry, **kw))
        return out

    def row_for(self, r, dungeon, stem):
        for row in r["rows"]:
            if row["dungeon"] == dungeon and row["stem"] == stem:
                return row
        return None

    def test_화이트리스트_밖은_기타로_세고_순위에서_빠진다(self):
        cs = self.base(items=["망령의 영혼석", "모험가 포인트"])
        r = mod.soul_dungeon_ranking(cs, SOUL_WL, SOUL_PRICE, CORR)
        self.assertIsNotNone(self.row_for(r, "페카 고분 심층 1층 2구역", "망령"))
        # 모험가 포인트는 순위 행이 안 되고 기타 건수로만 잡힌다.
        self.assertEqual(r["other_count"], 25)
        self.assertFalse(any("모험가" in (row.get("name") or "") for row in r["rows"]))

    def test_OCR변종이_캐논으로_합쳐진다(self):
        cs = self.base(n=13, items=["망령의 영혼석"])
        cs += self.base(n=12, items=["망경의 영혼석"])  # 같은 던전·간격
        r = mod.soul_dungeon_ranking(cs, SOUL_WL, SOUL_PRICE, CORR)
        rows = [row for row in r["rows"] if row["stem"] == "망령"]
        self.assertEqual(len(rows), 1, "변종이 따로 셈됨")
        self.assertEqual(rows[0]["count_total"], 25)

    def test_조인_문자열이_망령으로_잡힌다(self):
        cs = self.base(items=["마물 퇴치 증표 망령의 영혼석"])
        r = mod.soul_dungeon_ranking(cs, SOUL_WL, SOUL_PRICE, CORR)
        row = self.row_for(r, "페카 고분 심층 1층 2구역", "망령")
        self.assertIsNotNone(row)
        self.assertEqual(row["count_total"], 25)

    def test_종류_불명이_따로_세어진다(self):
        cs = self.base(items=["망령의 영혼석", "생의 영혼석"])
        r = mod.soul_dungeon_ranking(cs, SOUL_WL, SOUL_PRICE, CORR)
        self.assertEqual(r["unknown_count"], 25)
        # 종류 불명은 캐논 행으로 안 샌다.
        self.assertFalse(any(row["stem"] == "생" for row in r["rows"]))

    def test_시간당_개수와_데카가_나오고_데카_내림차순(self):
        # 망령(105) 던전과 파동(32) 던전, 개수·가동 동일 → 망령이 위.
        cs = self.base(dungeon="페카 고분 심층 1층 2구역", items=["망령의 영혼석"])
        cs += self.base(
            dungeon="룬다 1층 2구역", items=["파동의 영혼석"], start_hours=24
        )
        r = mod.soul_dungeon_ranking(cs, SOUL_WL, SOUL_PRICE, CORR)
        rows = r["rows"]
        self.assertEqual(rows[0]["stem"], "망령")
        self.assertEqual(rows[1]["stem"], "파동")
        self.assertGreater(rows[0]["per_hour_count"], 25)
        self.assertGreater(rows[0]["per_hour_deca"], rows[1]["per_hour_deca"])
        # 데카 = 시간당 개수 × 시세
        self.assertAlmostEqual(
            rows[0]["per_hour_deca"],
            rows[0]["per_hour_count"] * 105,
            places=3,
        )

    def test_시세_없는_영혼석은_데카가_빈다(self):
        prices = dict(SOUL_PRICE)
        del prices["망령의 영혼석"]  # 망령 시세 없음
        cs = self.base(items=["망령의 영혼석"])
        r = mod.soul_dungeon_ranking(cs, SOUL_WL, prices, CORR)
        row = self.row_for(r, "페카 고분 심층 1층 2구역", "망령")
        self.assertIsNone(row["per_hour_deca"])
        self.assertIsNotNone(row["per_hour_count"])  # 개수는 나온다

    def test_심층은_뱃지_있어도_1개(self):
        # 심층 던전은 더블 루팅이 없다 → 영혼석 무조건 1개. 뱃지는 무시.
        cs = self.base(
            n=25,
            dungeon="페카 고분 심층 1층 2구역",
            items=["망령의 영혼석"],
            quantities={"망령의 영혼석": 2},
        )
        r = mod.soul_dungeon_ranking(cs, SOUL_WL, SOUL_PRICE, CORR)
        row = self.row_for(r, "페카 고분 심층 1층 2구역", "망령")
        self.assertAlmostEqual(row["count_per_game"], 1.0, places=3)

    def test_비심층은_더블루팅_뱃지2가_2개(self):
        # 룬다·피오드(비심층)에서만 여러 개가 나온다.
        cs = self.base(
            n=25,
            dungeon="룬다 1층 2구역",
            items=["망령의 영혼석"],
            quantities={"망령의 영혼석": 2},
        )
        r = mod.soul_dungeon_ranking(cs, SOUL_WL, SOUL_PRICE, CORR)
        row = self.row_for(r, "룬다 1층 2구역", "망령")
        self.assertAlmostEqual(row["count_per_game"], 2.0, places=3)

    def test_비심층_조인오염_뱃지는_1개로_센다(self):
        # 조인으로 옆 아이템 수량(180)이 붙으면 개수를 못 믿는다 → 1개.
        cs = self.base(
            n=25,
            dungeon="피오드 1층 2구역",
            items=["마물 퇴치 증표 망령의 영혼석"],
            quantities={"마물 퇴치 증표 망령의 영혼석": 180},
        )
        r = mod.soul_dungeon_ranking(cs, SOUL_WL, SOUL_PRICE, CORR)
        row = self.row_for(r, "피오드 1층 2구역", "망령")
        self.assertAlmostEqual(row["count_per_game"], 1.0, places=3)

    def test_뱃지_없으면_1개(self):
        cs = self.base(n=25, dungeon="룬다 1층 2구역", items=["망령의 영혼석"])
        r = mod.soul_dungeon_ranking(cs, SOUL_WL, SOUL_PRICE, CORR)
        row = self.row_for(r, "룬다 1층 2구역", "망령")
        self.assertAlmostEqual(row["count_per_game"], 1.0, places=3)

    def test_재화표식_판별(self):
        MK = ["파편", "조각난"]
        self.assertTrue(mod.is_paid_run({"items": ["망령의 영혼석", "룬의 파편"]}, MK))
        self.assertTrue(mod.is_paid_run({"items": ["조각난 다이아몬드"]}, MK))
        # base만 있으면 무료
        self.assertFalse(
            mod.is_paid_run({"items": ["망령의 영혼석", "마물 퇴치 증표"]}, MK)
        )
        self.assertFalse(mod.is_paid_run({"items": []}, MK))

    def test_재화무료_모드로_갈린다(self):
        MK = ["파편"]
        # 무료 20판: 소울 없음. 재화 20판: 망령 + 룬의 파편(표식).
        free = self.base(n=20, dungeon="룬다 1층 2구역", items=["마물 퇴치 증표"])
        paid = self.base(
            n=20,
            dungeon="룬다 1층 2구역",
            start_hours=48,
            items=["망령의 영혼석", "룬의 파편"],
        )
        cs = free + paid
        r_all = mod.soul_dungeon_ranking(
            cs, SOUL_WL, SOUL_PRICE, CORR, mode="all", markers=MK
        )
        r_paid = mod.soul_dungeon_ranking(
            cs, SOUL_WL, SOUL_PRICE, CORR, mode="paid", markers=MK
        )
        r_free = mod.soul_dungeon_ranking(
            cs, SOUL_WL, SOUL_PRICE, CORR, mode="free", markers=MK
        )
        # 재화 모드: 망령 행, 판수 20, 판당 1개
        row_p = self.row_for(r_paid, "룬다 1층 2구역", "망령")
        self.assertIsNotNone(row_p)
        self.assertEqual(row_p["games"], 20)
        self.assertAlmostEqual(row_p["count_per_game"], 1.0, places=3)
        # 무료 모드: 소울 없어 망령 행이 없다
        self.assertIsNone(self.row_for(r_free, "룬다 1층 2구역", "망령"))
        # 전체: 40판 중 20판만 소울 → 판당 0.5
        row_a = self.row_for(r_all, "룬다 1층 2구역", "망령")
        self.assertAlmostEqual(row_a["count_per_game"], 0.5, places=3)
        # gph는 전체 판 기준으로 공유 → 재화 모드도 per_hour가 나온다
        self.assertIsNotNone(row_p["per_hour_count"])

    def test_mode_오버라이드가_표식보다_우선한다(self):
        # 표식 없어도 mode="재화"면 재화 판으로 잡힌다(사람이 못박은 값 우선).
        cs = self.base(n=20, dungeon="룬다 1층 2구역", items=["망령의 영혼석"])
        for c in cs:
            c["mode"] = "재화"
        r = mod.soul_dungeon_ranking(
            cs, SOUL_WL, SOUL_PRICE, CORR, mode="paid", markers=["파편"]
        )
        row = self.row_for(r, "룬다 1층 2구역", "망령")
        self.assertIsNotNone(row)
        self.assertEqual(row["games"], 20)
        # 무료 모드에선 안 잡힌다
        r2 = mod.soul_dungeon_ranking(
            cs, SOUL_WL, SOUL_PRICE, CORR, mode="free", markers=["파편"]
        )
        self.assertIsNone(self.row_for(r2, "룬다 1층 2구역", "망령"))

    def test_5분_넘는_간격은_판당소요에서_빠진다(self):
        from datetime import datetime, timedelta, timezone

        t0 = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
        offsets = [110 * i for i in range(24)]  # 110초 간격 23개
        offsets.append(offsets[-1] + 600)  # 10분 자리 비움 1개
        offsets.append(offsets[-1] + 110)
        cs = [
            cyc(
                (t0 + timedelta(seconds=o)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                dungeon="페카 고분 심층 1층 2구역",
                items=["망령의 영혼석"],
                entry="free",
            )
            for o in offsets
        ]
        r = mod.soul_dungeon_ranking(cs, SOUL_WL, SOUL_PRICE, CORR)
        row = self.row_for(r, "페카 고분 심층 1층 2구역", "망령")
        # 110초 = 시간당 ~32판. 600초가 섞였으면 확 낮아진다.
        self.assertGreater(row["per_hour_count"], 30)

    def test_활동량_데이터는_기존_요약함수_그대로(self):
        cs = self.base(n=25, items=["망령의 영혼석"])
        daily = mod.daily_summary(cs)
        self.assertTrue(daily)
        self.assertEqual(sum(d["games"] for d in daily), 25)

    def test_날짜별_데카_추세가_나온다(self):
        cs = self.base(n=25, items=["망령의 영혼석"])  # 하루, 판당 망령 1개
        trend = mod.daily_soul_deca(cs, SOUL_WL, SOUL_PRICE)
        self.assertEqual(len(trend), 1)
        # deca = 25 × 105, 가동 = 24 × 110초 → 시간당 데카
        expected = (25 * 105) / (24 * 110 / 3600)
        self.assertAlmostEqual(trend[0]["deca_per_hour"], expected, places=0)

    def test_시세_없으면_데카_추세는_비운다(self):
        cs = self.base(n=25, items=["망령의 영혼석"])
        trend = mod.daily_soul_deca(cs, SOUL_WL, {})  # 시세 전무
        self.assertIsNone(trend[0]["deca_per_hour"])


class DailySoulDeca(unittest.TestCase):
    def test_날짜별_총데카도_나온다(self):
        from datetime import datetime, timedelta, timezone

        t0 = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
        cs = [
            cyc(
                (t0 + timedelta(seconds=110 * i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                items=["망령의 영혼석"],
                entry="free",
            )
            for i in range(25)
        ]
        trend = mod.daily_soul_deca(cs, SOUL_WL, SOUL_PRICE)
        # 25판 × 망령 1개 × 105 = 2625 총 데카(하루)
        self.assertAlmostEqual(trend[0]["deca_total"], 25 * 105, places=0)

    def test_재화무료_데카가_갈린다(self):
        from datetime import datetime, timedelta, timezone

        t0 = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
        free = [
            cyc(
                (t0 + timedelta(seconds=110 * i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                items=["망령의 영혼석"],
            )
            for i in range(3)
        ]
        paid = [
            cyc(
                (t0 + timedelta(seconds=110 * (i + 5))).strftime("%Y-%m-%dT%H:%M:%SZ"),
                items=["망령의 영혼석", "룬의 파편"],
            )
            for i in range(2)
        ]
        trend = mod.daily_soul_deca(free + paid, SOUL_WL, SOUL_PRICE, markers=["파편"])
        row = trend[0]
        self.assertAlmostEqual(row["free_deca"], 3 * 105, places=0)
        self.assertAlmostEqual(row["paid_deca"], 2 * 105, places=0)
        self.assertAlmostEqual(row["deca_total"], 5 * 105, places=0)


class DungeonDetail(unittest.TestCase):
    def base(self, n, dungeon, items, start_hours=0, **kw):
        from datetime import datetime, timedelta, timezone

        t0 = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc) + timedelta(
            hours=start_hours
        )
        return [
            cyc(
                (t0 + timedelta(seconds=110 * i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                dungeon=dungeon,
                items=items,
                entry="free",
                **kw,
            )
            for i in range(n)
        ]

    def test_던전_상세가_모인다(self):
        cs = self.base(25, "룬다 1층 2구역", ["망령의 영혼석"])
        d = mod.dungeon_detail(cs, "룬다 1층 2구역", SOUL_WL, SOUL_PRICE, CORR)
        self.assertEqual(d["games"], 25)
        self.assertEqual(d["stem"], "망령")
        self.assertEqual(d["total_count"], 25)
        self.assertAlmostEqual(d["total_deca"], 25 * 105, places=0)
        self.assertAlmostEqual(d["per_game"], 1.0, places=3)
        self.assertTrue(d["daily"])  # 날짜별 추이
        self.assertIn("per_game", d["daily"][0])  # 드랍률 시계열

    def test_없는_던전은_None(self):
        cs = self.base(5, "룬다 1층 2구역", ["망령의 영혼석"])
        self.assertIsNone(
            mod.dungeon_detail(
                cs, "페카 고분 심층 9층 9구역", SOUL_WL, SOUL_PRICE, CORR
            )
        )

    def test_재화무료가_갈린다(self):
        free = self.base(15, "룬다 1층 2구역", ["망령의 영혼석"])
        paid = self.base(
            10, "룬다 1층 2구역", ["망령의 영혼석", "룬의 파편"], start_hours=48
        )
        d = mod.dungeon_detail(
            free + paid, "룬다 1층 2구역", SOUL_WL, SOUL_PRICE, CORR, markers=["파편"]
        )
        self.assertEqual(d["paid"]["games"], 10)
        self.assertEqual(d["free"]["games"], 15)

    def test_날짜별로도_재화무료가_갈린다(self):
        # 하루에 무료 3판·재화 2판이 섞이면 그날 행이 재화/무료로 쪼개진다.
        free = self.base(3, "룬다 1층 2구역", ["망령의 영혼석"])
        paid = self.base(
            2, "룬다 1층 2구역", ["망령의 영혼석", "룬의 파편"], start_hours=2
        )
        d = mod.dungeon_detail(
            free + paid, "룬다 1층 2구역", SOUL_WL, SOUL_PRICE, CORR, markers=["파편"]
        )
        day = d["daily"][0]  # 같은 날
        self.assertEqual(day["free_games"], 3)
        self.assertEqual(day["paid_games"], 2)
        self.assertAlmostEqual(day["free_per_game"], 1.0, places=3)
        self.assertAlmostEqual(day["paid_per_game"], 1.0, places=3)

    def test_전리품이_재화무료로_갈린다(self):
        free = self.base(5, "룬다 1층 2구역", ["망령의 영혼석"])
        paid = self.base(
            5, "룬다 1층 2구역", ["망령의 영혼석", "룬의 파편"], start_hours=48
        )
        d = mod.dungeon_detail(
            free + paid, "룬다 1층 2구역", SOUL_WL, SOUL_PRICE, CORR, markers=["파편"]
        )
        self.assertIn("룬의 파편", d["other_paid"])  # 재화 판에만
        self.assertEqual(d["other_paid"]["룬의 파편"], 5)
        self.assertNotIn("룬의 파편", d["other_free"])

    def test_세션에_재화무료_판수가_붙는다(self):
        free = self.base(4, "룬다 1층 2구역", ["망령의 영혼석"])
        paid = self.base(
            1, "룬다 1층 2구역", ["망령의 영혼석", "룬의 파편"], start_hours=0
        )
        d = mod.dungeon_detail(
            free + paid, "룬다 1층 2구역", SOUL_WL, SOUL_PRICE, CORR, markers=["파편"]
        )
        # 한 세션(연속 구간) 안에 재화/무료 판수가 각각 집계된다.
        tot_paid = sum(s["paid"] for s in d["sessions"])
        tot_free = sum(s["free"] for s in d["sessions"])
        self.assertEqual(tot_paid, 1)
        self.assertEqual(tot_free, 4)

    def test_시간대도_재화무료로_갈린다(self):
        free = self.base(4, "룬다 1층 2구역", ["망령의 영혼석"])
        paid = self.base(
            1, "룬다 1층 2구역", ["망령의 영혼석", "룬의 파편"], start_hours=0
        )
        d = mod.dungeon_detail(
            free + paid, "룬다 1층 2구역", SOUL_WL, SOUL_PRICE, CORR, markers=["파편"]
        )
        # 같은 시(KST 9시)에 재화 1·무료 4가 각각 잡힌다.
        self.assertEqual(sum(d["hours_paid"].values()), 1)
        self.assertEqual(sum(d["hours_free"].values()), 4)

    def test_돌린_구간_세션이_갈린다(self):
        from datetime import datetime, timedelta, timezone

        t0 = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
        secs = [110 * i for i in range(5)]  # 블록1: 5판
        secs += [secs[-1] + 1800 + 110 * i for i in range(1, 6)]  # 30분 갭 뒤 5판
        cs = [
            cyc(
                (t0 + timedelta(seconds=s)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                dungeon="룬다 1층 2구역",
                items=["망령의 영혼석"],
                entry="free",
            )
            for s in secs
        ]
        d = mod.dungeon_detail(cs, "룬다 1층 2구역", SOUL_WL, SOUL_PRICE, CORR)
        self.assertEqual(len(d["sessions"]), 2)  # 20분 넘게 벌어져 두 구간
        self.assertEqual(sum(s["games"] for s in d["sessions"]), 10)


class ExtractTribute(unittest.TestCase):
    def test_뒤끝_증표_조인이_갈린다(self):
        self.assertEqual(
            mod.extract_tribute("모험가 포인트 마물 퇴치 증표"),
            ["모험가 포인트", "마물 퇴치 증표"],
        )

    def test_앞끝_증표_조인이_갈린다_OCR변종(self):
        # 마울(마물)·앞끝. 나머지(시즌 경험치)를 따로 돌린다.
        self.assertEqual(
            mod.extract_tribute("마울 퇴치 증표 시즌 경험치"),
            ["마물 퇴치 증표", "시즌 경험치"],
        )

    def test_증표_단독_변종은_안_가른다(self):
        # 앞뒤에 다른 아이템 없으면 원문 그대로(오독 교정은 classify_slot 몫).
        self.assertEqual(mod.extract_tribute("마울 퇴치 증표"), ["마울 퇴치 증표"])
        self.assertEqual(mod.extract_tribute(". 마물 퇴치 증표"), [". 마물 퇴치 증표"])

    def test_가운데_낀_조인은_안_가른다(self):
        # 양쪽 다 내용이면 분리 사전 몫(우정 [증표] 주머니).
        self.assertEqual(
            mod.extract_tribute("우정 마물 퇴치 증표 주머니(시즌2)"),
            ["우정 마물 퇴치 증표 주머니(시즌2)"],
        )

    def test_증표_없으면_그대로(self):
        self.assertEqual(mod.extract_tribute("망령의 영혼석"), ["망령의 영혼석"])

    def test_조각난_보석_조인이_갈린다(self):
        self.assertEqual(
            mod.split_gems("조각난 사파이어 조각난 토파즈"),
            ["조각난 사파이어", "조각난 토파즈"],
        )
        # 구분 기호·공백 붙어도
        self.assertEqual(
            mod.split_gems("조각난 에메랄드, 조각난 루비"),
            ["조각난 에메랄드", "조각난 루비"],
        )
        # 앞에 다른 아이템이 붙어도 갈린다
        self.assertEqual(
            mod.split_gems("시즌 경험치 조각난 사파이어"),
            ["시즌 경험치", "조각난 사파이어"],
        )
        # 보석 하나면 그대로
        self.assertEqual(mod.split_gems("조각난 다이아몬드"), ["조각난 다이아몬드"])
        self.assertEqual(mod.split_gems("미지의 소울 조각"), ["미지의 소울 조각"])

    def test_소울_순위에서_증표조인이_기타로_안_샌다(self):
        # 파이프라인 통합: '세공된 지르콘Z 마물 퇴치 증표'가 증표+지르콘으로 갈려
        # 조인 이름이 기타 목록에 안 남는다.
        from datetime import datetime, timedelta, timezone

        t0 = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
        cs = [
            cyc(
                (t0 + timedelta(seconds=110 * i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                dungeon="룬다 1층 2구역",
                items=["세공된 지르콘 마물 퇴치 증표"],
                entry="free",
            )
            for i in range(25)
        ]
        r = mod.soul_dungeon_ranking(cs, SOUL_WL, SOUL_PRICE, CORR)
        self.assertNotIn("세공된 지르콘 마물 퇴치 증표", r["other_items"])
        self.assertIn("마물 퇴치 증표", r["other_items"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
