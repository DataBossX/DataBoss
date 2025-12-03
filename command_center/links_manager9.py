"""
DataBossX Links Manager
Manages external links, apps, and workflow groups.
Tracks usage and suggests optimal workflows.
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path
import webbrowser

logger = logging.getLogger(__name__)


class Link:
    """
    Represents an external link or application.
    """

    def __init__(self, link_id: str, name: str, url: str, category: str,
                 icon: str = "🔗", description: str = "", shortcut: str = "",
                 usage_count: int = 0, last_used: Optional[str] = None,
                 tags: Optional[List[str]] = None):
        """
        Initialize a Link object.

        Args:
            link_id: Unique identifier
            name: Display name
            url: Target URL
            category: Category (AI, Research, County, Communication, etc.)
            icon: Emoji icon
            description: Brief description
            shortcut: Keyboard shortcut hint
            usage_count: Number of times used
            last_used: ISO timestamp of last use
            tags: List of tags for grouping
        """
        self.link_id = link_id
        self.name = name
        self.url = url
        self.category = category
        self.icon = icon
        self.description = description
        self.shortcut = shortcut
        self.usage_count = usage_count
        self.last_used = last_used
        self.tags = tags or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert link to dictionary."""
        return {
            'link_id': self.link_id,
            'name': self.name,
            'url': self.url,
            'category': self.category,
            'icon': self.icon,
            'description': self.description,
            'shortcut': self.shortcut,
            'usage_count': self.usage_count,
            'last_used': self.last_used,
            'tags': self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Link':
        """Create Link from dictionary."""
        return cls(**data)


class WorkflowGroup:
    """
    Represents a group of links that work together as a workflow.
    """

    def __init__(self, group_id: str, name: str, description: str,
                 link_ids: List[str], icon: str = "⚡"):
        """
        Initialize a WorkflowGroup.

        Args:
            group_id: Unique identifier
            name: Group name
            description: What this workflow is for
            link_ids: List of link IDs in this group
            icon: Emoji icon
        """
        self.group_id = group_id
        self.name = name
        self.description = description
        self.link_ids = link_ids
        self.icon = icon

    def to_dict(self) -> Dict[str, Any]:
        """Convert workflow group to dictionary."""
        return {
            'group_id': self.group_id,
            'name': self.name,
            'description': self.description,
            'link_ids': self.link_ids,
            'icon': self.icon,
        }


class LinksManager:
    """
    Manages links, apps, and workflow groups.
    """

    def __init__(self, config_file: str = "links_config9.json"):
        """
        Initialize the LinksManager.

        Args:
            config_file: Path to the links configuration file
        """
        self.config_file = config_file
        self.links: Dict[str, Link] = {}
        self.workflow_groups: Dict[str, WorkflowGroup] = {}
        self._load_or_create_config()

    def _get_default_links(self) -> List[Dict[str, Any]]:
        """
        Get default links configuration.

        Returns:
            List of default link dictionaries
        """
        return [
            # AI Tools
            {
                "link_id": "chatgpt",
                "name": "ChatGPT",
                "url": "https://chat.openai.com",
                "category": "AI",
                "icon": "🤖",
                "description": "OpenAI ChatGPT",
                "shortcut": "GPT",
                "tags": ["ai", "chat", "research"]
            },
            {
                "link_id": "claude",
                "name": "Claude",
                "url": "https://claude.ai",
                "category": "AI",
                "icon": "🧠",
                "description": "Anthropic Claude",
                "shortcut": "CLD",
                "tags": ["ai", "chat", "research"]
            },
            {
                "link_id": "gemini",
                "name": "Gemini",
                "url": "https://gemini.google.com",
                "category": "AI",
                "icon": "✨",
                "description": "Google Gemini",
                "shortcut": "GEM",
                "tags": ["ai", "chat", "research"]
            },
            {
                "link_id": "deepseek",
                "name": "DeepSeek",
                "url": "https://chat.deepseek.com",
                "category": "AI",
                "icon": "🔍",
                "description": "DeepSeek AI",
                "shortcut": "DSK",
                "tags": ["ai", "chat", "research"]
            },
            {
                "link_id": "perplexity",
                "name": "Perplexity",
                "url": "https://www.perplexity.ai",
                "category": "AI",
                "icon": "🎯",
                "description": "Perplexity AI Search",
                "shortcut": "PER",
                "tags": ["ai", "search", "research"]
            },

            # Communication
            {
                "link_id": "aol",
                "name": "AOL Mail",
                "url": "https://mail.aol.com",
                "category": "Communication",
                "icon": "📧",
                "description": "AOL Email",
                "shortcut": "AOL",
                "tags": ["email", "communication"]
            },
            {
                "link_id": "gmail",
                "name": "Gmail",
                "url": "https://mail.google.com",
                "category": "Communication",
                "icon": "📬",
                "description": "Google Mail",
                "shortcut": "GML",
                "tags": ["email", "communication"]
            },

            # Penterra / Land Work
            {
                "link_id": "moea",
                "name": "MOEA",
                "url": "https://app.moea.com",
                "category": "Penterra",
                "icon": "💰",
                "description": "Missing Owner Escrow",
                "shortcut": "MOEA",
                "tags": ["penterra", "missing-owner", "escrow"]
            },
            {
                "link_id": "penterra_sharefile",
                "name": "Penterra ShareFile",
                "url": "https://penterra.sharefile.com",
                "category": "Penterra",
                "icon": "📁",
                "description": "Penterra document repository",
                "shortcut": "PSF",
                "tags": ["penterra", "documents", "storage"]
            },
            {
                "link_id": "ok_county_records",
                "name": "OK County Records",
                "url": "https://www.okcountyrecords.com",
                "category": "Research",
                "icon": "📋",
                "description": "Oklahoma County land records",
                "shortcut": "OKC",
                "tags": ["county", "records", "research", "penterra"]
            },
            {
                "link_id": "ok_tax_commission",
                "name": "OK Tax Commission",
                "url": "https://oktap.tax.ok.gov",
                "category": "Research",
                "icon": "🏛️",
                "description": "Oklahoma Tax Commission",
                "shortcut": "TAX",
                "tags": ["tax", "research", "oklahoma"]
            },

            # Genealogy
            {
                "link_id": "familysearch",
                "name": "FamilySearch",
                "url": "https://www.familysearch.org",
                "category": "Genealogy",
                "icon": "🌳",
                "description": "Family history research",
                "shortcut": "FS",
                "tags": ["genealogy", "family", "research"]
            },
            {
                "link_id": "ancestry",
                "name": "Ancestry",
                "url": "https://www.ancestry.com",
                "category": "Genealogy",
                "icon": "🧬",
                "description": "Ancestry research",
                "shortcut": "ANC",
                "tags": ["genealogy", "family", "research"]
            },
            {
                "link_id": "findagrave",
                "name": "Find A Grave",
                "url": "https://www.findagrave.com",
                "category": "Genealogy",
                "icon": "⚰️",
                "description": "Cemetery records",
                "shortcut": "FAG",
                "tags": ["genealogy", "cemetery", "research"]
            },

            # Development & Tools
            {
                "link_id": "github",
                "name": "GitHub",
                "url": "https://github.com",
                "category": "Development",
                "icon": "🐙",
                "description": "Code repository",
                "shortcut": "GH",
                "tags": ["development", "code", "git"]
            },
            {
                "link_id": "stackoverflow",
                "name": "Stack Overflow",
                "url": "https://stackoverflow.com",
                "category": "Development",
                "icon": "💻",
                "description": "Developer Q&A",
                "shortcut": "SO",
                "tags": ["development", "help", "programming"]
            },

            # Maps & Location
            {
                "link_id": "google_maps",
                "name": "Google Maps",
                "url": "https://maps.google.com",
                "category": "Maps",
                "icon": "🗺️",
                "description": "Google Maps",
                "shortcut": "MAP",
                "tags": ["maps", "location", "research"]
            },
            {
                "link_id": "google_earth",
                "name": "Google Earth",
                "url": "https://earth.google.com",
                "category": "Maps",
                "icon": "🌍",
                "description": "Google Earth",
                "shortcut": "GE",
                "tags": ["maps", "location", "research", "satellite"]
            },

            # Real Estate
            {
                "link_id": "zillow",
                "name": "Zillow",
                "url": "https://www.zillow.com",
                "category": "Real Estate",
                "icon": "🏠",
                "description": "Real estate listings",
                "shortcut": "ZIL",
                "tags": ["real-estate", "property", "research"]
            },
            {
                "link_id": "realtor",
                "name": "Realtor.com",
                "url": "https://www.realtor.com",
                "category": "Real Estate",
                "icon": "🏘️",
                "description": "Property listings",
                "shortcut": "RLT",
                "tags": ["real-estate", "property", "research"]
            },

            # Reference
            {
                "link_id": "wikipedia",
                "name": "Wikipedia",
                "url": "https://www.wikipedia.org",
                "category": "Reference",
                "icon": "📚",
                "description": "Wikipedia encyclopedia",
                "shortcut": "WIKI",
                "tags": ["reference", "research", "encyclopedia"]
            },
        ]

    def _get_default_workflow_groups(self) -> List[Dict[str, Any]]:
        """
        Get default workflow groups.

        Returns:
            List of default workflow group dictionaries
        """
        return [
            {
                "group_id": "ai_stack",
                "name": "AI Stack",
                "description": "All AI tools for research and problem-solving",
                "link_ids": ["chatgpt", "claude", "gemini", "deepseek", "perplexity"],
                "icon": "🚀"
            },
            {
                "group_id": "missing_owner_workflow",
                "name": "Missing Owner Workflow",
                "description": "Tools for missing owner research and escrow",
                "link_ids": ["moea", "penterra_sharefile", "ok_county_records", "familysearch"],
                "icon": "💼"
            },
            {
                "group_id": "genealogy_workflow",
                "name": "Genealogy Research",
                "description": "Family history research tools",
                "link_ids": ["familysearch", "ancestry", "findagrave", "google_maps"],
                "icon": "🌳"
            },
            {
                "group_id": "property_research",
                "name": "Property Research",
                "description": "Real estate and land research tools",
                "link_ids": ["ok_county_records", "ok_tax_commission", "zillow", "realtor", "google_earth"],
                "icon": "🏡"
            },
        ]

    def _load_or_create_config(self) -> None:
        """
        Load configuration from file or create default.
        """
        try:
            if Path(self.config_file).exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                # Load links
                for link_data in config.get('links', []):
                    link = Link.from_dict(link_data)
                    self.links[link.link_id] = link

                # Load workflow groups
                for group_data in config.get('workflow_groups', []):
                    group = WorkflowGroup(**group_data)
                    self.workflow_groups[group.group_id] = group

                logger.info(f"Links configuration loaded: {len(self.links)} links, {len(self.workflow_groups)} groups")

            else:
                logger.info("Creating default links configuration")
                # Create default links
                for link_data in self._get_default_links():
                    link = Link(**link_data)
                    self.links[link.link_id] = link

                # Create default workflow groups
                for group_data in self._get_default_workflow_groups():
                    group = WorkflowGroup(**group_data)
                    self.workflow_groups[group.group_id] = group

                self.save_config()

        except Exception as e:
            logger.error(f"Error loading links configuration: {e}")
            raise

    def save_config(self) -> bool:
        """
        Save configuration to file.

        Returns:
            True if successful
        """
        try:
            config = {
                'links': [link.to_dict() for link in self.links.values()],
                'workflow_groups': [group.to_dict() for group in self.workflow_groups.values()],
                'last_updated': datetime.now().isoformat()
            }

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            logger.info(f"Links configuration saved to {self.config_file}")
            return True

        except Exception as e:
            logger.error(f"Error saving links configuration: {e}")
            return False

    def get_link(self, link_id: str) -> Optional[Link]:
        """Get a link by ID."""
        return self.links.get(link_id)

    def get_links_by_category(self, category: str) -> List[Link]:
        """Get all links in a category."""
        return [link for link in self.links.values() if link.category == category]

    def get_all_categories(self) -> List[str]:
        """Get list of all categories."""
        return sorted(set(link.category for link in self.links.values()))

    def open_link(self, link_id: str) -> bool:
        """
        Open a link in the default browser and track usage.

        Args:
            link_id: ID of link to open

        Returns:
            True if successful
        """
        link = self.get_link(link_id)
        if not link:
            logger.error(f"Link not found: {link_id}")
            return False

        try:
            webbrowser.open(link.url)
            link.usage_count += 1
            link.last_used = datetime.now().isoformat()
            self.save_config()
            logger.info(f"Opened link: {link.name}")
            return True

        except Exception as e:
            logger.error(f"Error opening link: {e}")
            return False

    def open_workflow_group(self, group_id: str) -> bool:
        """
        Open all links in a workflow group.

        Args:
            group_id: ID of workflow group

        Returns:
            True if successful
        """
        group = self.workflow_groups.get(group_id)
        if not group:
            logger.error(f"Workflow group not found: {group_id}")
            return False

        try:
            for link_id in group.link_ids:
                self.open_link(link_id)

            logger.info(f"Opened workflow group: {group.name}")
            return True

        except Exception as e:
            logger.error(f"Error opening workflow group: {e}")
            return False

    def get_most_used_links(self, limit: int = 10) -> List[Link]:
        """
        Get most frequently used links.

        Args:
            limit: Maximum number of links to return

        Returns:
            List of most used links
        """
        sorted_links = sorted(
            self.links.values(),
            key=lambda l: l.usage_count,
            reverse=True
        )
        return sorted_links[:limit]

    def search_links(self, query: str) -> List[Link]:
        """
        Search links by name, description, or tags.

        Args:
            query: Search query

        Returns:
            List of matching links
        """
        query_lower = query.lower()
        results = []

        for link in self.links.values():
            if (query_lower in link.name.lower() or
                query_lower in link.description.lower() or
                any(query_lower in tag.lower() for tag in link.tags)):
                results.append(link)

        return results


if __name__ == "__main__":
    # Test the LinksManager
    print("Testing LinksManager...")

    manager = LinksManager()

    print(f"\nTotal links: {len(manager.links)}")
    print(f"Categories: {', '.join(manager.get_all_categories())}")
    print(f"Workflow groups: {len(manager.workflow_groups)}")

    # Show AI tools
    print("\nAI Tools:")
    for link in manager.get_links_by_category("AI"):
        print(f"  {link.icon} {link.name} - {link.url}")

    # Show workflow groups
    print("\nWorkflow Groups:")
    for group in manager.workflow_groups.values():
        print(f"  {group.icon} {group.name}: {group.description}")

    print(f"\nConfiguration saved to: {manager.config_file}")
