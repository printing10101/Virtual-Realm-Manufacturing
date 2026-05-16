from __future__ import annotations

import json
import logging
import os
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.skill_loader import (
    SkillLevel,
    get_skill_loader,
)

logger = logging.getLogger(__name__)

DEFAULT_MARKET_DIR = ".trae/skills/.marketplace"


@dataclass
class MarketListing:
    skill_id: str
    name: str
    version: str
    description: str
    author: str
    tags: List[str] = field(default_factory=list)
    downloads: int = 0
    avg_rating: float = 0.0
    rating_count: int = 0
    created_at: str = ""
    updated_at: str = ""


class SkillMarketplace:
    def __init__(self, market_dir: Optional[str] = None):
        self.market_dir = market_dir or DEFAULT_MARKET_DIR
        os.makedirs(self.market_dir, exist_ok=True)
        self._listings_file = os.path.join(self.market_dir, "listings.json")
        self._listings: Dict[str, MarketListing] = self._load_listings()

    def _load_listings(self) -> Dict[str, MarketListing]:
        if not os.path.exists(self._listings_file):
            return {}
        try:
            with open(self._listings_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return {k: MarketListing(**v) for k, v in raw.items()}
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed to load marketplace listings: %s", e)
            return {}

    def _save_listings(self) -> None:
        data = {
            k: {
                "skill_id": v.skill_id,
                "name": v.name,
                "version": v.version,
                "description": v.description,
                "author": v.author,
                "tags": v.tags,
                "downloads": v.downloads,
                "avg_rating": v.avg_rating,
                "rating_count": v.rating_count,
                "created_at": v.created_at,
                "updated_at": v.updated_at,
            }
            for k, v in self._listings.items()
        }
        with open(self._listings_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def publish(
        self,
        skill_id: str,
        author: str,
        level: SkillLevel = SkillLevel.PROJECT,
        sub_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        loader = get_skill_loader()
        package = loader.export_skill(skill_id)
        if package is None:
            logger.warning("Skill not found for publish: %s", skill_id)
            return None

        meta = package.get("metadata", {})
        now = datetime.now(timezone.utc).isoformat()

        listing = MarketListing(
            skill_id=skill_id,
            name=meta.get("name", skill_id),
            version=meta.get("version", "1.0.0"),
            description=meta.get("description", ""),
            author=author,
            tags=meta.get("tags", []),
            created_at=now,
            updated_at=now,
        )

        self._listings[skill_id] = listing

        pkg_file = self._build_package(package)
        self._save_listings()

        logger.info("Skill published: %s by %s", skill_id, author)
        return {
            "skill_id": skill_id,
            "listing": listing,
            "package_path": pkg_file,
        }

    def _build_package(self, package: Dict[str, Any]) -> str:
        skill_id = package["skill_id"]
        package_file = os.path.join(
            self.market_dir,
            f"{skill_id}_{package.get('metadata', {}).get('version', '1.0.0')}.skz",
        )

        with zipfile.ZipFile(package_file, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "manifest.json",
                json.dumps(
                    {
                        "skill_id": skill_id,
                        "name": package.get("name", ""),
                        "version": package.get("version", "1.0.0"),
                        "metadata": package.get("metadata", {}),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
            zf.writestr("skill.md", package.get("raw_content", ""))

        logger.info("Package built: %s", package_file)
        return package_file

    def list_available(self, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        results = []
        for skill_id, listing in self._listings.items():
            if tag and tag not in listing.tags:
                continue
            results.append(
                {
                    "skill_id": listing.skill_id,
                    "name": listing.name,
                    "version": listing.version,
                    "description": listing.description,
                    "author": listing.author,
                    "tags": listing.tags,
                    "downloads": listing.downloads,
                    "avg_rating": listing.avg_rating,
                    "rating_count": listing.rating_count,
                    "created_at": listing.created_at,
                    "updated_at": listing.updated_at,
                }
            )

        results.sort(key=lambda x: (x["avg_rating"], x["downloads"]), reverse=True)
        return results

    def search(self, query: str) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        results = []
        for skill_id, listing in self._listings.items():
            searchable = f"{listing.name} {listing.description} {' '.join(listing.tags)} {listing.author}"
            if query_lower in searchable.lower():
                results.append(
                    {
                        "skill_id": listing.skill_id,
                        "name": listing.name,
                        "version": listing.version,
                        "description": listing.description,
                        "author": listing.author,
                        "tags": listing.tags,
                        "downloads": listing.downloads,
                        "avg_rating": listing.avg_rating,
                        "rating_count": listing.rating_count,
                    }
                )

        results.sort(key=lambda x: (x["avg_rating"], x["downloads"]), reverse=True)
        return results

    def download(
        self,
        skill_id: str,
        target_level: SkillLevel = SkillLevel.PROJECT,
        target_sub_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        loader = get_skill_loader()

        matching_files = [
            f
            for f in os.listdir(self.market_dir)
            if f.startswith(f"{skill_id}_") and f.endswith(".skz")
        ]
        if not matching_files:
            logger.warning("Package not found for download: %s", skill_id)
            return None

        package_path = os.path.join(self.market_dir, matching_files[0])

        with zipfile.ZipFile(package_path, "r") as zf:
            manifest_raw = zf.read("manifest.json").decode("utf-8")
            manifest = json.loads(manifest_raw)
            skill_md = zf.read("skill.md").decode("utf-8")

        imported = loader.import_skill(
            {
                "skill_id": skill_id,
                "raw_content": skill_md,
                "metadata": manifest.get("metadata", {}),
            },
            level=target_level,
            sub_id=target_sub_id,
        )

        if skill_id in self._listings:
            self._listings[skill_id].downloads += 1
            self._save_listings()

        logger.info("Skill downloaded: %s", skill_id)
        return {
            "skill_id": skill_id,
            "imported": imported is not None,
            "level": target_level.value,
            "sub_id": target_sub_id,
        }

    def rate_skill(
        self, skill_id: str, rating: float, agent_id: str = ""
    ) -> Dict[str, Any]:
        loader = get_skill_loader()
        result = loader.rate_skill(skill_id, rating)

        if skill_id in self._listings:
            self._listings[skill_id].avg_rating = result["avg_rating"]
            self._listings[skill_id].rating_count = result["rating_count"]
            self._save_listings()

        return {
            **result,
            "agent_id": agent_id,
        }

    def unpublish(self, skill_id: str) -> bool:
        if skill_id in self._listings:
            del self._listings[skill_id]
            self._save_listings()

            matching_files = [
                f
                for f in os.listdir(self.market_dir)
                if f.startswith(f"{skill_id}_") and f.endswith(".skz")
            ]
            for f in matching_files:
                os.remove(os.path.join(self.market_dir, f))

            logger.info("Skill unpublished: %s", skill_id)
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_listings": len(self._listings),
            "market_dir": self.market_dir,
            "most_downloaded": max(
                self._listings.values(),
                key=lambda x: x.downloads,
                default=None,
            ),
            "highest_rated": max(
                self._listings.values(),
                key=lambda x: x.avg_rating,
                default=None,
            ),
        }


_marketplace: Optional[SkillMarketplace] = None


def get_marketplace(market_dir: Optional[str] = None) -> SkillMarketplace:
    global _marketplace
    if _marketplace is None:
        _marketplace = SkillMarketplace(market_dir)
    return _marketplace
