"""
DataBossX Deals Engine
Manages business opportunities, missing owner cases, and deal scoring.
Generates contact packages and tracks revenue opportunities.
"""

import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class Deal:
    """
    Represents a business opportunity or deal.
    """

    def __init__(self, deal_id: Optional[int] = None, title: str = "",
                 category: str = "Missing Owner", description: str = "",
                 estimated_value: float = 0.0, difficulty: str = "Medium",
                 deal_score: int = 50, contact_name: str = "",
                 contact_info: str = "", status: str = "Prospect",
                 created_at: Optional[str] = None, updated_at: Optional[str] = None,
                 notes: str = "", legal_description: str = "",
                 county: str = "", state: str = "Oklahoma"):
        """
        Initialize a Deal.

        Args:
            deal_id: Unique identifier
            title: Deal title
            category: Category (Missing Owner, Mineral Rights, Real Estate)
            description: Deal description
            estimated_value: Estimated dollar value
            difficulty: Difficulty level (Easy, Medium, Hard)
            deal_score: AI-calculated score (0-100)
            contact_name: Contact person name
            contact_info: Contact information
            status: Current status (Prospect, Contacted, Negotiating, Closed, Dead)
            created_at: Creation timestamp
            updated_at: Last update timestamp
            notes: Additional notes
            legal_description: Legal description if applicable
            county: County
            state: State
        """
        self.deal_id = deal_id
        self.title = title
        self.category = category
        self.description = description
        self.estimated_value = estimated_value
        self.difficulty = difficulty
        self.deal_score = deal_score
        self.contact_name = contact_name
        self.contact_info = contact_info
        self.status = status
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or datetime.now().isoformat()
        self.notes = notes
        self.legal_description = legal_description
        self.county = county
        self.state = state

    def to_dict(self) -> Dict[str, Any]:
        """Convert deal to dictionary."""
        return {
            'deal_id': self.deal_id,
            'title': self.title,
            'category': self.category,
            'description': self.description,
            'estimated_value': self.estimated_value,
            'difficulty': self.difficulty,
            'deal_score': self.deal_score,
            'contact_name': self.contact_name,
            'contact_info': self.contact_info,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'notes': self.notes,
            'legal_description': self.legal_description,
            'county': self.county,
            'state': self.state,
        }


class DealsEngine:
    """
    Manages deals and generates contact packages.
    """

    def __init__(self, db_path: str = "databossx_deals.db",
                 output_dir: str = "output/deals"):
        """
        Initialize the DealsEngine.

        Args:
            db_path: Path to SQLite database
            output_dir: Directory for output files
        """
        self.db_path = db_path
        self.output_dir = output_dir
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self) -> None:
        """
        Initialize the database schema.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Create deals table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS deals (
                        deal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        category TEXT DEFAULT 'Missing Owner',
                        description TEXT,
                        estimated_value REAL DEFAULT 0.0,
                        difficulty TEXT DEFAULT 'Medium',
                        deal_score INTEGER DEFAULT 50,
                        contact_name TEXT,
                        contact_info TEXT,
                        status TEXT DEFAULT 'Prospect',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        notes TEXT,
                        legal_description TEXT,
                        county TEXT,
                        state TEXT DEFAULT 'Oklahoma'
                    )
                """)

                # Create indexes
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_category ON deals(category)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_status ON deals(status)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_deal_score ON deals(deal_score DESC)
                """)

                conn.commit()
                logger.info(f"Deals database initialized: {self.db_path}")

        except Exception as e:
            logger.error(f"Error initializing deals database: {e}")
            raise

    def add_deal(self, deal: Deal) -> int:
        """
        Add a new deal.

        Args:
            deal: Deal object

        Returns:
            Deal ID
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO deals (title, category, description, estimated_value,
                                     difficulty, deal_score, contact_name, contact_info,
                                     status, created_at, updated_at, notes,
                                     legal_description, county, state)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    deal.title, deal.category, deal.description, deal.estimated_value,
                    deal.difficulty, deal.deal_score, deal.contact_name, deal.contact_info,
                    deal.status, deal.created_at, deal.updated_at, deal.notes,
                    deal.legal_description, deal.county, deal.state
                ))

                deal_id = cursor.lastrowid
                conn.commit()
                logger.info(f"Deal added: {deal_id} - {deal.title}")
                return deal_id

        except Exception as e:
            logger.error(f"Error adding deal: {e}")
            raise

    def get_deal(self, deal_id: int) -> Optional[Deal]:
        """
        Get a deal by ID.

        Args:
            deal_id: Deal ID

        Returns:
            Deal object or None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM deals WHERE deal_id = ?", (deal_id,))
                row = cursor.fetchone()

                if row:
                    return Deal(**dict(row))
                return None

        except Exception as e:
            logger.error(f"Error retrieving deal: {e}")
            return None

    def update_deal(self, deal: Deal) -> bool:
        """
        Update a deal.

        Args:
            deal: Deal object with updated values

        Returns:
            True if successful
        """
        try:
            deal.updated_at = datetime.now().isoformat()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE deals
                    SET title = ?, category = ?, description = ?, estimated_value = ?,
                        difficulty = ?, deal_score = ?, contact_name = ?, contact_info = ?,
                        status = ?, updated_at = ?, notes = ?, legal_description = ?,
                        county = ?, state = ?
                    WHERE deal_id = ?
                """, (
                    deal.title, deal.category, deal.description, deal.estimated_value,
                    deal.difficulty, deal.deal_score, deal.contact_name, deal.contact_info,
                    deal.status, deal.updated_at, deal.notes, deal.legal_description,
                    deal.county, deal.state, deal.deal_id
                ))

                conn.commit()
                logger.info(f"Deal updated: {deal.deal_id}")
                return True

        except Exception as e:
            logger.error(f"Error updating deal: {e}")
            return False

    def get_deals(self, category: Optional[str] = None, status: Optional[str] = None,
                  min_score: Optional[int] = None, limit: Optional[int] = None) -> List[Deal]:
        """
        Get deals with optional filtering.

        Args:
            category: Filter by category
            status: Filter by status
            min_score: Minimum deal score
            limit: Maximum number of deals

        Returns:
            List of Deal objects
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                query = "SELECT * FROM deals WHERE 1=1"
                params = []

                if category:
                    query += " AND category = ?"
                    params.append(category)

                if status:
                    query += " AND status = ?"
                    params.append(status)

                if min_score is not None:
                    query += " AND deal_score >= ?"
                    params.append(min_score)

                query += " ORDER BY deal_score DESC, estimated_value DESC"

                if limit:
                    query += f" LIMIT {limit}"

                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [Deal(**dict(row)) for row in rows]

        except Exception as e:
            logger.error(f"Error retrieving deals: {e}")
            return []

    def calculate_deal_score(self, deal: Deal, use_ai: bool = True) -> int:
        """
        Calculate deal score based on value and difficulty.

        Args:
            deal: Deal to score
            use_ai: Whether to use AI (future enhancement)

        Returns:
            Score from 0-100
        """
        score = 50  # Base score

        # Value component (0-40 points)
        if deal.estimated_value >= 100000:
            score += 40
        elif deal.estimated_value >= 50000:
            score += 30
        elif deal.estimated_value >= 25000:
            score += 20
        elif deal.estimated_value >= 10000:
            score += 10

        # Difficulty component (0-30 points, inverse)
        difficulty_scores = {
            'Easy': 30,
            'Medium': 20,
            'Hard': 10
        }
        score += difficulty_scores.get(deal.difficulty, 20)

        # Status component (0-20 points)
        status_scores = {
            'Prospect': 10,
            'Contacted': 15,
            'Negotiating': 20,
            'Closed': 0,  # Closed deals don't need scoring
            'Dead': 0
        }
        score += status_scores.get(deal.status, 10)

        # Category boost
        if deal.category == "Missing Owner":
            score += 5  # These are high-value opportunities

        # Keep in 0-100 range
        return max(0, min(100, score))

    def generate_contact_package(self, deal_id: int, use_llm: bool = True) -> Dict[str, Any]:
        """
        Generate contact package (email and letter) for a deal.

        Args:
            deal_id: Deal ID
            use_llm: Whether to use LLM for generation

        Returns:
            Dictionary with file paths and content
        """
        deal = self.get_deal(deal_id)
        if not deal:
            return {'success': False, 'error': 'Deal not found'}

        try:
            # Generate email content
            email_content = self._generate_email(deal, use_llm)

            # Generate letter content
            letter_content = self._generate_letter(deal, use_llm)

            # Save files
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"deal_{deal_id}_{timestamp}"

            email_path = Path(self.output_dir) / f"{base_name}_email.txt"
            letter_path = Path(self.output_dir) / f"{base_name}_letter.txt"
            metadata_path = Path(self.output_dir) / f"{base_name}_metadata.json"

            # Write email
            with open(email_path, 'w', encoding='utf-8') as f:
                f.write(email_content)

            # Write letter
            with open(letter_path, 'w', encoding='utf-8') as f:
                f.write(letter_content)

            # Write metadata
            metadata = {
                'deal_id': deal_id,
                'deal_title': deal.title,
                'contact_name': deal.contact_name,
                'generated_at': datetime.now().isoformat(),
                'email_path': str(email_path),
                'letter_path': str(letter_path)
            }
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Contact package generated for deal {deal_id}")

            return {
                'success': True,
                'email_path': str(email_path),
                'letter_path': str(letter_path),
                'metadata_path': str(metadata_path),
                'email_content': email_content,
                'letter_content': letter_content
            }

        except Exception as e:
            logger.error(f"Error generating contact package: {e}")
            return {'success': False, 'error': str(e)}

    def _generate_email(self, deal: Deal, use_llm: bool) -> str:
        """
        Generate email content for a deal.

        Args:
            deal: Deal object
            use_llm: Whether to use LLM

        Returns:
            Email content
        """
        # Template-based generation (would use LLM in production)
        email = f"""Subject: Regarding {deal.category} - {deal.county} County, {deal.state}

Dear {deal.contact_name or 'Property Owner'},

I hope this message finds you well. My name is [Your Name] with DataBossX, and I'm reaching out regarding an important matter concerning property in {deal.county} County, {deal.state}.

{deal.description}

We have identified this as a valuable opportunity and would like to discuss the details with you at your convenience. Based on our research, the estimated value of this opportunity is approximately ${deal.estimated_value:,.2f}.

I would be happy to provide more information and answer any questions you may have. Please feel free to contact me at your earliest convenience.

{'[NOTE: This email was generated using AI-assisted drafting]' if use_llm else '[NOTE: This email was generated using a standard template]'}

Best regards,
[Your Name]
DataBossX
[Your Contact Information]

---
Reference: Deal #{deal.deal_id}
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}
"""
        return email

    def _generate_letter(self, deal: Deal, use_llm: bool) -> str:
        """
        Generate formal letter content for a deal.

        Args:
            deal: Deal object
            use_llm: Whether to use LLM

        Returns:
            Letter content
        """
        # Template-based generation (would use LLM in production)
        letter = f"""[Your Letterhead]
[Your Company Name]
[Address]
[City, State ZIP]
[Phone]
[Email]

{datetime.now().strftime("%B %d, %Y")}

{deal.contact_name or 'Property Owner'}
{deal.contact_info or '[Address]'}

Re: {deal.category} Opportunity - {deal.county} County, {deal.state}

Dear {deal.contact_name or 'Property Owner'}:

I am writing to bring to your attention an important matter regarding property interests in {deal.county} County, {deal.state}.

{deal.description}

Our research indicates this represents a significant opportunity with an estimated value of ${deal.estimated_value:,.2f}. We have extensive experience handling {deal.category.lower()} cases and would be pleased to assist you in this matter.

{deal.legal_description if deal.legal_description else '[Legal description would be inserted here]'}

We would welcome the opportunity to discuss this matter with you in detail. Please do not hesitate to contact us at your convenience to arrange a consultation.

{'[NOTE: This letter was generated using AI-assisted drafting]' if use_llm else '[NOTE: This letter was generated using a standard template]'}

Sincerely,

[Your Name]
[Your Title]
DataBossX

---
Reference: Deal #{deal.deal_id}
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}
"""
        return letter

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get deal statistics.

        Returns:
            Dictionary with statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                stats = {}

                # Total deals
                cursor.execute("SELECT COUNT(*) FROM deals")
                stats['total_deals'] = cursor.fetchone()[0]

                # By category
                cursor.execute("SELECT category, COUNT(*) FROM deals GROUP BY category")
                stats['by_category'] = dict(cursor.fetchall())

                # By status
                cursor.execute("SELECT status, COUNT(*) FROM deals GROUP BY status")
                stats['by_status'] = dict(cursor.fetchall())

                # Total estimated value
                cursor.execute("SELECT SUM(estimated_value) FROM deals WHERE status != 'Dead'")
                stats['total_estimated_value'] = cursor.fetchone()[0] or 0.0

                # Average deal score
                cursor.execute("SELECT AVG(deal_score) FROM deals WHERE status = 'Prospect'")
                stats['avg_deal_score'] = cursor.fetchone()[0] or 0.0

                return stats

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}


if __name__ == "__main__":
    # Test the DealsEngine
    print("Testing DealsEngine...")

    engine = DealsEngine()

    # Add sample deal
    sample_deal = Deal(
        title="Missing Owner - Section 15",
        category="Missing Owner",
        description="Potential missing owner case with mineral rights",
        estimated_value=75000.0,
        difficulty="Medium",
        contact_name="John Doe",
        contact_info="john.doe@example.com",
        county="Oklahoma",
        state="Oklahoma"
    )

    # Calculate score
    sample_deal.deal_score = engine.calculate_deal_score(sample_deal)

    deal_id = engine.add_deal(sample_deal)
    print(f"\nAdded deal {deal_id}: {sample_deal.title}")
    print(f"Deal Score: {sample_deal.deal_score}/100")

    # Show statistics
    stats = engine.get_statistics()
    print(f"\nStatistics: {json.dumps(stats, indent=2)}")
