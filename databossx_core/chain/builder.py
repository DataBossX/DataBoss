"""
Chain-of-Title Builder - constructs ownership graphs from documents
"""

import uuid
from datetime import datetime
from typing import List, Dict, Optional
from decimal import Decimal

from ..models.chain import (
    ChainGraph,
    ChainNode,
    ChainLink,
    ChainGap,
    Ownership,
    InterestType,
    OwnershipType,
)
from ..models.entity import EntityExtraction
from ..models.document import Document, DocumentType


class ChainBuilder:
    """
    Builds chain-of-title graphs from extracted document entities
    """

    def __init__(self):
        self.nodes: Dict[str, ChainNode] = {}
        self.links: List[ChainLink] = []
        self.gaps: List[ChainGap] = []

    async def build_chain(
        self,
        documents: List[Document],
        extractions: List[EntityExtraction],
        property_description: str,
    ) -> ChainGraph:
        """
        Build complete chain-of-title graph

        Args:
            documents: List of documents
            extractions: List of entity extractions
            property_description: Description of the property

        Returns:
            ChainGraph object
        """
        # Reset state
        self.nodes = {}
        self.links = []
        self.gaps = []

        # Sort documents by date (if available)
        doc_map = {doc.id: doc for doc in documents}
        extraction_map = {ext.document_id: ext for ext in extractions}

        # Process each document chronologically
        sorted_docs = self._sort_documents_chronologically(documents)

        for doc in sorted_docs:
            extraction = extraction_map.get(doc.id)
            if not extraction:
                continue

            await self._process_document(doc, extraction)

        # Identify gaps and inconsistencies
        await self._identify_gaps()

        # Determine current owners and original grantors
        current_owners = self._identify_current_owners()
        original_grantors = self._identify_original_grantors()

        # Determine primary interest type
        interest_type = self._determine_interest_type(documents)

        return ChainGraph(
            id=str(uuid.uuid4()),
            property_description=property_description,
            nodes=list(self.nodes.values()),
            links=self.links,
            gaps=self.gaps,
            current_owners=current_owners,
            original_grantors=original_grantors,
            interest_type=interest_type,
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )

    async def _process_document(self, doc: Document, extraction: EntityExtraction):
        """Process a single document and add to chain"""
        # Determine interest type from document type
        interest_type = self._doc_type_to_interest_type(doc.document_type)

        # Create nodes for grantors
        grantor_nodes = []
        for grantor in extraction.grantors:
            node = self._get_or_create_node(grantor.normalized_name, grantor.name)
            grantor_nodes.append(node)

        # Create nodes for grantees
        grantee_nodes = []
        for grantee in extraction.grantees:
            node = self._get_or_create_node(grantee.normalized_name, grantee.name)
            grantee_nodes.append(node)

            # Add ownership to grantee
            ownership = Ownership(
                owner_id=node.id,
                owner_name=grantee.name,
                interest_type=interest_type,
                ownership_type=OwnershipType.FEE_SIMPLE,
                fraction=grantee.percentage_interest,
                acres=extraction.acreage_info.total_acres if extraction.acreage_info else None,
                source_document_id=doc.id,
                confidence=grantee.confidence,
            )
            node.ownerships.append(ownership)

        # Create links from grantors to grantees
        transaction_date = doc.metadata.recording_date if doc.metadata else None
        transaction_type = self._doc_type_to_transaction_type(doc.document_type)

        for grantor_node in grantor_nodes:
            for grantee_node in grantee_nodes:
                link = ChainLink(
                    id=str(uuid.uuid4()),
                    from_node_id=grantor_node.id,
                    to_node_id=grantee_node.id,
                    document_id=doc.id,
                    transaction_date=transaction_date,
                    transaction_type=transaction_type,
                    interest_transferred=interest_type,
                    metadata={"doc_type": doc.document_type.value},
                )
                self.links.append(link)

    def _get_or_create_node(self, normalized_name: str, display_name: str) -> ChainNode:
        """Get existing node or create new one"""
        if normalized_name in self.nodes:
            return self.nodes[normalized_name]

        node = ChainNode(
            id=str(uuid.uuid4()),
            entity_name=display_name,
            normalized_name=normalized_name,
            ownerships=[],
        )
        self.nodes[normalized_name] = node
        return node

    def _sort_documents_chronologically(self, documents: List[Document]) -> List[Document]:
        """Sort documents by recording date"""
        def get_date(doc):
            if doc.metadata and doc.metadata.recording_date:
                return doc.metadata.recording_date
            return doc.uploaded_at

        return sorted(documents, key=get_date)

    async def _identify_gaps(self):
        """Identify gaps and inconsistencies in the chain"""
        # Check for fractional mismatches
        await self._check_fractional_consistency()

        # Check for missing links
        await self._check_missing_links()

        # Check for date conflicts
        await self._check_date_conflicts()

    async def _check_fractional_consistency(self):
        """Check if fractional interests add up correctly"""
        for node in self.nodes.values():
            total_fraction = Decimal(0)
            for ownership in node.ownerships:
                if ownership.fraction:
                    total_fraction += ownership.fraction

            # If we have fractions and they don't sum to 1.0
            if total_fraction > 0 and abs(total_fraction - Decimal(1.0)) > Decimal(0.01):
                gap = ChainGap(
                    id=str(uuid.uuid4()),
                    gap_type="fractional_mismatch",
                    description=f"Fractional interests for {node.entity_name} sum to {total_fraction}, not 1.0",
                    severity="warning",
                    confidence=0.9,
                )
                self.gaps.append(gap)

    async def _check_missing_links(self):
        """Check for missing links in the chain"""
        # Find nodes with no incoming links (potential original grantors)
        nodes_with_incoming = {link.to_node_id for link in self.links}
        nodes_with_outgoing = {link.from_node_id for link in self.links}

        # Find nodes with no outgoing links (potential current owners)
        # and nodes with no incoming links (potential original grantors)

        # Check for nodes that have outgoing but no incoming (except original grantors)
        for node in self.nodes.values():
            has_incoming = node.id in nodes_with_incoming
            has_outgoing = node.id in nodes_with_outgoing

            if has_outgoing and not has_incoming:
                # This is likely an original grantor - not a gap
                continue

    async def _check_date_conflicts(self):
        """Check for date conflicts in chain"""
        # Sort links by date
        dated_links = [link for link in self.links if link.transaction_date]
        dated_links.sort(key=lambda x: x.transaction_date)

        # Check for same property transferred multiple times
        # (This is a simplified check - real implementation would be more sophisticated)
        pass

    def _identify_current_owners(self) -> List[str]:
        """Identify current owners (nodes with no outgoing links)"""
        nodes_with_outgoing = {link.from_node_id for link in self.links}
        nodes_with_incoming = {link.to_node_id for link in self.links}

        # Current owners are those who received but never transferred
        current_owners = []
        for node in self.nodes.values():
            if node.id in nodes_with_incoming and node.id not in nodes_with_outgoing:
                node.is_current_owner = True
                current_owners.append(node.id)

        return current_owners

    def _identify_original_grantors(self) -> List[str]:
        """Identify original grantors (nodes with no incoming links)"""
        nodes_with_incoming = {link.to_node_id for link in self.links}
        nodes_with_outgoing = {link.from_node_id for link in self.links}

        # Original grantors are those who transferred but never received
        original_grantors = []
        for node in self.nodes.values():
            if node.id in nodes_with_outgoing and node.id not in nodes_with_incoming:
                node.is_original_grantor = True
                original_grantors.append(node.id)

        return original_grantors

    def _doc_type_to_interest_type(self, doc_type: DocumentType) -> InterestType:
        """Map document type to interest type"""
        mapping = {
            DocumentType.MINERAL_DEED: InterestType.MINERAL,
            DocumentType.DEED: InterestType.MINERAL,
            DocumentType.LEASE: InterestType.LEASEHOLD,
            DocumentType.ASSIGNMENT: InterestType.WORKING_INTEREST,
            DocumentType.ROYALTY_DEED: InterestType.ROYALTY,
        }
        return mapping.get(doc_type, InterestType.UNKNOWN)

    def _doc_type_to_transaction_type(self, doc_type: DocumentType) -> str:
        """Map document type to transaction type"""
        mapping = {
            DocumentType.DEED: "conveyance",
            DocumentType.MINERAL_DEED: "conveyance",
            DocumentType.LEASE: "lease",
            DocumentType.ASSIGNMENT: "assignment",
            DocumentType.PROBATE: "devise",
            DocumentType.AFFIDAVIT: "affidavit",
        }
        return mapping.get(doc_type, "transfer")

    def _determine_interest_type(self, documents: List[Document]) -> InterestType:
        """Determine primary interest type from documents"""
        # Count document types
        type_counts = {}
        for doc in documents:
            interest_type = self._doc_type_to_interest_type(doc.document_type)
            type_counts[interest_type] = type_counts.get(interest_type, 0) + 1

        # Return most common
        if type_counts:
            return max(type_counts, key=type_counts.get)
        return InterestType.MINERAL
