#!/usr/bin/env python3
"""
Task Dashboard Generator v2 for clawd system
Goal hierarchy: Monthly → Weekly → Daily with project linking
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
import yaml


class TaskDashboardGenerator:
    """Generates HTML dashboard with goal hierarchy and project linking"""

    def __init__(self, config_path="config.json", output_dir=None):
        self.config = self._load_config(config_path)
        if output_dir:
            self.config["output_dir"] = output_dir
        self.tasks = []
        self.projects = set()
        self.owners = set()
        self.project_meta = {}
        self.goals = {'monthly': None, 'weekly': None, 'daily': None}
        self.script_dir = Path(__file__).parent.absolute()

    def _load_config(self, config_path):
        config_file = Path(config_path)
        if not config_file.exists():
            config_file = Path(__file__).parent / config_path
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {}
        defaults = {
            "projects_root": "../../projects",
            "output_dir": "../../docs/dashboard",
            "refresh_interval_sec": 0,
            "language": "ko"
        }
        for k, v in defaults.items():
            if k not in config:
                config[k] = v
        return config

    def _resolve_path(self, relative_path):
        """Resolve relative paths from script directory (without following symlinks)"""
        path = Path(relative_path)
        if path.is_absolute():
            return path
        return Path(os.path.normpath(self.script_dir / path))

    def scan_projects(self):
        projects_root = self._resolve_path(self.config["projects_root"])
        if not projects_root.exists():
            print(f"Error: Projects root directory not found: {projects_root}", file=sys.stderr)
            return False

        for project_dir in sorted(projects_root.iterdir()):
            if not project_dir.is_dir() or project_dir.name.startswith('_'):
                continue
            tasks_file = project_dir / "tasks.yml"
            if not tasks_file.exists():
                continue

            project_name = project_dir.name
            self.projects.add(project_name)

            try:
                with open(tasks_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)

                self.project_meta[project_name] = {
                    'description': data.get('description', '') if data else '',
                }

                if data and 'tasks' in data:
                    for task in data['tasks']:
                        if task:
                            task['project'] = project_name
                            task['projectType'] = 'work' if project_name.startswith('work--') else 'personal'
                            task['status'] = self._normalize_status(task.get('status', 'todo'))
                            owner = task.get('owner', 'unassigned')
                            task['owner'] = owner
                            self.owners.add(owner)
                            self.tasks.append(task)
            except Exception as e:
                print(f"Warning: Could not parse {tasks_file}: {e}", file=sys.stderr)

        return True

    def scan_goals(self):
        goals_root = self._resolve_path(
            self.config.get("goals_root", self.config["projects_root"] + "/_goals")
        )
        if not goals_root.exists():
            return

        now = datetime.now()

        monthly_file = goals_root / f"{now.strftime('%Y-%m')}.yml"
        if monthly_file.exists():
            try:
                with open(monthly_file, 'r', encoding='utf-8') as f:
                    self.goals['monthly'] = yaml.safe_load(f)
            except Exception as e:
                print(f"Warning: Could not parse {monthly_file}: {e}", file=sys.stderr)

        iso_year, iso_week, _ = now.isocalendar()
        weekly_file = goals_root / f"{iso_year}-W{iso_week:02d}.yml"
        if weekly_file.exists():
            try:
                with open(weekly_file, 'r', encoding='utf-8') as f:
                    self.goals['weekly'] = yaml.safe_load(f)
            except Exception as e:
                print(f"Warning: Could not parse {weekly_file}: {e}", file=sys.stderr)

        daily_file = goals_root / f"{now.strftime('%Y-%m-%d')}.yml"
        if daily_file.exists():
            try:
                with open(daily_file, 'r', encoding='utf-8') as f:
                    self.goals['daily'] = yaml.safe_load(f)
            except Exception as e:
                print(f"Warning: Could not parse {daily_file}: {e}", file=sys.stderr)

    def _calc_kr_percent(self, kr):
        import re
        if isinstance(kr, str):
            return None
        current_raw = kr.get('current', '')
        target_raw = kr.get('target', '')
        current = str(current_raw).strip() if current_raw is not None else ''
        target = str(target_raw).strip() if target_raw is not None else ''
        if not current or current == '0':
            return 0
        if current in ('완료', 'done', 'Done'):
            return 100
        if current in ('진행중', '진행 중', 'in_progress', 'In Progress'):
            return 50
        t_nums = re.findall(r'[\d.]+', target)
        c_nums = re.findall(r'[\d.]+', current)
        if t_nums and c_nums:
            try:
                t = float(t_nums[0])
                c = float(c_nums[0])
                if t > 0:
                    return min(100, round(c / t * 100))
            except (ValueError, TypeError):
                pass
        return 0

    def _prepare_goals_data(self):
        result = {}
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        project_to_monthly = {}
        project_to_weekly = {}

        # --- Monthly (sorted by priority) ---
        m = self.goals.get('monthly')
        if m and 'goals' in m:
            sorted_goals = sorted(m['goals'],
                key=lambda g: priority_order.get(g.get('priority', 'low'), 2))
            monthly_goals = []
            total_pct = 0
            kr_count = 0
            for g in sorted_goals:
                project_to_monthly[g.get('project', '')] = g.get('title', '')
                goal_info = {
                    'title': g.get('title', ''),
                    'project': g.get('project', ''),
                    'priority': g.get('priority', 'low'),
                    'key_results': []
                }
                for kr in g.get('key_results', []):
                    if isinstance(kr, dict):
                        pct = self._calc_kr_percent(kr)
                        goal_info['key_results'].append({
                            'description': kr.get('description', ''),
                            'percent': pct if pct is not None else 0,
                            'target': str(kr.get('target', '')),
                            'current': str(kr.get('current', ''))
                        })
                        if pct is not None:
                            total_pct += pct
                            kr_count += 1
                monthly_goals.append(goal_info)

            result['monthly'] = {
                'month': m.get('month', ''),
                'theme': m.get('theme', ''),
                'percent': round(total_pct / kr_count) if kr_count > 0 else 0,
                'completed_krs': sum(1 for g in monthly_goals for kr in g['key_results'] if kr['percent'] == 100),
                'total_krs': kr_count,
                'goals': monthly_goals
            }

        # --- Weekly (sorted by priority, linked to monthly) ---
        w = self.goals.get('weekly')
        if w and 'goals' in w:
            sorted_goals = sorted(w['goals'],
                key=lambda g: priority_order.get(g.get('priority', 'low'), 2))
            weekly_goals = []
            status_scores = {'done': 100, 'in_progress': 50, 'todo': 0}
            total_score = 0
            for g in sorted_goals:
                proj = g.get('project', '')
                project_to_weekly[proj] = g.get('title', '')
                status = g.get('status', 'todo')
                total_score += status_scores.get(status, 0)
                krs = g.get('key_results', [])
                weekly_goals.append({
                    'title': g.get('title', ''),
                    'project': proj,
                    'priority': g.get('priority', 'medium'),
                    'status': status,
                    'monthly_goal': project_to_monthly.get(proj, ''),
                    'key_results': [
                        kr if isinstance(kr, str) else kr.get('description', '')
                        for kr in krs
                    ]
                })

            result['weekly'] = {
                'week': w.get('week', ''),
                'period': w.get('period', ''),
                'percent': round(total_score / len(weekly_goals)) if weekly_goals else 0,
                'done_goals': sum(1 for g in weekly_goals if g['status'] == 'done'),
                'total_goals': len(weekly_goals),
                'goals': weekly_goals
            }

        # --- Daily (linked to weekly/monthly) ---
        d = self.goals.get('daily')
        if d:
            top3 = []
            top3_done = 0
            for item in d.get('top3', []):
                status = item.get('status', 'todo')
                if status == 'done':
                    top3_done += 1
                proj = item.get('project', '')
                top3.append({
                    'title': item.get('title', ''),
                    'project': proj,
                    'status': status,
                    'weekly_goal': project_to_weekly.get(proj, ''),
                    'monthly_goal': project_to_monthly.get(proj, '')
                })

            time_blocks = [
                {'time': b.get('time', ''), 'task': b.get('task', ''), 'category': b.get('category', 'work')}
                for b in d.get('time_blocks', [])
            ]

            checklist = []
            checklist_done = 0
            for item in d.get('checklist', []):
                done = item.get('done', False)
                if done:
                    checklist_done += 1
                checklist.append({'task': item.get('task', ''), 'done': done})

            total_items = len(top3) + len(checklist)
            done_items = top3_done + checklist_done
            result['daily'] = {
                'date': d.get('date', ''),
                'day_of_week': d.get('day_of_week', ''),
                'energy_level': d.get('energy_level', 'medium'),
                'percent': round(done_items / total_items * 100) if total_items > 0 else 0,
                'done': done_items,
                'total': total_items,
                'top3': top3,
                'time_blocks': time_blocks,
                'checklist': checklist
            }

        # --- Project detail data ---
        project_data = {}
        for proj_name in self.projects:
            proj_tasks = [t for t in self.tasks if t['project'] == proj_name]
            done_tasks = [t for t in proj_tasks if t['status'] == 'Done']
            project_data[proj_name] = {
                'name': proj_name.replace('work--', '').replace('personal--', ''),
                'type': 'work' if proj_name.startswith('work--') else 'personal',
                'description': self.project_meta.get(proj_name, {}).get('description', ''),
                'monthly_goal': project_to_monthly.get(proj_name, ''),
                'weekly_goal': project_to_weekly.get(proj_name, ''),
                'task_counts': {
                    'total': len(proj_tasks),
                    'done': len(done_tasks),
                    'in_progress': len([t for t in proj_tasks if t['status'] == 'In Progress']),
                },
                'all_tasks': [
                    {'title': t.get('title', ''), 'status': t['status'],
                     'priority': t.get('priority', ''), 'owner': t.get('owner', '')}
                    for t in proj_tasks
                ],
                'history': [
                    {'title': t.get('title', ''),
                     'completed': str(t.get('completed', t.get('deadline', '')))}
                    for t in done_tasks
                ]
            }
        result['projects'] = project_data

        # Annotate tasks with goal links
        for task in self.tasks:
            task['monthly_goal'] = project_to_monthly.get(task.get('project', ''), '')
            task['weekly_goal'] = project_to_weekly.get(task.get('project', ''), '')

        return result

    def _normalize_status(self, status):
        mapping = {
            'todo': 'Not Started', 'in_progress': 'In Progress',
            'done': 'Done', 'blocked': 'Blocked',
            'Not Started': 'Not Started', 'In Progress': 'In Progress',
            'Done': 'Done', 'Blocked': 'Blocked'
        }
        return mapping.get(status, status)

    def generate_html(self):
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        # _prepare_goals_data() must run first — it annotates self.tasks with goal links
        goals_data = self._prepare_goals_data()
        tasks_json = json.dumps(self.tasks, ensure_ascii=False, default=str)
        projects_list = json.dumps(sorted(self.projects), ensure_ascii=False)
        owners_list = json.dumps(sorted(self.owners), ensure_ascii=False)
        goals_json = json.dumps(goals_data, ensure_ascii=False, default=str)

        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daye HQ Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        :root {{
            --bg: #f8f9fa;
            --surface: #ffffff;
            --text: #1a1a2e;
            --text2: #6c757d;
            --border: #e9ecef;
            --primary: #2c3e50;
            --not-started: #adb5bd;
            --in-progress: #3498db;
            --done: #27ae60;
            --blocked: #e74c3c;
            --shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
            --shadow-lg: 0 4px 12px rgba(0,0,0,0.1);
            --purple: #8e44ad;
            --blue: #2980b9;
            --green: #27ae60;
            --radius: 10px;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }}

        .container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}

        .header {{
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 28px; padding-bottom: 16px;
            border-bottom: 2px solid var(--border);
        }}
        .header h1 {{ font-size: 1.6em; color: var(--primary); }}
        .header-meta {{ font-size: 0.85em; color: var(--text2); }}

        /* === Today Hero Section === */
        .today-hero {{
            margin-bottom: 20px;
        }}
        .today-hero .goal-card.daily {{
            border-left-width: 5px;
            padding: 24px 28px;
        }}
        .today-top3-item {{
            padding: 14px 0;
            border-bottom: 1px solid var(--border);
        }}
        .today-top3-item:last-child {{ border-bottom: none; }}
        .goal-chain {{
            display: flex; align-items: center; gap: 4px;
            font-size: 0.72em; color: var(--text2); margin-bottom: 6px;
            flex-wrap: wrap;
        }}
        .goal-chain-step {{
            padding: 2px 8px; border-radius: 8px; font-weight: 600;
            white-space: nowrap;
        }}
        .goal-chain-step.monthly {{ background: #f0e6f6; color: #8e44ad; }}
        .goal-chain-step.weekly {{ background: #e8f4fd; color: #2980b9; }}
        .goal-chain-arrow {{ color: var(--border); font-size: 1.1em; }}
        .today-task-title {{
            font-size: 1em; font-weight: 600; color: var(--text);
            display: flex; align-items: center; gap: 8px;
        }}
        .today-bottom {{
            display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
            margin-top: 12px;
        }}

        /* === Goals Context (Monthly + Weekly) === */
        .goals-context {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-bottom: 28px;
        }}

        .goal-card {{
            background: var(--surface);
            border-radius: var(--radius);
            padding: 20px;
            box-shadow: var(--shadow);
            border-left: 4px solid var(--primary);
            animation: fadeIn 0.4s ease-out;
        }}
        .goal-card.monthly {{ border-left-color: var(--purple); }}
        .goal-card.weekly {{ border-left-color: var(--blue); }}
        .goal-card.daily {{ border-left-color: var(--green); }}

        .goal-card-header {{
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 6px;
        }}
        .goal-card-label {{
            font-size: 0.75em; font-weight: 700; text-transform: uppercase;
            letter-spacing: 0.5px; color: var(--text2);
        }}
        .goal-card-pct {{ font-size: 1.3em; font-weight: 800; }}
        .goal-card.monthly .goal-card-pct {{ color: var(--purple); }}
        .goal-card.weekly .goal-card-pct {{ color: var(--blue); }}
        .goal-card.daily .goal-card-pct {{ color: var(--green); }}

        .goal-card-theme {{
            font-size: 0.95em; font-weight: 600; color: var(--text);
            margin-bottom: 8px; line-height: 1.3;
        }}

        .goal-progress {{
            width: 100%; height: 6px; background: var(--border);
            border-radius: 3px; overflow: hidden; margin-bottom: 12px;
        }}
        .goal-progress-fill {{
            height: 100%; border-radius: 3px;
            transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        .goal-card.monthly .goal-progress-fill {{ background: linear-gradient(90deg, #8e44ad, #9b59b6); }}
        .goal-card.weekly .goal-progress-fill {{ background: linear-gradient(90deg, #2980b9, #3498db); }}
        .goal-card.daily .goal-progress-fill {{ background: linear-gradient(90deg, #27ae60, #2ecc71); }}

        /* Goal items */
        .goal-item {{
            padding: 6px 0;
            border-bottom: 1px solid var(--border);
            font-size: 0.85em;
        }}
        .goal-item:last-child {{ border-bottom: none; }}

        .goal-item-header {{
            display: flex; align-items: center; gap: 6px;
        }}
        .goal-item-title {{
            flex: 1; color: var(--text);
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }}

        .priority-dot {{
            width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
        }}
        .priority-dot.high {{ background: #e74c3c; }}
        .priority-dot.medium {{ background: #f39c12; }}
        .priority-dot.low {{ background: #27ae60; }}

        .goal-link-tag {{
            display: inline-block;
            font-size: 0.7em; padding: 1px 6px;
            border-radius: 8px; margin-left: 4px;
            white-space: nowrap;
        }}
        .goal-link-tag.monthly {{ background: #f0e6f6; color: #8e44ad; }}
        .goal-link-tag.weekly {{ background: #e8f4fd; color: #2980b9; }}

        .kr-detail {{
            font-size: 0.8em; color: var(--text2);
            margin-left: 14px; padding: 2px 0;
        }}
        .kr-bar {{
            display: inline-block; height: 4px; border-radius: 2px;
            background: var(--border); width: 60px; margin-left: 4px;
            vertical-align: middle;
        }}
        .kr-bar-fill {{
            display: block; height: 100%; border-radius: 2px;
            background: var(--purple);
        }}

        .project-link {{
            cursor: pointer; color: var(--blue);
            text-decoration: underline dotted;
            text-underline-offset: 2px;
        }}
        .project-link:hover {{ color: var(--purple); }}

        /* Daily-specific */
        .daily-section {{ margin-top: 10px; padding-top: 8px; border-top: 1px solid var(--border); }}
        .daily-section-label {{
            font-size: 0.7em; font-weight: 700; text-transform: uppercase;
            color: var(--text2); margin-bottom: 4px;
        }}

        .time-blocks {{ display: flex; flex-direction: column; gap: 2px; }}
        .time-block {{ display: flex; align-items: center; gap: 6px; font-size: 0.8em; }}
        .time-block-time {{
            font-weight: 600; color: var(--text2); min-width: 85px;
            font-variant-numeric: tabular-nums; font-size: 0.85em;
        }}
        .time-block-bar {{
            flex: 1; height: 20px; border-radius: 4px;
            display: flex; align-items: center; padding: 0 8px;
            font-size: 0.8em; color: white; font-weight: 500;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }}
        .time-block-bar.work {{ background: linear-gradient(90deg, #3498db, #5dade2); }}
        .time-block-bar.personal {{ background: linear-gradient(90deg, #27ae60, #58d68d); }}
        .time-block-bar.calendar {{ background: linear-gradient(90deg, #f39c12, #f7dc6f); color: #333; }}

        .checklist {{ list-style: none; }}
        .checklist li {{
            display: flex; align-items: center; gap: 6px;
            padding: 1px 0; font-size: 0.8em; color: var(--text2);
        }}
        .checklist li.done {{ text-decoration: line-through; opacity: 0.5; }}
        .check-box {{
            width: 14px; height: 14px; border-radius: 3px;
            border: 2px solid var(--border); flex-shrink: 0;
            display: inline-flex; align-items: center; justify-content: center;
            font-size: 9px;
        }}
        .check-box.checked {{ background: var(--done); border-color: var(--done); color: white; }}

        .energy-badge {{
            display: inline-block; padding: 1px 6px; border-radius: 8px;
            font-size: 0.7em; font-weight: 600; margin-left: 4px;
        }}
        .energy-badge.high {{ background: #e8f5e9; color: #2e7d32; }}
        .energy-badge.medium {{ background: #fff3e0; color: #e65100; }}
        .energy-badge.low {{ background: #ffebee; color: #c62828; }}

        .goal-empty {{
            text-align: center; color: var(--text2); font-size: 0.9em; padding: 20px 0;
        }}

        /* === Stats + Filters + Chart + Table === */
        .stats-grid {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 12px; margin-bottom: 24px;
        }}
        .stat-card {{
            background: var(--surface); padding: 14px;
            border-radius: var(--radius); box-shadow: var(--shadow);
        }}
        .stat-card h3 {{
            font-size: 0.75em; color: var(--text2);
            text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;
        }}
        .stat-card .number {{ font-size: 1.8em; font-weight: bold; color: var(--primary); }}

        .filters {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 12px; margin-bottom: 24px;
        }}
        .filter-group {{ display: flex; flex-direction: column; gap: 4px; }}
        .filter-group label {{
            font-size: 0.75em; font-weight: 600; color: var(--text2);
            text-transform: uppercase; letter-spacing: 0.5px;
        }}
        .filter-group select {{
            padding: 8px 10px; border: 1px solid var(--border); border-radius: 6px;
            background: var(--surface); color: var(--text); font-size: 13px; cursor: pointer;
        }}
        .filter-group select:focus {{ outline: none; border-color: var(--primary); }}

        .chart-container {{
            background: var(--surface); padding: 20px; border-radius: var(--radius);
            box-shadow: var(--shadow); margin-bottom: 24px; max-height: 320px;
        }}
        .chart-title {{ font-size: 1em; font-weight: 600; margin-bottom: 12px; color: var(--primary); }}

        .table-container {{
            background: var(--surface); border-radius: var(--radius);
            box-shadow: var(--shadow); overflow-x: auto;
        }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        thead {{ background: var(--bg); }}
        th {{
            padding: 10px 12px; text-align: left; font-weight: 600;
            cursor: pointer; user-select: none; white-space: nowrap;
            border-bottom: 2px solid var(--border); font-size: 0.85em;
            color: var(--text2); text-transform: uppercase; letter-spacing: 0.3px;
        }}
        th:hover {{ background: var(--border); }}
        td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); }}
        tbody tr:hover {{ background: var(--bg); }}

        .status-badge {{
            display: inline-block; padding: 2px 8px; border-radius: 12px;
            font-size: 11px; font-weight: 600; white-space: nowrap;
        }}
        .status-badge.not-started {{ background: #e9ecef; color: #6c757d; }}
        .status-badge.in-progress {{ background: #d6eaf8; color: #2471a3; }}
        .status-badge.done {{ background: #d5f5e3; color: #1e8449; }}
        .status-badge.blocked {{ background: #fadbd8; color: #c0392b; }}

        .priority-badge {{
            display: inline-block; padding: 2px 8px; border-radius: 4px;
            font-size: 11px; font-weight: 600;
        }}
        .priority-badge.high {{ background: #ffcdd2; color: #c62828; }}
        .priority-badge.medium {{ background: #fff3e0; color: #e65100; }}
        .priority-badge.low {{ background: #e0f2f1; color: #004d40; }}

        .owner-badge {{
            display: inline-block; padding: 2px 8px; border-radius: 10px;
            font-size: 11px; font-weight: 500;
        }}
        .owner-badge.mingming {{ background: #f3e5f5; color: #7b1fa2; }}
        .owner-badge.daye {{ background: #e8f5e9; color: #2e7d32; }}

        .goal-tag-small {{
            font-size: 0.7em; color: var(--purple);
            background: #f5eef8; padding: 1px 5px; border-radius: 6px;
        }}

        .overdue {{ background: rgba(243, 156, 18, 0.08); }}

        .footer {{
            margin-top: 32px; padding-top: 16px; border-top: 1px solid var(--border);
            text-align: center; color: var(--text2); font-size: 0.8em;
        }}

        /* === Project Detail Modal === */
        .modal-overlay {{
            display: none; position: fixed; top: 0; left: 0;
            width: 100%; height: 100%; background: rgba(0,0,0,0.4);
            z-index: 1000; justify-content: center; align-items: center;
        }}
        .modal-overlay.active {{ display: flex; }}
        .modal {{
            background: var(--surface); border-radius: 14px;
            width: 90%; max-width: 600px; max-height: 80vh;
            overflow-y: auto; padding: 28px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.2);
            animation: modalIn 0.25s ease-out;
        }}
        .modal-header {{
            display: flex; justify-content: space-between; align-items: flex-start;
            margin-bottom: 16px;
        }}
        .modal-title {{ font-size: 1.3em; font-weight: 700; color: var(--primary); }}
        .modal-type {{
            font-size: 0.7em; padding: 2px 8px; border-radius: 8px;
            font-weight: 600; margin-left: 8px;
        }}
        .modal-type.work {{ background: #d6eaf8; color: #2471a3; }}
        .modal-type.personal {{ background: #d5f5e3; color: #1e8449; }}
        .modal-close {{
            background: none; border: none; font-size: 1.5em;
            cursor: pointer; color: var(--text2); line-height: 1;
        }}
        .modal-close:hover {{ color: var(--text); }}
        .modal-section {{
            margin-bottom: 16px; padding-bottom: 12px;
            border-bottom: 1px solid var(--border);
        }}
        .modal-section:last-child {{ border-bottom: none; margin-bottom: 0; }}
        .modal-section-title {{
            font-size: 0.75em; font-weight: 700; text-transform: uppercase;
            color: var(--text2); margin-bottom: 6px; letter-spacing: 0.5px;
        }}
        .modal-goal-item {{
            padding: 4px 0; font-size: 0.9em; display: flex; align-items: center; gap: 6px;
        }}
        .modal-task-item {{
            padding: 6px 0; font-size: 0.85em; display: flex;
            justify-content: space-between; align-items: center;
            border-bottom: 1px solid var(--border);
        }}
        .modal-task-item:last-child {{ border-bottom: none; }}
        .modal-desc {{ font-size: 0.9em; color: var(--text2); line-height: 1.5; }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(8px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        @keyframes modalIn {{
            from {{ opacity: 0; transform: scale(0.95); }}
            to {{ opacity: 1; transform: scale(1); }}
        }}

        @media (max-width: 1024px) {{
            .goals-context {{ grid-template-columns: 1fr 1fr; }}
            .today-bottom {{ grid-template-columns: 1fr; }}
        }}
        @media (max-width: 768px) {{
            .container {{ padding: 16px; }}
            .header {{ flex-direction: column; gap: 8px; align-items: flex-start; }}
            .goals-context {{ grid-template-columns: 1fr; }}
            .today-bottom {{ grid-template-columns: 1fr; }}
            .stats-grid {{ grid-template-columns: 1fr 1fr; }}
            .filters {{ grid-template-columns: 1fr; }}
            .time-block-time {{ min-width: 70px; font-size: 0.8em; }}
            .modal {{ width: 95%; padding: 20px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Daye HQ</h1>
            <span class="header-meta">{timestamp}</span>
        </div>

        <div class="today-hero" id="todayHero"></div>
        <div class="goals-context" id="goalsContext"></div>

        <div class="stats-grid" id="statsContainer"></div>

        <div class="filters">
            <div class="filter-group">
                <label for="projectFilter">프로젝트</label>
                <select id="projectFilter"><option value="">전체</option></select>
            </div>
            <div class="filter-group">
                <label for="ownerFilter">담당자</label>
                <select id="ownerFilter"><option value="">전체</option></select>
            </div>
            <div class="filter-group">
                <label for="statusFilter">상태</label>
                <select id="statusFilter">
                    <option value="">전체</option>
                    <option value="Not Started">시작 전</option>
                    <option value="In Progress">진행 중</option>
                    <option value="Done">완료</option>
                    <option value="Blocked">차단</option>
                </select>
            </div>
            <div class="filter-group">
                <label for="priorityFilter">우선순위</label>
                <select id="priorityFilter">
                    <option value="">전체</option>
                    <option value="high">높음</option>
                    <option value="medium">중간</option>
                    <option value="low">낮음</option>
                </select>
            </div>
        </div>

        <div class="chart-container">
            <div class="chart-title">담당자별 작업 현황</div>
            <canvas id="statusChart"></canvas>
        </div>

        <div class="table-container">
            <table id="tasksTable">
                <thead>
                    <tr>
                        <th onclick="sortTable(0)">프로젝트</th>
                        <th onclick="sortTable(1)">작업</th>
                        <th onclick="sortTable(2)">담당자</th>
                        <th onclick="sortTable(3)">상태</th>
                        <th onclick="sortTable(4)">우선순위</th>
                        <th onclick="sortTable(5)">관련 목표</th>
                        <th onclick="sortTable(6)">시작일</th>
                        <th onclick="sortTable(7)">마감일</th>
                    </tr>
                </thead>
                <tbody id="tasksTableBody"></tbody>
            </table>
        </div>

        <div class="footer"><p>Last updated: {timestamp}</p></div>
    </div>

    <!-- Project Detail Modal -->
    <div class="modal-overlay" id="modalOverlay">
        <div class="modal" id="modalContent"></div>
    </div>

    <script>
        const tasksData = {tasks_json};
        const projects = {projects_list};
        const owners = {owners_list};
        const goalsData = {goals_json};
        let currentSort = {{column: null, ascending: true}};
        let chartInstance = null;

        function initializeUI() {{
            renderGoals();
            populateFilters();
            updateStats();
            renderChart();
            renderTable();
            setupEventListeners();
        }}

        /* ===== Goals Rendering ===== */
        function renderGoals() {{
            const hero = document.getElementById('todayHero');
            const ctx = document.getElementById('goalsContext');
            if (!goalsData) {{ hero.style.display='none'; ctx.style.display='none'; return; }}
            hero.innerHTML = renderDailyCard();
            ctx.innerHTML = renderMonthlyCard() + renderWeeklyCard();
            if (!goalsData.monthly && !goalsData.weekly) ctx.style.display = 'none';
        }}

        function renderMonthlyCard() {{
            const m = goalsData.monthly;
            if (!m) return `<div class="goal-card monthly"><div class="goal-card-header"><span class="goal-card-label">이번 달</span></div><div class="goal-empty">월간 목표 미설정</div></div>`;

            let html = `<div class="goal-card monthly">
                <div class="goal-card-header">
                    <span class="goal-card-label">이번 달</span>
                    <span class="goal-card-pct">${{m.percent}}%</span>
                </div>
                <div class="goal-card-theme">${{m.theme || m.month}}</div>
                <div class="goal-progress"><div class="goal-progress-fill" style="width:${{m.percent}}%"></div></div>`;

            m.goals.forEach(g => {{
                html += `<div class="goal-item">
                    <div class="goal-item-header">
                        <span class="priority-dot ${{g.priority}}"></span>
                        <span class="goal-item-title">
                            <span class="project-link" onclick="showProjectDetail('${{g.project}}')">${{g.title}}</span>
                        </span>
                    </div>`;
                g.key_results.forEach(kr => {{
                    const badge = kr.percent === 100
                        ? '<span class="status-badge done">완료</span>'
                        : kr.percent > 0
                        ? '<span class="status-badge in-progress">진행중</span>'
                        : '<span class="status-badge not-started">시작전</span>';
                    const detail = kr.current ? ` (${{kr.current}})` : '';
                    html += `<div class="kr-detail">
                        ${{badge}} ${{kr.description}}${{detail}}
                        <span class="kr-bar"><span class="kr-bar-fill" style="width:${{kr.percent}}%"></span></span>
                    </div>`;
                }});
                html += `</div>`;
            }});
            html += `</div>`;
            return html;
        }}

        function renderWeeklyCard() {{
            const w = goalsData.weekly;
            if (!w) return `<div class="goal-card weekly"><div class="goal-card-header"><span class="goal-card-label">이번 주</span></div><div class="goal-empty">주간 목표 미설정</div></div>`;

            let html = `<div class="goal-card weekly">
                <div class="goal-card-header">
                    <span class="goal-card-label">이번 주 (${{w.week}})</span>
                    <span class="goal-card-pct">${{w.percent}}%</span>
                </div>
                <div class="goal-card-theme">${{w.period || ''}}</div>
                <div class="goal-progress"><div class="goal-progress-fill" style="width:${{w.percent}}%"></div></div>`;

            w.goals.forEach(g => {{
                const badge = g.status === 'done'
                    ? '<span class="status-badge done">완료</span>'
                    : g.status === 'in_progress'
                    ? '<span class="status-badge in-progress">진행중</span>'
                    : '<span class="status-badge not-started">시작전</span>';
                const monthlyTag = g.monthly_goal
                    ? `<span class="goal-link-tag monthly" title="월간: ${{g.monthly_goal}}">&#8593; ${{g.monthly_goal.substring(0, 12)}}${{g.monthly_goal.length > 12 ? '...' : ''}}</span>`
                    : '';
                html += `<div class="goal-item">
                    <div class="goal-item-header">
                        <span class="priority-dot ${{g.priority}}"></span>
                        <span class="goal-item-title">
                            ${{badge}} <span class="project-link" onclick="showProjectDetail('${{g.project}}')">${{g.title}}</span>
                            ${{monthlyTag}}
                        </span>
                    </div>
                </div>`;
            }});
            html += `</div>`;
            return html;
        }}

        function renderDailyCard() {{
            const d = goalsData.daily;
            if (!d) return `<div class="goal-card daily"><div class="goal-card-header"><span class="goal-card-label">오늘</span></div><div class="goal-empty">일간 목표 미설정</div></div>`;

            const energyMap = {{ high: 'High', medium: 'Medium', low: 'Low' }};
            let html = `<div class="goal-card daily">
                <div class="goal-card-header">
                    <span class="goal-card-label">오늘의 포커스 (${{d.date}} ${{d.day_of_week || ''}})<span class="energy-badge ${{d.energy_level || 'medium'}}">${{energyMap[d.energy_level] || ''}}</span></span>
                    <span class="goal-card-pct">${{d.percent}}%</span>
                </div>
                <div class="goal-progress"><div class="goal-progress-fill" style="width:${{d.percent}}%"></div></div>`;

            // Top 3 with goal chains only
            if (d.top3 && d.top3.length > 0) {{
                d.top3.forEach(g => {{
                    const badge = g.status === 'done'
                        ? '<span class="status-badge done">완료</span>'
                        : g.status === 'in_progress'
                        ? '<span class="status-badge in-progress">진행중</span>'
                        : '<span class="status-badge not-started">시작전</span>';

                    let chain = '<div class="goal-chain">';
                    if (g.monthly_goal) {{
                        chain += `<span class="goal-chain-step monthly">${{g.monthly_goal}}</span>`;
                        if (g.weekly_goal) chain += '<span class="goal-chain-arrow">&rsaquo;</span>';
                    }}
                    if (g.weekly_goal) {{
                        chain += `<span class="goal-chain-step weekly">${{g.weekly_goal}}</span>`;
                    }}
                    chain += '</div>';

                    html += `<div class="today-top3-item">
                        ${{chain}}
                        <div class="today-task-title">${{badge}} ${{g.title}}</div>
                    </div>`;
                }});
            }}
            html += `</div>`;

            // Time blocks + Checklist as separate cards below
            const hasTimeBlocks = d.time_blocks && d.time_blocks.length > 0;
            const hasChecklist = d.checklist && d.checklist.length > 0;
            if (hasTimeBlocks || hasChecklist) {{
                html += `<div class="today-bottom">`;
                if (hasTimeBlocks) {{
                    html += `<div class="goal-card daily" style="border-left-width:3px;padding:16px 20px">
                        <div class="daily-section-label">시간 블록</div><div class="time-blocks">`;
                    d.time_blocks.forEach(b => {{
                        html += `<div class="time-block">
                            <span class="time-block-time">${{b.time}}</span>
                            <div class="time-block-bar ${{b.category}}">${{b.task}}</div>
                        </div>`;
                    }});
                    html += `</div></div>`;
                }}
                if (hasChecklist) {{
                    html += `<div class="goal-card daily" style="border-left-width:3px;padding:16px 20px">
                        <div class="daily-section-label">체크리스트</div><ul class="checklist">`;
                    d.checklist.forEach(c => {{
                        const cls = c.done ? 'done' : '';
                        const chk = c.done ? 'checked' : '';
                        const mark = c.done ? '&#10003;' : '';
                        html += `<li class="${{cls}}"><span class="check-box ${{chk}}">${{mark}}</span>${{c.task}}</li>`;
                    }});
                    html += `</ul></div>`;
                }}
                html += `</div>`;
            }}

            return html;
        }}

        /* ===== Project Detail Modal ===== */
        function showProjectDetail(projectKey) {{
            const proj = goalsData.projects ? goalsData.projects[projectKey] : null;
            if (!proj) return;

            const modal = document.getElementById('modalContent');
            const statusLabels = {{ 'Not Started': '시작 전', 'In Progress': '진행 중', 'Done': '완료', 'Blocked': '차단' }};
            const priLabels = {{ 'high': '높음', 'medium': '중간', 'low': '낮음' }};

            let html = `<div class="modal-header">
                <div>
                    <span class="modal-title">${{proj.name}}</span>
                    <span class="modal-type ${{proj.type}}">${{proj.type === 'work' ? '업무' : '개인'}}</span>
                </div>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>`;

            // Description
            if (proj.description) {{
                html += `<div class="modal-section">
                    <div class="modal-section-title">설명</div>
                    <div class="modal-desc">${{proj.description}}</div>
                </div>`;
            }}

            // Related goals
            if (proj.monthly_goal || proj.weekly_goal) {{
                html += `<div class="modal-section"><div class="modal-section-title">연결된 목표</div>`;
                if (proj.monthly_goal) {{
                    html += `<div class="modal-goal-item"><span class="priority-dot high"></span><span class="goal-link-tag monthly">월간</span> ${{proj.monthly_goal}}</div>`;
                }}
                if (proj.weekly_goal) {{
                    html += `<div class="modal-goal-item"><span class="priority-dot medium"></span><span class="goal-link-tag weekly">주간</span> ${{proj.weekly_goal}}</div>`;
                }}
                html += `</div>`;
            }}

            // Task stats
            const tc = proj.task_counts;
            if (tc && tc.total > 0) {{
                html += `<div class="modal-section">
                    <div class="modal-section-title">작업 현황 (${{tc.done}}/${{tc.total}} 완료)</div>
                    <div class="goal-progress" style="margin:8px 0"><div class="goal-progress-fill" style="width:${{tc.total > 0 ? Math.round(tc.done/tc.total*100) : 0}}%;background:var(--done)"></div></div>`;

                // All tasks
                proj.all_tasks.forEach(t => {{
                    const stCls = (t.status || '').toLowerCase().replace(/\\s+/g, '-');
                    html += `<div class="modal-task-item">
                        <span>${{t.title}}</span>
                        <span class="status-badge ${{stCls}}">${{statusLabels[t.status] || t.status}}</span>
                    </div>`;
                }});
                html += `</div>`;
            }}

            // History
            if (proj.history && proj.history.length > 0) {{
                html += `<div class="modal-section"><div class="modal-section-title">완료 히스토리</div>`;
                proj.history.forEach(h => {{
                    html += `<div class="modal-task-item">
                        <span>&#10003; ${{h.title}}</span>
                        <span style="font-size:0.8em;color:var(--text2)">${{h.completed}}</span>
                    </div>`;
                }});
                html += `</div>`;
            }}

            modal.innerHTML = html;
            document.getElementById('modalOverlay').classList.add('active');
        }}

        function closeModal() {{
            document.getElementById('modalOverlay').classList.remove('active');
        }}

        /* ===== Filters & Stats ===== */
        function populateFilters() {{
            const ps = document.getElementById('projectFilter');
            const os = document.getElementById('ownerFilter');
            projects.forEach(p => {{
                const opt = document.createElement('option');
                opt.value = p; opt.textContent = p.replace(/^(work|personal)--/, '');
                ps.appendChild(opt);
            }});
            owners.forEach(o => {{
                const opt = document.createElement('option');
                opt.value = o;
                opt.textContent = o === 'daye' ? 'Daye' : o === 'mingming' ? '밍밍' : o;
                os.appendChild(opt);
            }});
        }}

        function getFilteredTasks() {{
            const pf = document.getElementById('projectFilter').value;
            const of2 = document.getElementById('ownerFilter').value;
            const sf = document.getElementById('statusFilter').value;
            const rf = document.getElementById('priorityFilter').value;
            return tasksData.filter(t => {{
                if (pf && t.project !== pf) return false;
                if (of2 && t.owner !== of2) return false;
                if (sf && t.status !== sf) return false;
                if (rf && t.priority !== rf) return false;
                return true;
            }});
        }}

        function filterByProject(project) {{
            document.getElementById('projectFilter').value = project || '';
            updateStats(); renderChart(); renderTable();
        }}

        function updateStats() {{
            const f = getFilteredTasks();
            const s = {{
                total: f.length,
                ip: f.filter(t => t.status === 'In Progress').length,
                done: f.filter(t => t.status === 'Done').length,
                blocked: f.filter(t => t.status === 'Blocked').length,
            }};
            document.getElementById('statsContainer').innerHTML = `
                <div class="stat-card"><h3>전체</h3><div class="number">${{s.total}}</div></div>
                <div class="stat-card"><h3>진행 중</h3><div class="number">${{s.ip}}</div></div>
                <div class="stat-card"><h3>완료</h3><div class="number">${{s.done}}</div></div>
                <div class="stat-card"><h3>차단</h3><div class="number">${{s.blocked}}</div></div>
            `;
        }}

        /* ===== Chart ===== */
        function renderChart() {{
            const od = {{}};
            owners.forEach(o => {{ od[o] = {{'Not Started':0,'In Progress':0,'Done':0,'Blocked':0}}; }});
            getFilteredTasks().forEach(t => {{ if (od[t.owner]) od[t.owner][t.status] = (od[t.owner][t.status]||0)+1; }});
            const labels = owners.map(o => o === 'daye' ? 'Daye' : o === 'mingming' ? '밍밍' : o);
            const ctx = document.getElementById('statusChart').getContext('2d');
            if (chartInstance) chartInstance.destroy();
            chartInstance = new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels,
                    datasets: [
                        {{label:'시작 전', data: owners.map(o=>od[o]['Not Started']), backgroundColor:'#adb5bd'}},
                        {{label:'진행 중', data: owners.map(o=>od[o]['In Progress']), backgroundColor:'#3498db'}},
                        {{label:'완료', data: owners.map(o=>od[o]['Done']), backgroundColor:'#27ae60'}},
                        {{label:'차단', data: owners.map(o=>od[o]['Blocked']), backgroundColor:'#e74c3c'}}
                    ]
                }},
                options: {{
                    responsive: true, maintainAspectRatio: true,
                    plugins: {{legend: {{position:'top'}}}},
                    scales: {{x: {{stacked:true}}, y: {{stacked:true, beginAtZero:true}}}}
                }}
            }});
        }}

        /* ===== Table ===== */
        function renderTable() {{
            const filtered = getFilteredTasks();
            const tbody = document.getElementById('tasksTableBody');
            tbody.innerHTML = filtered.map(task => {{
                const goalTag = task.monthly_goal
                    ? `<span class="goal-tag-small">${{task.monthly_goal.substring(0,15)}}${{task.monthly_goal.length>15?'...':''}}</span>`
                    : '<span style="color:var(--text2)">-</span>';
                return `<tr class="${{isOverdue(task)?'overdue':''}}">
                    <td><span class="project-link" onclick="showProjectDetail('${{task.project}}')">${{task.project.replace(/^(work|personal)--/,'')}}</span></td>
                    <td>${{task.title || task.name || '-'}}</td>
                    <td><span class="owner-badge ${{task.owner}}">${{task.owner === 'daye' ? 'Daye' : task.owner === 'mingming' ? '밍밍' : task.owner}}</span></td>
                    <td><span class="status-badge ${{getStatusClass(task.status)}}">${{getStatusLabel(task.status)}}</span></td>
                    <td><span class="priority-badge ${{(task.priority||'low').toLowerCase()}}">${{getPriorityLabel(task.priority)}}</span></td>
                    <td>${{goalTag}}</td>
                    <td>${{formatDate(task.start)}}</td>
                    <td>${{formatDate(task.deadline || task.due)}}</td>
                </tr>`;
            }}).join('');
        }}

        function getStatusClass(s) {{ return (s||'').toLowerCase().replace(/\\s+/g,'-'); }}
        function getStatusLabel(s) {{ return {{'Not Started':'시작 전','In Progress':'진행 중','Done':'완료','Blocked':'차단'}}[s]||s||'-'; }}
        function getPriorityLabel(p) {{ return {{'high':'높음','medium':'중간','low':'낮음'}}[(p||'').toLowerCase()]||'-'; }}
        function formatDate(d) {{ if(!d) return '-'; return new Date(d).toLocaleDateString('ko-KR',{{month:'short',day:'numeric'}}); }}
        function isOverdue(t) {{ if(!t.deadline&&!t.due) return false; if(t.status==='Done') return false; return new Date(t.deadline||t.due)<new Date(); }}

        function sortTable(col) {{
            const tbody = document.getElementById('tasksTableBody');
            const rows = Array.from(tbody.rows);
            if (currentSort.column===col) currentSort.ascending=!currentSort.ascending;
            else {{ currentSort.column=col; currentSort.ascending=true; }}
            rows.sort((a,b) => {{
                let av=a.cells[col].textContent, bv=b.cells[col].textContent;
                return currentSort.ascending ? av.localeCompare(bv) : bv.localeCompare(av);
            }});
            rows.forEach(r => tbody.appendChild(r));
        }}

        function setupEventListeners() {{
            ['projectFilter','ownerFilter','statusFilter','priorityFilter'].forEach(id => {{
                document.getElementById(id).addEventListener('change', () => {{
                    updateStats(); renderChart(); renderTable();
                }});
            }});
            // Close modal on overlay click
            document.getElementById('modalOverlay').addEventListener('click', e => {{
                if (e.target === e.currentTarget) closeModal();
            }});
            // Close modal on Escape
            document.addEventListener('keydown', e => {{
                if (e.key === 'Escape') closeModal();
            }});
        }}

        document.addEventListener('DOMContentLoaded', initializeUI);
    </script>
</body>
</html>
"""
        return html

    def write_html(self):
        output_dir = self._resolve_path(self.config["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        html_content = self.generate_html()
        index_path = output_dir / "index.html"
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return output_dir

    def run(self):
        if not self.scan_projects():
            return False
        self.scan_goals()
        self.write_html()
        return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Generate task dashboard')
    parser.add_argument('--output', '-o', help='Output directory', default=None)
    parser.add_argument('--config', '-c', help='Config file path', default='config.json')
    args = parser.parse_args()

    try:
        generator = TaskDashboardGenerator(config_path=args.config, output_dir=args.output)
        success = generator.run()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
