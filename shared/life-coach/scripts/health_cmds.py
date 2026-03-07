#!/usr/bin/env python3
"""Health commands — exercise routines, symptom analysis, guides, lifestyle advice, checkup.

Migrated from health-coach/scripts/coach.py. Data source: SQLite.
"""

import json
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import (get_conn, query_exercises, query_symptoms,
                query_check_ins)

_REFS_DIR = Path(__file__).resolve().parent.parent / "references"


class HealthCoach:
    def __init__(self):
        self.exercises_db = self._load_exercises()

    def _load_exercises(self):
        exercises_path = _REFS_DIR / "exercises.json"
        try:
            with open(exercises_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Exercise database not found: {exercises_path}", file=sys.stderr)
            sys.exit(1)

    def suggest_routine(self, duration=15, focus="core", level="beginner"):
        focus_map = {
            "core": "core_stability", "lower": "lower_body",
            "flexibility": "flexibility", "cardio": "cardio_low_impact",
        }
        category_key = focus_map.get(focus, "core_stability")
        exercises = self.exercises_db.get(category_key, [])

        today = datetime.now().strftime("%Y-%m-%d")
        since = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        conn = get_conn()
        try:
            recent = query_exercises(conn, since, today)
        finally:
            conn.close()

        print(f"\n{duration}min {focus} routine (level: {level})")
        print("=" * 60)

        if recent:
            print(f"\n[recent exercises - last 3 days: {len(recent)} entries]")
            for e in recent[-3:]:
                print(f"  - {e['date']}: {e.get('type', '?')}")

        filtered = [ex for ex in exercises if ex.get("level") == level or ex.get("level") == "all"]
        if not filtered:
            filtered = exercises

        num_exercises = min(3 if duration <= 15 else 4, len(filtered))
        selected = filtered[:num_exercises]

        print("\nRecommended exercises:\n")
        for i, ex in enumerate(selected, 1):
            print(f"{i}. {ex['name']}")
            print(f"   Target: {ex['target']}")
            if "sets_reps" in ex:
                print(f"   Sets: {ex['sets_reps']}")
            elif "duration" in ex:
                print(f"   Duration: {ex['duration']}")
            print(f"   How: {ex['description']}")
            print(f"   Breathing: {ex.get('breathing', 'N/A')}")
            print(f"   Caution: {ex['caution']}")
            print()

        print("AVOID these movements (disk herniation precaution):")
        for avoid in self.exercises_db.get("avoid", [])[:3]:
            print(f"  X {avoid['name']}: {avoid['reason']}")

        print("\n" + "=" * 60)
        print("\nSafety rules:")
        print("  - Maintain neutral spine")
        print("  - Breathe with movement")
        print("  - Stop immediately if pain occurs")
        print("  - Increase intensity gradually")

    def analyze_symptoms(self, period="7days"):
        days = int(period.replace("days", ""))
        today = datetime.now().strftime("%Y-%m-%d")
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        conn = get_conn()
        try:
            entries = query_symptoms(conn, since, today)
        finally:
            conn.close()

        print(f"\nSymptom analysis: {since} ~ {today}")
        print("=" * 60)

        if not entries:
            print(f"\nNo symptom records found in the last {days} days.")
            return

        symptom_counts = {}
        severity_counts = {}
        for e in entries:
            name = e["type"]
            symptom_counts[name] = symptom_counts.get(name, 0) + 1
            sev = e.get("severity", "")
            severity_counts.setdefault(name, []).append(sev)

        print(f"\nTotal symptom records: {len(entries)}")
        print("\nSymptom frequency:")
        for name, count in sorted(symptom_counts.items(), key=lambda x: -x[1]):
            sevs = severity_counts.get(name, [])
            print(f"  {name}: {count}x (severities: {', '.join(sevs)})")

    def guide_exercise(self, exercise_name, level="beginner"):
        print(f"\n{exercise_name} - Detailed Guide")
        print("=" * 60)

        found = None
        for category in ["core_stability", "lower_body", "flexibility", "cardio_low_impact"]:
            for ex in self.exercises_db.get(category, []):
                if exercise_name.lower() in ex["name"].lower():
                    found = ex
                    break
            if found:
                break

        if not found:
            print(f"\nExercise not found: {exercise_name}")
            print("\nAvailable exercises:")
            for cat in ["core_stability", "lower_body", "flexibility", "cardio_low_impact"]:
                for ex in self.exercises_db.get(cat, []):
                    print(f"  - {ex['name']}")
            return

        print(f"\nName: {found['name']}")
        print(f"Level: {found['level']}")
        print(f"Target: {found['target']}")
        if "sets_reps" in found:
            print(f"\nSets/Reps: {found['sets_reps']}")
        elif "duration" in found:
            print(f"\nDuration: {found['duration']}")
        print(f"\nHow to perform:\n  {found['description']}")
        print(f"\nBreathing:\n  {found['breathing']}")
        print(f"\nCaution:\n  {found['caution']}")
        if "progression" in found:
            print(f"\nProgression:\n  {found['progression']}")
        if "common_mistakes" in found:
            print("\nCommon mistakes:")
            for mistake in found["common_mistakes"]:
                print(f"  - {mistake}")

    def lifestyle_advice(self, category="sleep"):
        advice = {
            "sleep": {
                "title": "Sleep Optimization (Spinal Health)",
                "tips": ["Side sleeping (pillow between knees)", "Mattress: medium firmness",
                         "Pillow height: keep neck/spine aligned", "No prone sleeping",
                         "Light stretching before bed", "Consistent sleep schedule (7-8 hours)",
                         "Room temperature: 18-20C"],
                "avoid": ["Hard floor", "Pillow too high", "Prone sleeping", "Late-night screen time"],
            },
            "diet": {
                "title": "Spinal Health Diet",
                "tips": ["Anti-inflammatory: salmon, nuts, blueberries", "Calcium: milk, cheese, broccoli",
                         "Vitamin D: sunlight, salmon, eggs", "Protein: muscle recovery",
                         "Omega-3: reduce inflammation", "Hydration: 2L+ daily"],
                "avoid": ["Processed food", "Excess sugar", "Trans fats", "Too much caffeine"],
            },
            "posture": {
                "title": "Daily Posture Correction",
                "tips": ["Sitting: lumbar support, feet flat", "Monitor: eye level, arm's length",
                         "Stand/stretch every 30 minutes", "Lifting: bend knees, keep object close"],
                "avoid": ["Prolonged sitting", "Bending to lift", "Crossing legs"],
            },
            "stress": {
                "title": "Stress Management",
                "tips": ["Breathing: diaphragmatic 5 min", "Meditation: 10 min daily",
                         "Walking: 20-30 min in nature", "Set limits: do only what you can"],
                "avoid": ["Overwork", "Sleep deprivation", "Social isolation"],
            },
        }

        if category not in advice:
            print(f"Unknown category: {category}")
            print("Available: sleep, diet, posture, stress")
            return

        info = advice[category]
        print(f"\n{info['title']}")
        print("=" * 60)

        if category == "sleep":
            today = datetime.now().strftime("%Y-%m-%d")
            since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            conn = get_conn()
            try:
                checkins = query_check_ins(conn, since, today)
            finally:
                conn.close()
            sleep_data = [c["sleep_hours"] for c in checkins if c.get("sleep_hours")]
            if sleep_data:
                avg = sum(sleep_data) / len(sleep_data)
                print(f"\n[Your avg sleep last 7 days: {avg:.1f}h]")

        print("\nRecommendations:")
        for tip in info["tips"]:
            print(f"  - {tip}")
        print("\nAvoid:")
        for avoid in info["avoid"]:
            print(f"  - {avoid}")

    def health_checkup(self):
        print("\nComprehensive Health Check")
        print("=" * 60)

        today = datetime.now().strftime("%Y-%m-%d")
        conn = get_conn()
        try:
            checkins = query_check_ins(conn, today, today)
            today_data = checkins[0] if checkins else None

            since_3d = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
            symptoms = query_symptoms(conn, since_3d, today)
        finally:
            conn.close()

        if today_data:
            print(f"\nToday's check-in ({today}):")
            for key in ["sleep_hours", "sleep_quality", "steps", "workout", "stress", "water_ml", "notes"]:
                val = today_data.get(key)
                if val is not None:
                    print(f"  {key}: {val}")
        else:
            print(f"\nNo check-in recorded for today ({today}).")
            print("Use track_health.py to record your daily metrics.")

        if symptoms:
            print(f"\nRecent symptoms (last 3 days): {len(symptoms)}")
            for s in symptoms[-3:]:
                print(f"  - {s['date']}: {s['type']} (severity: {s['severity']})")

        print("\nDaily checklist:")
        items = [
            ("Exercise", "Did you move for 15+ minutes today?"),
            ("Posture", "Did you use lumbar support while sitting?"),
            ("Stretching", "Did you stand/stretch every 30 minutes?"),
            ("Hydration", "Did you drink 1.5L+ water?"),
            ("Sleep", "Did you sleep 7+ hours last night?"),
            ("Pain", "Did you have back pain today?"),
            ("Stress", "Did you spend time managing stress?"),
        ]
        for label, question in items:
            status = " "
            if today_data:
                if label == "Exercise" and today_data.get("workout"):
                    status = "x"
                elif label == "Hydration" and (today_data.get("water_ml", 0) or 0) >= 1500:
                    status = "x"
                elif label == "Sleep" and (today_data.get("sleep_hours", 0) or 0) >= 7:
                    status = "x"
            print(f"  [{status}] {question}")


def main():
    parser = argparse.ArgumentParser(description="Health Coach commands (SQLite-backed)")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    rp = subparsers.add_parser("suggest-routine", help="Suggest exercise routine")
    rp.add_argument("--duration", type=int, default=15)
    rp.add_argument("--focus", choices=["core", "lower", "flexibility", "cardio"], default="core")
    rp.add_argument("--level", choices=["beginner", "intermediate", "advanced"], default="beginner")

    sp = subparsers.add_parser("analyze-symptoms", help="Analyze symptom patterns")
    sp.add_argument("--period", default="7days")

    gp = subparsers.add_parser("guide-exercise", help="Detailed exercise guide")
    gp.add_argument("--exercise", required=True)
    gp.add_argument("--level", choices=["beginner", "intermediate", "advanced"], default="beginner")

    lp = subparsers.add_parser("lifestyle-advice", help="Lifestyle guidance")
    lp.add_argument("--category", choices=["sleep", "diet", "posture", "stress"], required=True)

    subparsers.add_parser("health-checkup", help="Comprehensive health check")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    coach = HealthCoach()
    if args.command == "suggest-routine":
        coach.suggest_routine(args.duration, args.focus, args.level)
    elif args.command == "analyze-symptoms":
        coach.analyze_symptoms(args.period)
    elif args.command == "guide-exercise":
        coach.guide_exercise(args.exercise, args.level)
    elif args.command == "lifestyle-advice":
        coach.lifestyle_advice(args.category)
    elif args.command == "health-checkup":
        coach.health_checkup()


if __name__ == "__main__":
    main()
