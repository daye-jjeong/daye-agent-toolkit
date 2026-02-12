#!/usr/bin/env python3
"""
Health Coach - AI-powered health advisor.

Obsidian vault (~/openclaw/vault/health/) 에서 데이터를 읽어
운동 루틴 추천, 증상 분석, 운동 가이드, 생활 조언을 제공한다.
stdlib만 사용.
"""

import json
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# health_io는 같은 scripts/ 디렉토리에 위치
sys.path.insert(0, str(Path(__file__).parent))
import health_io


class HealthCoach:
    def __init__(self):
        self.skill_dir = Path(__file__).parent.parent
        self.exercises_db = self._load_exercises()

    def _load_exercises(self):
        """Load exercise database from config/exercises.json."""
        exercises_path = self.skill_dir / "config" / "exercises.json"
        try:
            with open(exercises_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Exercise database not found: {exercises_path}", file=sys.stderr)
            sys.exit(1)

    # ── suggest-routine ─────────────────────────────────
    def suggest_routine(self, duration=15, focus="core", level="beginner"):
        """Suggest a safe exercise routine based on focus area and level."""
        focus_map = {
            "core": "core_stability",
            "lower": "lower_body",
            "flexibility": "flexibility",
            "cardio": "cardio_low_impact",
        }
        category_key = focus_map.get(focus, "core_stability")
        exercises = self.exercises_db.get(category_key, [])

        # Also read recent exercise entries from Obsidian to show context
        recent = health_io.read_entries("exercises", days=3)

        print(f"\n{duration}min {focus} routine (level: {level})")
        print("=" * 60)

        if recent:
            print(f"\n[recent exercises - last 3 days: {len(recent)} entries]")
            for _, fm in recent[-3:]:
                print(f"  - {fm.get('date', '?')}: {fm.get('name', fm.get('exercise', '?'))}")

        # Filter by level
        filtered = [
            ex
            for ex in exercises
            if ex.get("level") == level or ex.get("level") == "all"
        ]
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
        print("  - Maintain neutral spine (no hyperextension/flexion)")
        print("  - Breathe with movement (never hold breath)")
        print("  - Stop immediately if pain occurs")
        print("  - Increase intensity gradually")
        print("  - Rest when fatigued")

    # ── analyze-symptoms ────────────────────────────────
    def analyze_symptoms(self, period="7days"):
        """Analyze symptom patterns from Obsidian health/symptoms/ data."""
        days = int(period.replace("days", ""))
        entries = health_io.read_entries("symptoms", days=days)

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        print(f"\nSymptom analysis: {start_date} ~ {end_date}")
        print("=" * 60)

        if not entries:
            print(f"\nNo symptom records found in the last {days} days.")
            print("Record symptoms via health-tracker to enable analysis.")
            print(f"\nVault path: {health_io.CATEGORIES['symptoms']}")
            return

        # Aggregate stats
        symptom_counts = {}
        severity_sums = {}
        locations = {}
        for _, fm in entries:
            name = fm.get("symptom", fm.get("name", "unknown"))
            symptom_counts[name] = symptom_counts.get(name, 0) + 1
            sev = fm.get("severity", fm.get("intensity", 0))
            if isinstance(sev, (int, float)):
                severity_sums[name] = severity_sums.get(name, 0) + sev
            loc = fm.get("location", "")
            if loc:
                locations[loc] = locations.get(loc, 0) + 1

        print(f"\nTotal symptom records: {len(entries)}")

        print("\nSymptom frequency:")
        for name, count in sorted(symptom_counts.items(), key=lambda x: -x[1]):
            avg_sev = severity_sums.get(name, 0) / count if count else 0
            print(f"  {name}: {count}x (avg severity: {avg_sev:.1f}/10)")

        if locations:
            print("\nAffected locations:")
            for loc, count in sorted(locations.items(), key=lambda x: -x[1]):
                print(f"  {loc}: {count}x")

        print("\nAdvice:")
        print("  - Record symptoms immediately when they occur")
        print("  - Note triggers: activity, posture, stress")
        print("  - Need at least 2 weeks of data for pattern analysis")

    # ── guide-exercise ──────────────────────────────────
    def guide_exercise(self, exercise_name, level="beginner"):
        """Provide detailed exercise guide."""
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

        print("\n" + "=" * 60)
        print("\nTips:")
        print("  - Check form in a mirror")
        print("  - Stay within pain-free range")
        print("  - Move slowly with control")
        print("  - Increase intensity weekly")

    # ── lifestyle-advice ────────────────────────────────
    def lifestyle_advice(self, category="sleep"):
        """Provide lifestyle guidance for a specific category."""
        advice = {
            "sleep": {
                "title": "Sleep Optimization (Spinal Health)",
                "tips": [
                    "Side sleeping (pillow between knees)",
                    "Mattress: medium firmness",
                    "Pillow height: keep neck/spine aligned",
                    "No prone sleeping (hyperextends lumbar)",
                    "Light stretching before bed (child's pose)",
                    "Consistent sleep schedule (7-8 hours)",
                    "Room temperature: 18-20C",
                ],
                "avoid": [
                    "Hard floor",
                    "Pillow too high",
                    "Prone sleeping",
                    "Late-night screen time",
                ],
            },
            "diet": {
                "title": "Spinal Health Diet",
                "tips": [
                    "Anti-inflammatory: salmon, nuts, blueberries, leafy greens",
                    "Calcium: milk, cheese, broccoli, almonds",
                    "Vitamin D: sunlight, salmon, eggs",
                    "Protein: muscle recovery (chicken, tofu, beans)",
                    "Omega-3: reduce inflammation (oily fish, flaxseed)",
                    "Hydration: 2L+ daily (disc hydration)",
                    "Magnesium: muscle relaxation (spinach, banana)",
                ],
                "avoid": [
                    "Processed food",
                    "Excess sugar",
                    "Trans fats",
                    "Too much caffeine",
                ],
            },
            "posture": {
                "title": "Daily Posture Correction",
                "tips": [
                    "Sitting: lumbar support, feet flat on floor",
                    "Chair height: knees at 90deg, feet on ground",
                    "Monitor: eye level, arm's length away",
                    "Stand/stretch every 30 minutes",
                    "Lifting: bend knees, keep object close",
                    "Standing: distribute weight evenly",
                    "Driving: backrest at 100-110deg",
                ],
                "avoid": [
                    "Prolonged sitting",
                    "Bending to lift",
                    "Leaning to one side",
                    "Crossing legs",
                ],
            },
            "stress": {
                "title": "Stress Management",
                "tips": [
                    "Breathing: diaphragmatic breathing 5 min",
                    "Meditation: 10 min mindfulness daily",
                    "Walking: 20-30 min in nature",
                    "Hobbies: focus on activities you enjoy",
                    "Social connection: time with friends/family",
                    "Sleep: sufficient rest",
                    "Set limits: do only what you can",
                ],
                "avoid": [
                    "Overwork",
                    "Sleep deprivation",
                    "Excess caffeine",
                    "Social isolation",
                ],
            },
        }

        if category not in advice:
            print(f"Unknown category: {category}")
            print("Available: sleep, diet, posture, stress")
            return

        info = advice[category]
        print(f"\n{info['title']}")
        print("=" * 60)

        # Show relevant check-in data if available
        checkins = health_io.read_entries("check-ins", days=7)
        if checkins and category == "sleep":
            sleep_data = [
                fm.get("sleep_hours")
                for _, fm in checkins
                if fm.get("sleep_hours") is not None
            ]
            if sleep_data:
                avg = sum(sleep_data) / len(sleep_data)
                print(f"\n[Your avg sleep last 7 days: {avg:.1f}h]")

        print("\nRecommendations:")
        for tip in info["tips"]:
            print(f"  - {tip}")

        print("\nAvoid:")
        for avoid in info["avoid"]:
            print(f"  - {avoid}")

        print("\n" + "=" * 60)
        print("\nStart with small changes: one habit at a time, 2 weeks to build.")

    # ── health-checkup ──────────────────────────────────
    def health_checkup(self):
        """Comprehensive health check using today's Obsidian data."""
        print("\nComprehensive Health Check")
        print("=" * 60)

        # Try to read today's check-in
        today_str = health_io.today()
        checkins = health_io.read_entries("check-ins", days=1)
        today_data = None
        for _, fm in checkins:
            if str(fm.get("date", "")) == today_str:
                today_data = fm
                break

        if today_data:
            print(f"\nToday's check-in ({today_str}):")
            for key in ["sleep_hours", "sleep_quality", "steps", "workout",
                        "stress", "water", "notes"]:
                val = today_data.get(key)
                if val is not None:
                    print(f"  {key}: {val}")
        else:
            print(f"\nNo check-in recorded for today ({today_str}).")
            print("Use track_health.py to record your daily metrics.")

        # Recent symptoms
        symptoms = health_io.read_entries("symptoms", days=3)
        if symptoms:
            print(f"\nRecent symptoms (last 3 days): {len(symptoms)}")
            for _, fm in symptoms[-3:]:
                name = fm.get("symptom", fm.get("name", "?"))
                sev = fm.get("severity", "?")
                print(f"  - {fm.get('date', '?')}: {name} (severity: {sev})")

        # Checklist
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
                elif label == "Hydration" and (today_data.get("water", 0) or 0) >= 1500:
                    status = "x"
                elif label == "Sleep" and (today_data.get("sleep_hours", 0) or 0) >= 7:
                    status = "x"
            print(f"  [{status}] {question}")

        print("\n" + "=" * 60)
        print("\nImprovement suggestions:")
        print("  - Not enough exercise -> Start 15-min core routine")
        print("  - Poor posture -> Lumbar support, adjust monitor height")
        print("  - Pain present -> Record in health-tracker, rest")
        print("  - Sleep deficit -> Set consistent sleep schedule")


def main():
    parser = argparse.ArgumentParser(
        description="Health Coach - AI-powered health advisor (Obsidian-backed)"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # suggest-routine
    rp = subparsers.add_parser("suggest-routine", help="Suggest exercise routine")
    rp.add_argument("--duration", type=int, default=15, help="Duration in minutes")
    rp.add_argument(
        "--focus",
        choices=["core", "lower", "flexibility", "cardio"],
        default="core",
    )
    rp.add_argument(
        "--level",
        choices=["beginner", "intermediate", "advanced"],
        default="beginner",
    )

    # analyze-symptoms
    sp = subparsers.add_parser("analyze-symptoms", help="Analyze symptom patterns")
    sp.add_argument(
        "--period", default="7days", help="Analysis period (e.g., 7days, 14days)"
    )

    # guide-exercise
    gp = subparsers.add_parser("guide-exercise", help="Detailed exercise guide")
    gp.add_argument("--exercise", required=True, help="Exercise name")
    gp.add_argument(
        "--level",
        choices=["beginner", "intermediate", "advanced"],
        default="beginner",
    )

    # lifestyle-advice
    lp = subparsers.add_parser("lifestyle-advice", help="Lifestyle guidance")
    lp.add_argument(
        "--category",
        choices=["sleep", "diet", "posture", "stress"],
        required=True,
    )

    # health-checkup
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
