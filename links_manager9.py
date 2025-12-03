"""
DataBossX Links Manager v9
Manages apps, links, and workflow groups with usage tracking
"""

import json
import webbrowser
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

from config_databossx9 import get_config

# Configure logging
logger = logging.getLogger(__name__)


class LinksManager:
    """
    Manages external links, apps, and workflow groups.
    Tracks usage and suggests optimal workflows.
    """

    def __init__(self, config_file: str = "config/links_config9.json"):
        """
        Initialize Links Manager.

        Args:
            config_file: Path to links configuration file
        """
        self.config_file = Path(config_file)
        self.links: Dict[str, Any] = {}
        self.usage_stats: Dict[str, int] = defaultdict(int)
        self._ensure_config_directory()
        self.load_links()
        logger.info("LinksManager initialized")

    def _ensure_config_directory(self):
        """Ensure configuration directory exists"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

    def load_links(self):
        """Load links configuration from file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.links = data.get('links', {})
                    self.usage_stats = defaultdict(int, data.get('usage_stats', {}))
                logger.info(f"Links loaded from {self.config_file}")
            else:
                self._create_default_config()
                logger.info("Default links configuration created")
        except Exception as e:
            logger.error(f"Error loading links: {e}")
            self._create_default_config()

    def _create_default_config(self):
        """Create default links configuration"""
        self.links = {
            # Communication
            "aol_mail": {
                "name": "AOL Mail",
                "url": "https://mail.aol.com",
                "category": "Communication",
                "icon": "📧",
                "shortcut": "AOL",
                "description": "Personal email"
            },
            "gmail": {
                "name": "Gmail",
                "url": "https://mail.google.com",
                "category": "Communication",
                "icon": "📬",
                "description": "Google email"
            },

            # AI Tools
            "chatgpt": {
                "name": "ChatGPT",
                "url": "https://chat.openai.com",
                "category": "AI",
                "icon": "🤖",
                "description": "OpenAI ChatGPT"
            },
            "claude": {
                "name": "Claude",
                "url": "https://claude.ai",
                "category": "AI",
                "icon": "🧠",
                "description": "Anthropic Claude"
            },
            "gemini": {
                "name": "Gemini",
                "url": "https://gemini.google.com",
                "category": "AI",
                "icon": "✨",
                "description": "Google Gemini"
            },
            "deepseek": {
                "name": "DeepSeek",
                "url": "https://chat.deepseek.com",
                "category": "AI",
                "icon": "🔮",
                "description": "DeepSeek AI"
            },
            "perplexity": {
                "name": "Perplexity",
                "url": "https://www.perplexity.ai",
                "category": "AI",
                "icon": "🔍",
                "description": "AI Search"
            },

            # Penterra/Title Work
            "penterra_sharefile": {
                "name": "Penterra ShareFile",
                "url": "https://penterra.sharefile.com",
                "category": "Penterra",
                "icon": "📁",
                "shortcut": "PSF",
                "description": "Document sharing"
            },
            "moea": {
                "name": "MOEA",
                "url": "https://moea.ok.gov",
                "category": "Penterra",
                "icon": "💰",
                "description": "Missing Owner Escrow Authority"
            },
            "ok_county_records": {
                "name": "OK County Records",
                "url": "https://www.okcountyrecords.com",
                "category": "Penterra",
                "icon": "📜",
                "description": "Oklahoma County Records"
            },
            "oklahoma_tax_commission": {
                "name": "Oklahoma Tax Commission",
                "url": "https://oktap.tax.ok.gov",
                "category": "Penterra",
                "icon": "💵",
                "description": "Tax records"
            },

            # Genealogy
            "familysearch": {
                "name": "FamilySearch",
                "url": "https://www.familysearch.org",
                "category": "Genealogy",
                "icon": "🌳",
                "description": "Free genealogy research"
            },
            "ancestry": {
                "name": "Ancestry",
                "url": "https://www.ancestry.com",
                "category": "Genealogy",
                "icon": "🧬",
                "description": "Ancestry research"
            },
            "findagrave": {
                "name": "FindAGrave",
                "url": "https://www.findagrave.com",
                "category": "Genealogy",
                "icon": "⚰️",
                "description": "Cemetery records"
            },

            # Research
            "google": {
                "name": "Google",
                "url": "https://www.google.com",
                "category": "Research",
                "icon": "🔎",
                "description": "Search engine"
            },
            "google_maps": {
                "name": "Google Maps",
                "url": "https://maps.google.com",
                "category": "Research",
                "icon": "🗺️",
                "description": "Maps and locations"
            },
            "wikipedia": {
                "name": "Wikipedia",
                "url": "https://www.wikipedia.org",
                "category": "Research",
                "icon": "📚",
                "description": "Encyclopedia"
            },

            # Productivity
            "github": {
                "name": "GitHub",
                "url": "https://github.com",
                "category": "Development",
                "icon": "🐙",
                "description": "Code repository"
            },
            "google_drive": {
                "name": "Google Drive",
                "url": "https://drive.google.com",
                "category": "Productivity",
                "icon": "💾",
                "description": "Cloud storage"
            },
            "google_docs": {
                "name": "Google Docs",
                "url": "https://docs.google.com",
                "category": "Productivity",
                "icon": "📝",
                "description": "Document editing"
            },

            # Real Estate
            "zillow": {
                "name": "Zillow",
                "url": "https://www.zillow.com",
                "category": "Real Estate",
                "icon": "🏠",
                "description": "Real estate listings"
            },
            "realtor": {
                "name": "Realtor.com",
                "url": "https://www.realtor.com",
                "category": "Real Estate",
                "icon": "🏡",
                "description": "Property search"
            }
        }

        # Workflow groups
        self.workflow_groups = {
            "missing_owner": {
                "name": "Missing Owner Workflow",
                "description": "Complete workflow for missing owner research",
                "links": ["moea", "ok_county_records", "penterra_sharefile", "familysearch"],
                "icon": "🔍"
            },
            "ai_stack": {
                "name": "Launch AI Stack",
                "description": "Open all AI tools simultaneously",
                "links": ["chatgpt", "claude", "gemini", "deepseek", "perplexity"],
                "icon": "🚀"
            },
            "genealogy_research": {
                "name": "Genealogy Research",
                "description": "Full genealogy research toolkit",
                "links": ["familysearch", "ancestry", "findagrave", "google"],
                "icon": "🌳"
            },
            "title_research": {
                "name": "Title Research",
                "description": "Complete title research workflow",
                "links": ["ok_county_records", "oklahoma_tax_commission", "google_maps"],
                "icon": "📜"
            },
            "real_estate_deals": {
                "name": "Real Estate Deals",
                "description": "Property research and deals",
                "links": ["zillow", "realtor", "google_maps", "ok_county_records"],
                "icon": "💰"
            }
        }

        self.save_links()

    def save_links(self):
        """Save links configuration to file"""
        try:
            data = {
                "links": self.links,
                "workflow_groups": self.workflow_groups,
                "usage_stats": dict(self.usage_stats),
                "last_updated": datetime.now().isoformat()
            }
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=4)
            logger.info("Links configuration saved")
        except Exception as e:
            logger.error(f"Error saving links: {e}")

    def open_link(self, link_id: str) -> bool:
        """
        Open a link in default browser.

        Args:
            link_id: Link identifier

        Returns:
            Success status
        """
        try:
            if link_id not in self.links:
                logger.warning(f"Link not found: {link_id}")
                return False

            url = self.links[link_id]['url']
            webbrowser.open(url)

            # Track usage
            self.usage_stats[link_id] += 1
            self.save_links()

            logger.info(f"Opened link: {self.links[link_id]['name']}")
            return True

        except Exception as e:
            logger.error(f"Error opening link {link_id}: {e}")
            return False

    def open_workflow_group(self, group_id: str) -> bool:
        """
        Open all links in a workflow group.

        Args:
            group_id: Workflow group identifier

        Returns:
            Success status
        """
        try:
            if group_id not in self.workflow_groups:
                logger.warning(f"Workflow group not found: {group_id}")
                return False

            group = self.workflow_groups[group_id]
            for link_id in group['links']:
                self.open_link(link_id)

            logger.info(f"Opened workflow group: {group['name']}")
            return True

        except Exception as e:
            logger.error(f"Error opening workflow group {group_id}: {e}")
            return False

    def get_all_links(self) -> Dict[str, Any]:
        """Get all links"""
        return self.links

    def get_links_by_category(self, category: str) -> Dict[str, Any]:
        """
        Get links filtered by category.

        Args:
            category: Category name

        Returns:
            Filtered links dictionary
        """
        return {
            k: v for k, v in self.links.items()
            if v.get('category') == category
        }

    def get_categories(self) -> List[str]:
        """Get all unique categories"""
        categories = set()
        for link in self.links.values():
            categories.add(link.get('category', 'Uncategorized'))
        return sorted(list(categories))

    def get_most_used_links(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most frequently used links.

        Args:
            limit: Maximum number of links

        Returns:
            List of link dictionaries with usage count
        """
        sorted_links = sorted(
            self.usage_stats.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]

        return [
            {
                "id": link_id,
                "name": self.links[link_id]['name'],
                "url": self.links[link_id]['url'],
                "usage_count": count
            }
            for link_id, count in sorted_links
            if link_id in self.links
        ]

    def add_link(self, link_id: str, name: str, url: str, category: str = "Custom",
                 icon: str = "🔗", description: str = "") -> bool:
        """
        Add a new link.

        Args:
            link_id: Unique identifier
            name: Display name
            url: URL
            category: Category
            icon: Icon emoji
            description: Description

        Returns:
            Success status
        """
        try:
            self.links[link_id] = {
                "name": name,
                "url": url,
                "category": category,
                "icon": icon,
                "description": description
            }
            self.save_links()
            logger.info(f"Link added: {name}")
            return True

        except Exception as e:
            logger.error(f"Error adding link: {e}")
            return False

    def remove_link(self, link_id: str) -> bool:
        """
        Remove a link.

        Args:
            link_id: Link identifier

        Returns:
            Success status
        """
        try:
            if link_id in self.links:
                del self.links[link_id]
                if link_id in self.usage_stats:
                    del self.usage_stats[link_id]
                self.save_links()
                logger.info(f"Link removed: {link_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error removing link: {e}")
            return False

    def get_workflow_groups(self) -> Dict[str, Any]:
        """Get all workflow groups"""
        return self.workflow_groups

    def suggest_workflow(self, recent_links: List[str]) -> Optional[str]:
        """
        Suggest a workflow group based on recent link usage.

        Args:
            recent_links: List of recently used link IDs

        Returns:
            Suggested workflow group ID or None
        """
        if not recent_links:
            return None

        # Find workflow groups that match recent usage
        best_match = None
        best_score = 0

        for group_id, group in self.workflow_groups.items():
            group_links = set(group['links'])
            recent_set = set(recent_links)
            overlap = len(group_links & recent_set)

            if overlap > best_score:
                best_score = overlap
                best_match = group_id

        return best_match if best_score >= 2 else None


if __name__ == "__main__":
    # Test the LinksManager
    manager = LinksManager()

    print(f"Total links: {len(manager.get_all_links())}")
    print(f"Categories: {manager.get_categories()}")
    print(f"Workflow groups: {list(manager.get_workflow_groups().keys())}")

    # Simulate opening AI Stack
    print("\nOpening AI Stack...")
    # manager.open_workflow_group("ai_stack")  # Commented to avoid actually opening browsers
