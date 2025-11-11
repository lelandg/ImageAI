"""
Tag-based semantic search for Prompt Builder items.

This module provides intelligent search functionality using pre-generated
semantic tags and metadata. Enables users to find relevant artists, styles,
and moods using high-level concepts like "Mad Magazine" or "cyberpunk".
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result with relevance scoring."""
    item: str
    category: str
    score: float
    matched_on: List[str]  # What triggered the match (tag, keyword, etc.)


class TagSearcher:
    """
    Semantic search for Prompt Builder items using pre-generated tags.

    Supports fuzzy matching across:
    - Item names (exact and partial)
    - Semantic tags
    - Cultural keywords
    - Descriptions
    - Related items

    Scoring:
    - Exact name match: 100 points
    - Partial name match: 50 points
    - Tag match: 20 points
    - Keyword match: 15 points
    - Description match: 10 points
    - Related item match: 5 points
    - Popularity boost: +0-10 points
    """

    def __init__(self, metadata_path: Optional[Path] = None):
        """
        Initialize the tag searcher.

        Args:
            metadata_path: Path to metadata.json file. If None, uses default location.
        """
        if metadata_path is None:
            # Default to data/prompts/metadata.json
            metadata_path = Path(__file__).parent.parent / "data" / "prompts" / "metadata.json"

        self.metadata_path = metadata_path
        self.metadata: Dict[str, Dict] = {}
        self.loaded = False

        # Load metadata on init
        self._load_metadata()

    def _load_metadata(self) -> bool:
        """
        Load metadata from JSON file.

        Returns:
            True if successful, False otherwise.
        """
        try:
            if not self.metadata_path.exists():
                logger.error(f"Metadata file not found: {self.metadata_path}")
                return False

            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)

            # Count total items
            total = sum(len(items) for items in self.metadata.values())
            logger.info(f"Loaded metadata for {total} items from {self.metadata_path}")
            self.loaded = True
            return True

        except Exception as e:
            logger.error(f"Error loading metadata: {e}")
            return False

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        max_results: int = 10,
        min_score: float = 5.0
    ) -> List[SearchResult]:
        """
        Search for items matching the query.

        Args:
            query: Search query (e.g., "mad magazine", "cyberpunk", "moody")
            category: Optional category filter (artists, styles, mediums, colors, lighting, moods)
            max_results: Maximum results per category
            min_score: Minimum relevance score to include

        Returns:
            List of SearchResult objects, sorted by relevance score (highest first)
        """
        if not self.loaded:
            logger.warning("Metadata not loaded, search unavailable")
            return []

        if not query or not query.strip():
            return []

        # Normalize query for matching
        query_lower = query.lower().strip()
        query_terms = query_lower.split()

        results: List[SearchResult] = []

        # Determine which categories to search
        categories_to_search = [category] if category else list(self.metadata.keys())

        for cat in categories_to_search:
            if cat not in self.metadata:
                continue

            for item_name, item_data in self.metadata[cat].items():
                score, matched_on = self._score_item(
                    item_name, item_data, query_lower, query_terms
                )

                if score >= min_score:
                    results.append(SearchResult(
                        item=item_name,
                        category=cat,
                        score=score,
                        matched_on=matched_on
                    ))

        # Sort by score (descending) and limit results
        results.sort(key=lambda r: r.score, reverse=True)

        if max_results > 0:
            results = results[:max_results]

        logger.debug(f"Search '{query}' returned {len(results)} results")
        return results

    def search_by_category(
        self,
        query: str,
        max_per_category: int = 10,
        min_score: float = 5.0
    ) -> Dict[str, List[SearchResult]]:
        """
        Search across all categories, returning results grouped by category.

        Args:
            query: Search query
            max_per_category: Maximum results per category
            min_score: Minimum relevance score

        Returns:
            Dict mapping category name to list of SearchResult objects
        """
        results_by_category = {}

        for category in self.metadata.keys():
            results = self.search(
                query=query,
                category=category,
                max_results=max_per_category,
                min_score=min_score
            )
            if results:
                results_by_category[category] = results

        return results_by_category

    def _score_item(
        self,
        item_name: str,
        item_data: Dict,
        query_lower: str,
        query_terms: List[str]
    ) -> Tuple[float, List[str]]:
        """
        Calculate relevance score for an item.

        Args:
            item_name: Name of the item
            item_data: Metadata for the item
            query_lower: Lowercase query string
            query_terms: Query split into terms

        Returns:
            Tuple of (score, list of match reasons)
        """
        score = 0.0
        matched_on = []

        item_name_lower = item_name.lower()

        # 1. Exact name match (100 points)
        if query_lower == item_name_lower:
            score += 100
            matched_on.append("exact_name")
        # 2. Partial name match (50 points)
        elif query_lower in item_name_lower:
            score += 50
            matched_on.append("partial_name")
        # 3. All query terms in name (40 points)
        elif all(term in item_name_lower for term in query_terms):
            score += 40
            matched_on.append("name_all_terms")

        # 4. Tag matches (20 points per tag)
        tags = item_data.get('tags', [])
        for tag in tags:
            tag_lower = str(tag).lower()
            if query_lower == tag_lower:
                score += 20
                matched_on.append(f"tag:{tag}")
            elif query_lower in tag_lower or tag_lower in query_lower:
                score += 15
                matched_on.append(f"tag_partial:{tag}")
            elif any(term in tag_lower for term in query_terms):
                score += 10
                matched_on.append(f"tag_term:{tag}")

        # 5. Cultural keyword matches (15 points per keyword)
        keywords = item_data.get('cultural_keywords', [])
        for keyword in keywords:
            keyword_lower = str(keyword).lower()
            if query_lower in keyword_lower:
                score += 15
                matched_on.append(f"keyword:{keyword}")
            elif any(term in keyword_lower for term in query_terms):
                score += 10
                matched_on.append(f"keyword_term:{keyword}")

        # 6. Description match (10 points)
        description = item_data.get('description', '')
        if description:
            desc_lower = description.lower()
            if query_lower in desc_lower:
                score += 10
                matched_on.append("description")
            elif any(term in desc_lower for term in query_terms):
                score += 5
                matched_on.append("description_term")

        # 7. Related styles/moods match (5 points)
        related_fields = ['related_styles', 'related_moods', 'related_artists']
        for field in related_fields:
            related = item_data.get(field, [])
            for rel_item in related:
                rel_lower = str(rel_item).lower()
                if query_lower in rel_lower:
                    score += 5
                    matched_on.append(f"{field}:{rel_item}")

        # 8. Era match (8 points)
        era = item_data.get('era', '')
        if era:
            era_lower = era.lower()
            # Match decade patterns (1960s, 1970s, etc.)
            if any(term in era_lower for term in query_terms):
                score += 8
                matched_on.append(f"era:{era}")

        # 9. Popularity boost (0-10 points)
        popularity = item_data.get('popularity', 5)
        if popularity > 5:
            boost = (popularity - 5) * 2  # 6->2, 7->4, 8->6, 9->8, 10->10
            score += boost
            matched_on.append(f"popularity:{popularity}")

        return score, matched_on

    def get_related_items(self, item_name: str, category: str) -> Dict[str, List[str]]:
        """
        Get related items for a given item.

        Args:
            item_name: Name of the item
            category: Category of the item

        Returns:
            Dict with keys like 'related_styles', 'related_moods', etc.
        """
        if category not in self.metadata:
            return {}

        item_data = self.metadata[category].get(item_name, {})

        related = {}
        for key in ['related_styles', 'related_moods', 'related_artists']:
            if key in item_data:
                related[key] = item_data[key]

        return related

    def get_item_tags(self, item_name: str, category: str) -> List[str]:
        """
        Get all tags for a given item.

        Args:
            item_name: Name of the item
            category: Category of the item

        Returns:
            List of tags
        """
        if category not in self.metadata:
            return []

        item_data = self.metadata[category].get(item_name, {})
        return item_data.get('tags', [])

    def get_all_tags(self, category: Optional[str] = None) -> Set[str]:
        """
        Get all unique tags across items.

        Args:
            category: Optional category filter

        Returns:
            Set of all unique tags
        """
        all_tags = set()

        categories = [category] if category else list(self.metadata.keys())

        for cat in categories:
            if cat not in self.metadata:
                continue

            for item_data in self.metadata[cat].values():
                tags = item_data.get('tags', [])
                all_tags.update(tags)

        return all_tags
