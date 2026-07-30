#!/usr/bin/env python3
"""톤 룰이 실제로 먹히는지 세션 로그에서 측정한다.

rules/tone/tone-kr.md 를 고친 뒤, 사용자가 덜 답답해졌는지·내 문체가 바뀌었는지
`~/.claude/projects/` 의 세션 로그로 확인하는 도구다. 감이 아니라 수치로 판정한다.

사용법
  python3 scripts/measure_tone_effect.py signals
  python3 scripts/measure_tone_effect.py terms
  python3 scripts/measure_tone_effect.py effect  --cut 2026-07-24T17:11
  python3 scripts/measure_tone_effect.py clauses --cut 2026-07-24T17:11
  python3 scripts/measure_tone_effect.py all     --cut 2026-07-24T17:11

옵션
  --project <이름>   ~/.claude/projects/*<이름>*/ 로 매칭. 기본 cube-backend
  --cut <ISO시각>    이 시각 전후로 나눠 비교. effect·clauses 에 필요

배경 (2026-07-30 측정)
  답답함 신호 306/1213건(22.6%). "X가 뭐야"로 막힌 용어 103건 중 84건이
  코드에 없는 한국어 명사구였다. 7/24 문체 섹션 도입 후 문장은 51.1→38.4자로
  짧아졌지만 표는 0.9→1.6행으로 늘고 신호는 11.5→19.6%로 올랐다.
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

PROJECTS_ROOT = os.path.expanduser("~/.claude/projects")

# 사용자가 막혔다는 신호. 카테고리별로 나눠 어느 종류가 많은지 본다.
SIGNALS = {
    "A_이해실패": r"(이게\s*뭐|무슨\s*소리|무슨소리|이해가?\s*안|이해안|모르겠|뭔데|뭐임|뭐냐)",
    "B_재설명요청": r"(다시\s*(설명|말|해)|쉽게|간단하게|간단히|개요부터|풀어서|정리해)",
    "C_부정교정": r"(그게\s*아니|아닌데|틀렸|잘못|말고|왜\s*그렇게|하지\s*말)",
    "D_반복좌절": r"(답답|몇\s*번|자꾸|계속\s*(왜|그|같은)|아까\s*(말|얘기)|또\s*그|왜\s*안)",
    "E_신뢰확인": r"(진짜\s*(맞|했|돼)|정말\s*(맞|했)|확실\s*(해|한)|확인\s*했어|검증\s*했어|했어\?|맞아\?)",
    "F_물음표강조": r"\?\?+",
}

# 위 카테고리를 하나로 합친 것. 비율 추이에 쓴다.
SIGNAL_ANY = re.compile(
    r"(이게\s*뭐|무슨\s*소리|무슨소리|이해가?\s*안|이해안|모르겠|뭔데|뭐냐|"
    r"다시\s*(설명|말|해)|쉽게|간단하게|간단히|개요부터|그게\s*아니|아닌데|"
    r"틀렸|답답|왜\s*자꾸|장황|못\s*읽|\?\?+)"
)

# "X가 뭐야" 에서 X 를 뽑는다. 영문 심볼과 한글 명사구를 구분해 센다.
TERM_RX = re.compile(
    r"([A-Za-z_][\w./:\-]{1,40}|[가-힣][가-힣\s]{0,18})\s*(?:가|이|는|은|을|를)?\s*"
    r"(?:뭐야|뭔데|뭐냐|무슨\s*의미|무슨\s*소리|뭘\s*얘기)"
)
TERM_STOPWORDS = {"그게", "이게", "저게", "그거", "이거", "그건", "이건", "질문이", "e는"}

# 사용자가 직접 지적한 표현. 빈도가 낮아도 내용이 날카로우니 원문을 본다.
DIRECT = {
    "앞뒤 잘라먹": r"앞뒤\s*잘라",
    "레벨/눈높이": r"레벨(을|이|도)?\s*(좀\s*)?(나랑|맞|다르)",
    "장황·길다": r"(장황|너무\s*길|길게|못\s*읽|안\s*읽)",
    "왜 자꾸": r"왜\s*자꾸",
    "요청 안 함": r"(내가\s*[^.]{0,25}(얘기했어|말했어|요청했어|하라고)|요청한\s*(가드|것|게)\s*아니)",
    "확인받고": r"(확인받고|승인받고|물어보고)\s*(작업|해)",
    "쉽게": r"쉽게\s*(설명|말|다시)",
    "개요부터": r"개요부터",
}

# tone-kr.md 조항별 위반 탐지. 위반이 0 에 가까우면 그 조항은 일을 안 하는 것이다.
CLAUSES = {
    "아첨": r"(좋은\s*질문|정확한\s*지적이|훌륭한|예리한|핵심을\s*찌|말씀대로)",
    "서두 상투어": r"^(확인\s*(끝|했|완료)|정리(합니다|해)|알겠습니다[.!]|네[,.]\s)",
    "마무리 상투어": r"(도움이\s*되셨|필요하면\s*말씀|언제든\s*말씀|참고하시)",
    "이모지": r"[\U0001F300-\U0001FAFF✅❌⭐⚠]",
    "번역체": r"(를\s*탐색|심층적|에\s*대해\s*(살펴|알아)|을\s*통해\s*(확인|수행))",
    "후속 제안": r"(원하시면|필요하시면|원한다면)\s*\S*\s*(도|추가|같이|더)",
    "가상 식별자": r"\b(foo|bar|baz|someValue|myVar|exampleFn)\b",
    "질문 2개+": r"\?[^?]*\?[^?]*\?",
    "이중피동": r"(되어(지|졌)|되어질|불리어|보여지)",
    "-것 같다 반복": r"(것\s*같습니다[\s\S]{0,300}것\s*같습니다)",
    "중점 3개+": r"[가-힣A-Za-z0-9)][·][가-힣A-Za-z0-9(][^\n]{0,40}[·][^\n]{0,40}[·]",
    "Insight 박스": r"★\s*Insight",
    "위임 질문": r"(어느\s*방향|어떻게\s*생각하|어떤\s*걸\s*원|선호하시|택하시겠)",
    "지어낸 이름": r"(부호\s*가드|원장\s*술어|범위\s*검사|검수\s*제외|운영자조합)",
}

CONNECTIVES = re.compile(r"(그래서|그런데|즉|따라서|반면|다만|대신|왜냐|그러면|하지만)")
SENT_SPLIT = re.compile(r"[.!?。]\s+|\n")

# 세션 로그에는 시스템이 끼워 넣은 블록도 user 역할로 들어온다. 사용자 발화가 아니다.
INJECTED_PREFIXES = (
    "This session is being continued",
    "Base directory for this skill",
    "Caveat:",
)


def session_files(project):
    pattern = f"{PROJECTS_ROOT}/*{project}*/*.jsonl"
    files = glob.glob(pattern)
    if not files:
        sys.exit(f"세션 로그가 없다: {pattern}")
    return files


def walk(project):
    """(timestamp, role, text) 스트림. sidechain·도구결과·시스템 주입은 걸러낸다."""
    for path in session_files(project):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                    except Exception:
                        continue
                    if entry.get("isSidechain"):
                        continue
                    role = entry.get("type")
                    if role not in ("user", "assistant"):
                        continue
                    content = (entry.get("message") or {}).get("content")
                    if isinstance(content, list):
                        if any(isinstance(b, dict) and b.get("type") == "tool_result"
                               for b in content):
                            continue
                        text = " ".join(b.get("text", "") for b in content
                                        if isinstance(b, dict) and b.get("type") == "text")
                    elif isinstance(content, str):
                        text = content
                    else:
                        continue
                    text = text.strip()
                    if not text or text.startswith("<") or "system-reminder" in text:
                        continue
                    if text.startswith(INJECTED_PREFIXES):
                        continue
                    yield entry.get("timestamp", ""), role, text
        except Exception:
            continue


def collect(project):
    users, assistants = [], []
    for ts, role, text in walk(project):
        (users if role == "user" else assistants).append((ts, text))
    return users, assistants


def cmd_signals(project, cut=None):
    """답답함 신호를 카테고리별로 센다."""
    users, assistants = collect(project)
    # 신호 직전 assistant 응답 길이를 알아야 "길이 탓인가"를 판정할 수 있다.
    timeline = sorted(
        [(ts, "u", t) for ts, t in users] + [(ts, "a", t) for ts, t in assistants]
    )
    prev_len, hits = 0, defaultdict(list)
    compiled = {k: re.compile(v) for k, v in SIGNALS.items()}
    for ts, role, text in timeline:
        if role == "a":
            prev_len = len(text)
            continue
        for cat, rx in compiled.items():
            if rx.search(text):
                hits[cat].append((ts, text, prev_len))

    total = len(users)
    print(f"사용자 발화 {total}건\n")
    print("=== 신호별 빈도 ===")
    for cat in SIGNALS:
        n = len(hits[cat])
        print(f"{cat:14s} {n:5d}건  ({n / max(total, 1) * 100:4.1f}%)")

    flat = [h for v in hits.values() for h in v]
    print(f"\n중복 제외 {len({h[1] for h in flat})}건 "
          f"(전체의 {len({h[1] for h in flat}) / max(total, 1) * 100:.1f}%)")

    lens = sorted(h[2] for h in flat if h[2] > 0)
    if lens:
        print("\n=== 신호 직전 assistant 응답 길이(자) ===")
        print(f"중위 {lens[len(lens) // 2]}, 평균 {sum(lens) // len(lens)}, "
              f"상위10% {lens[int(len(lens) * 0.9)]}, 최대 {lens[-1]}")

    print("\n=== 카테고리별 최근 샘플 ===")
    for cat in SIGNALS:
        recent = sorted(hits[cat], key=lambda x: x[0], reverse=True)[:6]
        if not recent:
            continue
        print(f"\n--- {cat} ({len(hits[cat])}건) ---")
        for ts, text, plen in recent:
            print(f"  [{ts[:10]}] (직전 {plen:5d}자) {' '.join(text.split())[:100]}")


def cmd_terms(project, cut=None):
    """무엇을 못 알아들었나 — 막힌 용어와 직접 지적을 뽑는다."""
    users, _ = collect(project)
    users.sort()

    terms = []
    for ts, text in users:
        for m in TERM_RX.finditer(text):
            term = m.group(1).strip()
            if len(term) < 2 or term in TERM_STOPWORDS:
                continue
            terms.append((ts[:10], term))

    english = [t for _, t in terms if re.match(r"^[A-Za-z_]", t)]
    korean = [t for _, t in terms if not re.match(r"^[A-Za-z_]", t)]
    print(f"=== '~가 뭐야' 로 막힌 용어 {len(terms)}건 ===")
    print(f"  영문 심볼·식별자 {len(english)}건 / 한글 표현 {len(korean)}건")
    print("  한글 표현이 많으면 내가 코드에 없는 이름을 지어냈다는 뜻이다.\n")
    for ts, term in terms[-25:]:
        print(f"  [{ts}] {term}")

    print("\n=== 사용자의 직접 지적 ===")
    for label, pattern in DIRECT.items():
        rx = re.compile(pattern)
        hit = [(ts[:10], " ".join(t.split())[:90]) for ts, t in users if rx.search(t)]
        print(f"\n--- {label}: {len(hit)}건 ---")
        for ts, s in hit[-3:]:
            print(f"    [{ts}] {s}")

    by_month = defaultdict(lambda: [0, 0])
    for ts, text in users:
        if not ts:
            continue
        by_month[ts[:7]][0] += 1
        if SIGNAL_ANY.search(text):
            by_month[ts[:7]][1] += 1
    print("\n=== 월별 답답함 신호 비율 ===")
    for month in sorted(by_month):
        tot, hit = by_month[month]
        if tot < 15:
            continue
        print(f"  {month}  {hit:4d}/{tot:4d}  {hit / tot * 100:5.1f}%  {'█' * int(hit / tot * 40)}")


def _split_by_cut(items, cut):
    before = [(ts, t) for ts, t in items if ts and ts < cut]
    after = [(ts, t) for ts, t in items if ts and ts >= cut]
    return before, after


def cmd_effect(project, cut):
    """기준선 전후로 내 문체와 사용자 신호가 어떻게 달라졌나."""
    users, assistants = collect(project)
    ub, ua = _split_by_cut(users, cut)
    ab, aa = _split_by_cut(assistants, cut)

    def style(msgs):
        if not msgs:
            return {}
        sents, sent_chars, long_sents = 0, 0, 0
        tables, bullets, conns, chars = 0, 0, 0, 0
        for _, text in msgs:
            chars += len(text)
            parts = [s.strip() for s in SENT_SPLIT.split(text) if len(s.strip()) > 3]
            sents += len(parts)
            sent_chars += sum(len(s) for s in parts)
            long_sents += sum(1 for s in parts if len(s) > 50)
            tables += text.count("\n|")
            bullets += len(re.findall(r"^\s*[-*]\s", text, re.M))
            conns += len(CONNECTIVES.findall(text))
        n = len(msgs)
        return {
            "메시지 수": n,
            "응답 평균 길이(자)": chars / n,
            "평균 문장 길이(자)": sent_chars / max(sents, 1),
            "50자 초과 문장 비율": long_sents / max(sents, 1) * 100,
            "응답당 표 행 수": tables / n,
            "응답당 불릿 수": bullets / n,
            "응답당 이음말 수": conns / n,
        }

    sb, sa = style(ab), style(aa)
    print(f"기준선 {cut}\n")
    header = f"{'지표':<26}{'전':>11}{'후':>11}{'변화':>9}"
    print(header)
    print("-" * (len(header) + 4))
    for key in sb:
        a, c = sb[key], sa.get(key, 0)
        change = "n/a" if not a else f"{'↑' if c > a else '↓'}{abs((c - a) / a * 100):.0f}%"
        print(f"{key:<26}{a:>11.1f}{c:>11.1f}{change:>9}")

    print("-" * (len(header) + 4))
    for label, group in (("전", ub), ("후", ua)):
        sig = sum(1 for _, t in group if SIGNAL_ANY.search(t))
        rate = sig / max(len(group), 1) * 100
        print(f"  {label}: 사용자 발화 {len(group):4d}건 / 답답함 신호 {sig:4d}건 ({rate:.1f}%)")
    print("\n  문장이 짧아졌는데 신호가 늘었다면, 한 축을 누른 압력이")
    print("  다른 축(표·불릿)으로 새어나갔을 가능성을 본다.")


def cmd_clauses(project, cut):
    """조항별 위반율. 0 에 가까운 조항은 삭제 후보다."""
    _, assistants = collect(project)
    ab, aa = _split_by_cut(assistants, cut)
    compiled = {k: re.compile(v, re.M) for k, v in CLAUSES.items()}

    counts = {"before": Counter(), "after": Counter()}
    for bucket, msgs in (("before", ab), ("after", aa)):
        for _, text in msgs:
            for name, rx in compiled.items():
                if rx.search(text):
                    counts[bucket][name] += 1

    print(f"기준선 {cut}")
    print(f"assistant 응답 — 전 {len(ab)}건, 후 {len(aa)}건\n")
    header = f"{'조항':<18}{'전':>8}{'후':>8}{'후 위반율':>11}   판정"
    print(header)
    print("-" * (len(header) + 12))
    rows = []
    for name in CLAUSES:
        bf, af = counts["before"][name], counts["after"][name]
        rows.append((af / max(len(aa), 1) * 100, name, bf, af))
    for rate, name, bf, af in sorted(rows):
        if rate < 0.5:
            verdict = "거의 안 어김 → 삭제 후보"
        elif rate < 3:
            verdict = "드묾"
        else:
            verdict = "자주 어김 → 문안 문제"
        print(f"{name:<18}{bf:>8}{af:>8}{rate:>10.1f}%   {verdict}")


COMMANDS = {
    "signals": cmd_signals,
    "terms": cmd_terms,
    "effect": cmd_effect,
    "clauses": cmd_clauses,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=list(COMMANDS) + ["all"])
    ap.add_argument("--project", default="cube-backend",
                    help="~/.claude/projects/*<이름>*/ 매칭 (기본 cube-backend)")
    ap.add_argument("--cut", help="ISO 시각. effect·clauses 에 필요")
    args = ap.parse_args()

    needs_cut = {"effect", "clauses"}
    if args.command in needs_cut and not args.cut:
        sys.exit(f"{args.command} 는 --cut 이 필요하다 (예: --cut 2026-07-24T17:11)")

    todo = list(COMMANDS) if args.command == "all" else [args.command]
    for i, name in enumerate(todo):
        if args.command == "all":
            if name in needs_cut and not args.cut:
                continue
            print(f"\n{'=' * 60}\n{name}\n{'=' * 60}")
        elif i:
            print()
        COMMANDS[name](args.project, args.cut)


if __name__ == "__main__":
    main()
