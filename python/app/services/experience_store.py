import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import chromadb
from chromadb.config import Settings

from app.models.experience import ProcessExperience, ExperienceStatus


class ExperienceStore:
    def __init__(self, data_dir: str = "./data/experiences"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.experiences_file = self.data_dir / "experiences.jsonl"
        self.rules_file = self.data_dir / "rules.json"
        self.manifest_file = self.data_dir / "manifest.json"

        chroma_dir = self.data_dir / "chroma_db"
        chroma_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=str(chroma_dir))
        self.collection = self.chroma_client.get_or_create_collection(
            name="experience_store",
            metadata={"description": "加工工艺经验向量存储"}
        )

        self._experiences: List[ProcessExperience] = []
        self._rules: Dict[str, List[Dict[str, Any]]] = {}
        self._load_from_disk()

    def _load_from_disk(self):
        if self.experiences_file.exists():
            with open(self.experiences_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            exp = ProcessExperience.from_jsonl(line)
                            self._experiences.append(exp)
                        except Exception:
                            pass

        if self.rules_file.exists():
            with open(self.rules_file, "r", encoding="utf-8") as f:
                self._rules = json.load(f)

    def _save_experience_file(self, experience: ProcessExperience):
        with open(self.experiences_file, "a", encoding="utf-8") as f:
            f.write(experience.to_jsonl() + "\n")

    def _update_rules(self, experience: ProcessExperience):
        scenario = experience.scenario or "default"
        if scenario not in self._rules:
            self._rules[scenario] = []

        existing_rules = {r["rule"] for r in self._rules[scenario]}
        for rule in experience.extracted_rules:
            if rule not in existing_rules:
                self._rules[scenario].append({
                    "rule": rule,
                    "source_experience_id": experience.experience_id,
                    "status": experience.status.value,
                    "created_at": experience.created_at,
                    "enabled": True
                })
                existing_rules.add(rule)

        with open(self.rules_file, "w", encoding="utf-8") as f:
            json.dump(self._rules, f, ensure_ascii=False, indent=2)

    def _update_manifest(self):
        stats = self._compute_stats()
        with open(self.manifest_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

    def _compute_stats(self) -> Dict[str, Any]:
        total = len(self._experiences)
        success = sum(1 for e in self._experiences if e.status == ExperienceStatus.SUCCESS)
        failure = sum(1 for e in self._experiences if e.status == ExperienceStatus.FAILURE)
        partial = sum(1 for e in self._experiences if e.status == ExperienceStatus.PARTIAL)

        scenario_dist = {}
        for e in self._experiences:
            scenario = e.scenario or "default"
            scenario_dist[scenario] = scenario_dist.get(scenario, 0) + 1

        total_rules = sum(len(rules) for rules in self._rules.values())

        return {
            "total_experiences": total,
            "success_count": success,
            "failure_count": failure,
            "partial_count": partial,
            "success_rate": success / total if total > 0 else 0,
            "scenario_distribution": scenario_dist,
            "total_rules": total_rules,
            "last_updated": datetime.now().isoformat()
        }

    def _add_to_vector_store(self, experience: ProcessExperience):
        if experience.similarity_key:
            try:
                self.collection.add(
                    documents=[experience.similarity_key],
                    metadatas=[{
                        "experience_id": experience.experience_id,
                        "status": experience.status.value,
                        "material": experience.material,
                        "tool": experience.tool,
                        "operation": experience.operation,
                        "scenario": experience.scenario
                    }],
                    ids=[experience.experience_id]
                )
            except Exception:
                pass

    def add_experience(self, experience: ProcessExperience) -> str:
        self._experiences.append(experience)
        self._save_experience_file(experience)
        self._update_rules(experience)
        self._add_to_vector_store(experience)
        self._update_manifest()
        return experience.experience_id

    def query_similar(
        self,
        material: str = "",
        tool: str = "",
        operation: str = "",
        params: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> Dict[str, List[ProcessExperience]]:
        query_text = f"{material} {tool} {operation}"
        if params:
            for k, v in params.items():
                query_text += f" {k}={v}"

        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=top_k
            )

            ids = results["ids"][0] if results["ids"] else []
            success_experiences = []
            failure_experiences = []

            for exp in self._experiences:
                if exp.experience_id in ids:
                    if exp.status == ExperienceStatus.SUCCESS:
                        success_experiences.append(exp)
                    else:
                        failure_experiences.append(exp)

            return {
                "success_experiences": success_experiences,
                "failure_experiences": failure_experiences
            }
        except Exception:
            return {"success_experiences": [], "failure_experiences": []}

    def get_rules(self, scenario: str = "") -> Dict[str, List[Dict[str, Any]]]:
        if scenario:
            return {scenario: self._rules.get(scenario, [])}
        return self._rules

    def get_all_experiences(
        self,
        scenario: str = "",
        material: str = "",
        status: str = ""
    ) -> List[ProcessExperience]:
        results = self._experiences
        if scenario:
            results = [e for e in results if e.scenario == scenario]
        if material:
            results = [e for e in results if e.material == material]
        if status:
            results = [e for e in results if e.status.value == status]
        return results

    def get_experience_by_id(self, experience_id: str) -> Optional[ProcessExperience]:
        for exp in self._experiences:
            if exp.experience_id == experience_id:
                return exp
        return None

    def delete_experience(self, experience_id: str) -> bool:
        exp = self.get_experience_by_id(experience_id)
        if not exp:
            return False

        self._experiences = [e for e in self._experiences if e.experience_id != experience_id]

        try:
            self.collection.delete(ids=[experience_id])
        except Exception:
            pass

        with open(self.experiences_file, "w", encoding="utf-8") as f:
            for e in self._experiences:
                f.write(e.to_jsonl() + "\n")

        self._update_manifest()
        return True

    def get_stats(self) -> Dict[str, Any]:
        return self._compute_stats()

    def toggle_rule(self, scenario: str, rule_index: int) -> bool:
        if scenario not in self._rules:
            return False
        if rule_index >= len(self._rules[scenario]):
            return False
        self._rules[scenario][rule_index]["enabled"] = not self._rules[scenario][rule_index]["enabled"]
        with open(self.rules_file, "w", encoding="utf-8") as f:
            json.dump(self._rules, f, ensure_ascii=False, indent=2)
        return True


_experience_store: Optional[ExperienceStore] = None


def get_experience_store(data_dir: str = "./data/experiences") -> ExperienceStore:
    global _experience_store
    if _experience_store is None:
        _experience_store = ExperienceStore(data_dir=data_dir)
    return _experience_store
