"""
Data loader module for loading catalog, profiles, interventions, and triggers.
"""

import json
from typing import Dict, List, Optional
from submission.src.models import CatalogueTitle, GoalRule, TriggerEvent


class DataLoader:
    def __init__(self, data_dir: str = "submission/data"):
        self.data_dir = data_dir
        self.titles: Dict[str, CatalogueTitle] = {}
        self.titles_by_dialect: Dict[str, List[CatalogueTitle]] = {
            f"d{i}": [] for i in range(1, 7)
        }
        self.goals: Dict[str, GoalRule] = {}
        self.interventions: Dict[str, dict] = {}
        self.profiles: Dict[str, dict] = {}
        self._load_all()

    def _load_all(self):
        # Load content catalogue
        with open(f"{self.data_dir}/content_catalogue.json", "r", encoding="utf-8") as f:
            raw_titles = json.load(f)
            for t in raw_titles:
                title_obj = CatalogueTitle(**t)
                self.titles[title_obj.title_id] = title_obj
                for d in title_obj.dialects:
                    if d in self.titles_by_dialect:
                        self.titles_by_dialect[d].append(title_obj)

        # Load goal catalogue
        with open(f"{self.data_dir}/goal_catalogue.json", "r", encoding="utf-8") as f:
            raw_goals = json.load(f)
            for g in raw_goals:
                goal_obj = GoalRule(**g)
                self.goals[goal_obj.goal_id] = goal_obj

        # Load intervention catalogue
        with open(f"{self.data_dir}/intervention_catalogue.json", "r", encoding="utf-8") as f:
            self.interventions = json.load(f)

        # Load viewer profiles snapshot
        with open(f"{self.data_dir}/viewer_profiles.json", "r", encoding="utf-8") as f:
            raw_profiles = json.load(f)
            for p in raw_profiles:
                vid = p["viewer_id"]
                # Keep existing if duplicate, but note duplicate conflict in profile loader
                if vid in self.profiles:
                    # Mark existing record with duplicate conflict
                    existing = self.profiles[vid]
                    if existing.get("preferred_dialect") != p.get("preferred_dialect"):
                        existing["has_profile_conflict"] = True
                        existing["alternate_profile"] = p
                else:
                    self.profiles[vid] = p

    def get_titles_for_dialect(self, dialect: str, available_only: bool = True) -> List[CatalogueTitle]:
        titles = self.titles_by_dialect.get(dialect, [])
        if available_only:
            return [t for t in titles if t.is_available]
        return titles

    def get_profile(self, viewer_id: str) -> Optional[dict]:
        return self.profiles.get(viewer_id)

    def load_triggers(self, file_path: Optional[str] = None) -> List[TriggerEvent]:
        path = file_path or f"{self.data_dir}/replay_triggers.jsonl"
        triggers = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    triggers.append(TriggerEvent(**data))
        return triggers
