"""
DataBossX Deals Engine v9
Tracks money-making opportunities with AI-powered scoring and contact generation
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import json

from config_databossx9 import get_config

# Configure logging
logger = logging.getLogger(__name__)


class DealsEngine:
    """
    Manages money-making opportunities including missing owners,
    mineral rights, and real estate deals with AI scoring.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize Deals Engine.

        Args:
            db_path: Path to SQLite database
        """
        config = get_config()
        self.db_path = db_path or config.get('paths', 'database_path', 'databossx.db')
        self.deals_folder = Path(config.get('paths', 'deals_folder', 'output/deals'))
        self.deal_types = config.get('deals', 'deal_types', [])
        self.min_score = config.get('deals', 'min_score_threshold', 60)

        # Ensure deals folder exists
        self.deals_folder.mkdir(parents=True, exist_ok=True)

        self._init_database()
        logger.info("DealsEngine initialized")

    def _init_database(self):
        """Initialize deals database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Deals table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS deals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deal_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    prospect_name TEXT,
                    prospect_address TEXT,
                    prospect_phone TEXT,
                    prospect_email TEXT,
                    property_address TEXT,
                    county TEXT,
                    state TEXT,
                    estimated_value REAL,
                    difficulty_level TEXT,
                    deal_score REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'New',
                    priority TEXT DEFAULT 'Medium',
                    source TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    contacted_at TEXT,
                    closed_at TEXT,
                    revenue REAL
                )
            """)

            # Deal contacts/communications table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS deal_contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deal_id INTEGER NOT NULL,
                    contact_type TEXT NOT NULL,
                    contact_method TEXT,
                    contact_date TEXT NOT NULL,
                    notes TEXT,
                    response_received BOOLEAN DEFAULT 0,
                    FOREIGN KEY (deal_id) REFERENCES deals (id)
                )
            """)

            # Deal documents table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS deal_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deal_id INTEGER NOT NULL,
                    document_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (deal_id) REFERENCES deals (id)
                )
            """)

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_deals_score ON deals(deal_score)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_deals_status ON deals(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_deals_type ON deals(deal_type)")

            conn.commit()
            conn.close()
            logger.info("Deals database initialized")

        except Exception as e:
            logger.error(f"Error initializing deals database: {e}")
            raise

    def add_deal(self, deal_type: str, title: str, description: str = "",
                 prospect_name: str = "", property_address: str = "",
                 estimated_value: float = 0.0, **kwargs) -> int:
        """
        Add a new deal opportunity.

        Args:
            deal_type: Type of deal
            title: Deal title
            description: Deal description
            prospect_name: Name of prospect
            property_address: Property address
            estimated_value: Estimated value
            **kwargs: Additional fields

        Returns:
            Deal ID
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            now = datetime.now().isoformat()

            # Calculate initial deal score
            deal_data = {
                'deal_type': deal_type,
                'estimated_value': estimated_value,
                'difficulty_level': kwargs.get('difficulty_level', 'Medium'),
                **kwargs
            }
            deal_score = self._calculate_deal_score(deal_data)

            cursor.execute("""
                INSERT INTO deals (
                    deal_type, title, description, prospect_name, prospect_address,
                    prospect_phone, prospect_email, property_address, county, state,
                    estimated_value, difficulty_level, deal_score, status, priority,
                    source, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                deal_type, title, description, prospect_name,
                kwargs.get('prospect_address', ''),
                kwargs.get('prospect_phone', ''),
                kwargs.get('prospect_email', ''),
                property_address,
                kwargs.get('county', ''),
                kwargs.get('state', ''),
                estimated_value,
                kwargs.get('difficulty_level', 'Medium'),
                deal_score,
                kwargs.get('status', 'New'),
                kwargs.get('priority', 'Medium'),
                kwargs.get('source', ''),
                kwargs.get('notes', ''),
                now, now
            ))

            deal_id = cursor.lastrowid
            conn.commit()
            conn.close()

            logger.info(f"Deal added: {deal_id} - {title} (Score: {deal_score})")
            return deal_id

        except Exception as e:
            logger.error(f"Error adding deal: {e}")
            raise

    def _calculate_deal_score(self, deal_data: Dict[str, Any]) -> float:
        """
        Calculate AI deal score (0-100).
        Higher score = better opportunity.

        Args:
            deal_data: Deal data dictionary

        Returns:
            Deal score (0-100)
        """
        score = 0.0

        # Value score (0-40 points)
        estimated_value = deal_data.get('estimated_value', 0)
        if estimated_value > 0:
            if estimated_value >= 100000:
                score += 40
            elif estimated_value >= 50000:
                score += 30
            elif estimated_value >= 10000:
                score += 20
            elif estimated_value >= 5000:
                score += 10
            else:
                score += 5

        # Difficulty score (0-30 points) - inverse scoring
        difficulty_map = {
            'Easy': 30,
            'Medium': 20,
            'Hard': 10,
            'Very Hard': 5
        }
        difficulty = deal_data.get('difficulty_level', 'Medium')
        score += difficulty_map.get(difficulty, 15)

        # Deal type value (0-20 points)
        type_value_map = {
            'Missing Owner': 20,
            'Mineral Rights': 18,
            'Real Estate': 15,
            'Estate': 15,
            'Other': 10
        }
        deal_type = deal_data.get('deal_type', 'Other')
        score += type_value_map.get(deal_type, 10)

        # Contact information completeness (0-10 points)
        contact_score = 0
        if deal_data.get('prospect_name'):
            contact_score += 3
        if deal_data.get('prospect_address') or deal_data.get('property_address'):
            contact_score += 3
        if deal_data.get('prospect_phone'):
            contact_score += 2
        if deal_data.get('prospect_email'):
            contact_score += 2
        score += contact_score

        return min(100.0, score)

    def update_deal(self, deal_id: int, **updates) -> bool:
        """
        Update deal fields.

        Args:
            deal_id: Deal ID
            **updates: Fields to update

        Returns:
            Success status
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            valid_fields = [
                'deal_type', 'title', 'description', 'prospect_name', 'prospect_address',
                'prospect_phone', 'prospect_email', 'property_address', 'county', 'state',
                'estimated_value', 'difficulty_level', 'status', 'priority', 'notes',
                'contacted_at', 'closed_at', 'revenue'
            ]

            update_fields = {k: v for k, v in updates.items() if k in valid_fields}

            if not update_fields:
                return False

            update_fields['updated_at'] = datetime.now().isoformat()

            # Recalculate score if relevant fields changed
            if any(k in update_fields for k in ['estimated_value', 'difficulty_level']):
                cursor.execute("SELECT * FROM deals WHERE id = ?", (deal_id,))
                deal = cursor.fetchone()
                if deal:
                    # Merge current data with updates
                    deal_data = dict(zip(
                        [desc[0] for desc in cursor.description],
                        deal
                    ))
                    deal_data.update(update_fields)
                    update_fields['deal_score'] = self._calculate_deal_score(deal_data)

            # Build update query
            set_clause = ", ".join([f"{k} = ?" for k in update_fields.keys()])
            values = list(update_fields.values()) + [deal_id]

            cursor.execute(f"UPDATE deals SET {set_clause} WHERE id = ?", values)
            conn.commit()
            conn.close()

            logger.info(f"Deal updated: {deal_id}")
            return True

        except Exception as e:
            logger.error(f"Error updating deal {deal_id}: {e}")
            return False

    def get_deal(self, deal_id: int) -> Optional[Dict[str, Any]]:
        """
        Get deal by ID.

        Args:
            deal_id: Deal ID

        Returns:
            Deal dictionary or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM deals WHERE id = ?", (deal_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                return dict(row)
            return None

        except Exception as e:
            logger.error(f"Error getting deal {deal_id}: {e}")
            return None

    def get_deals(self, deal_type: Optional[str] = None, status: Optional[str] = None,
                  min_score: Optional[float] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get deals with optional filtering.

        Args:
            deal_type: Filter by deal type
            status: Filter by status
            min_score: Minimum deal score
            limit: Maximum number of deals

        Returns:
            List of deal dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM deals WHERE 1=1"
            params = []

            if deal_type:
                query += " AND deal_type = ?"
                params.append(deal_type)
            if status:
                query += " AND status = ?"
                params.append(status)
            if min_score is not None:
                query += " AND deal_score >= ?"
                params.append(min_score)

            query += " ORDER BY deal_score DESC, created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting deals: {e}")
            return []

    def get_top_deals(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top deals by score.

        Args:
            limit: Maximum number of deals

        Returns:
            List of top deal dictionaries
        """
        return self.get_deals(status="New", min_score=self.min_score, limit=limit)

    def generate_contact_package(self, deal_id: int) -> Dict[str, str]:
        """
        Generate email and letter for contacting prospect.

        Args:
            deal_id: Deal ID

        Returns:
            Dictionary with email and letter content
        """
        deal = self.get_deal(deal_id)
        if not deal:
            return {}

        # Generate email
        email_subject = f"Inquiry Regarding {deal['property_address'] or 'Your Property'}"
        email_body = f"""Dear {deal['prospect_name'] or 'Property Owner'},

I hope this message finds you well. My name is Rodney, and I work with DataBossX, a company specializing in {deal['deal_type'].lower()} opportunities.

We have identified a matter that may be of interest to you regarding {deal['property_address'] or 'property in ' + deal['county']}.

{deal['description']}

I would appreciate the opportunity to discuss this matter with you at your convenience. Please feel free to contact me at your earliest convenience.

Best regards,
Rodney
DataBossX
"""

        # Generate formal letter
        letter_content = f"""
[Your Letterhead]

{datetime.now().strftime('%B %d, %Y')}

{deal['prospect_name'] or 'Property Owner'}
{deal['prospect_address'] or ''}

Dear {deal['prospect_name'] or 'Sir/Madam'},

RE: {deal['title']}

I am writing to bring to your attention a matter regarding {deal['property_address'] or 'property in ' + deal['county'] + ' County, ' + deal['state']}.

{deal['description']}

We believe this represents a significant opportunity, with an estimated value of ${deal['estimated_value']:,.2f}.

I would welcome the opportunity to discuss this matter with you in greater detail. Please do not hesitate to contact me at your convenience.

Sincerely,

Rodney
DataBossX
"""

        # Save files
        try:
            deal_folder = self.deals_folder / f"deal_{deal_id}"
            deal_folder.mkdir(parents=True, exist_ok=True)

            email_file = deal_folder / f"email_{deal_id}.txt"
            letter_file = deal_folder / f"letter_{deal_id}.txt"

            with open(email_file, 'w') as f:
                f.write(f"Subject: {email_subject}\n\n{email_body}")

            with open(letter_file, 'w') as f:
                f.write(letter_content)

            # Record in database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO deal_documents (deal_id, document_type, file_path, created_at)
                VALUES (?, ?, ?, ?)
            """, (deal_id, "Email", str(email_file), datetime.now().isoformat()))

            cursor.execute("""
                INSERT INTO deal_documents (deal_id, document_type, file_path, created_at)
                VALUES (?, ?, ?, ?)
            """, (deal_id, "Letter", str(letter_file), datetime.now().isoformat()))

            conn.commit()
            conn.close()

            logger.info(f"Contact package generated for deal {deal_id}")

        except Exception as e:
            logger.error(f"Error saving contact package: {e}")

        return {
            'email_subject': email_subject,
            'email_body': email_body,
            'letter': letter_content
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get deal statistics.

        Returns:
            Statistics dictionary
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            stats = {}

            # Total deals
            cursor.execute("SELECT COUNT(*) FROM deals")
            stats['total_deals'] = cursor.fetchone()[0]

            # By status
            cursor.execute("SELECT status, COUNT(*) FROM deals GROUP BY status")
            stats['by_status'] = dict(cursor.fetchall())

            # By type
            cursor.execute("SELECT deal_type, COUNT(*) FROM deals GROUP BY deal_type")
            stats['by_type'] = dict(cursor.fetchall())

            # Total estimated value
            cursor.execute("SELECT SUM(estimated_value) FROM deals WHERE status != 'Closed'")
            total_value = cursor.fetchone()[0]
            stats['total_pipeline_value'] = total_value if total_value else 0

            # Total revenue
            cursor.execute("SELECT SUM(revenue) FROM deals WHERE status = 'Closed'")
            total_revenue = cursor.fetchone()[0]
            stats['total_revenue'] = total_revenue if total_revenue else 0

            # Average deal score
            cursor.execute("SELECT AVG(deal_score) FROM deals")
            avg_score = cursor.fetchone()[0]
            stats['avg_deal_score'] = avg_score if avg_score else 0

            # High priority deals
            cursor.execute("SELECT COUNT(*) FROM deals WHERE deal_score >= ? AND status = 'New'", (self.min_score,))
            stats['high_priority_deals'] = cursor.fetchone()[0]

            conn.close()
            return stats

        except Exception as e:
            logger.error(f"Error getting deal statistics: {e}")
            return {}


if __name__ == "__main__":
    # Test the DealsEngine
    engine = DealsEngine()

    # Add a sample deal
    deal_id = engine.add_deal(
        deal_type="Missing Owner",
        title="Oklahoma Mineral Rights - Smith Estate",
        description="Located mineral rights owner through research. Estate value estimated at $75,000.",
        prospect_name="John Smith",
        property_address="Section 12, Township 5N, Range 3W, Oklahoma County, OK",
        estimated_value=75000,
        difficulty_level="Medium",
        county="Oklahoma",
        state="Oklahoma"
    )

    print(f"Created deal: {deal_id}")

    # Get top deals
    top_deals = engine.get_top_deals(limit=5)
    print(f"\nTop {len(top_deals)} deals:")
    for deal in top_deals:
        print(f"  - {deal['title']} (Score: {deal['deal_score']:.1f})")

    # Get statistics
    stats = engine.get_statistics()
    print(f"\nStatistics: {json.dumps(stats, indent=2)}")
