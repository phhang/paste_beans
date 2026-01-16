"""Vector database operations using ChromaDB for storing and retrieving Beancount entries."""

import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional
import re
import os
from datetime import datetime

from logger import setup_logging, log_exception

logger = setup_logging(__name__)


class VectorDatabase:
    """Manages ChromaDB operations for Beancount entries."""

    def __init__(self, persist_directory: str = "./data/chroma_db"):
        """Initialize ChromaDB client with persistent storage.

        Args:
            persist_directory: Directory to persist ChromaDB data
        """
        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)

        logger.debug(f"Initializing ChromaDB at {persist_directory}")

        self.client = chromadb.Client(Settings(
            persist_directory=persist_directory,
            is_persistent=True
        ))

        # Get or create collection for beancount entries
        self.collection = self.client.get_or_create_collection(
            name="beancount_entries",
            metadata={"description": "Beancount transaction entries"}
        )

        logger.debug(f"ChromaDB collection: {self.collection.name}")

    def parse_beancount_entry(self, entry: str) -> Optional[Dict]:
        """Parse a Beancount entry to extract structured information.

        Args:
            entry: Beancount entry string

        Returns:
            Dictionary with parsed fields or None if parsing fails
        """
        # Match pattern: YYYY-MM-DD * "Merchant" "Description"
        # Example: 2024-01-15 * "Amazon" "Office supplies"
        pattern = r'(\d{4}-\d{2}-\d{2})\s+[*!]\s+"([^"]+)"(?:\s+"([^"]*)")?'
        match = re.search(pattern, entry)

        if not match:
            return None

        date_str, payee, narration = match.groups()
        narration = narration or ""

        # Extract account and category from posting lines
        # Example: Expenses:Shopping:Electronics    45.00 USD
        account_pattern = r'(Expenses:[^\s]+|Assets:[^\s]+|Liabilities:[^\s]+|Income:[^\s]+|Equity:[^\s]+)'
        accounts = re.findall(account_pattern, entry)

        # Extract expense category (first Expenses: account)
        expense_category = None
        for account in accounts:
            if account.startswith('Expenses:'):
                expense_category = account
                break

        return {
            'date': date_str,
            'payee': payee,
            'narration': narration,
            'expense_category': expense_category,
            'accounts': accounts,
            'full_entry': entry
        }

    def add_entry(self, entry: str, entry_id: Optional[str] = None):
        """Add a Beancount entry to the vector database.

        Args:
            entry: Beancount entry string
            entry_id: Optional unique ID for the entry
        """
        parsed = self.parse_beancount_entry(entry)

        if not parsed:
            logger.warning(f"Could not parse entry: {entry[:50]}...")
            return

        # Generate ID if not provided
        if entry_id is None:
            entry_id = f"{parsed['date']}_{parsed['payee']}_{hash(entry) % 10000}"

        logger.debug(f"Adding entry: {entry_id} - {parsed['payee']}")

        # Create searchable document combining key fields
        document = f"{parsed['payee']} {parsed['narration']} {parsed['expense_category'] or ''}"

        # Store in ChromaDB
        self.collection.add(
            documents=[document],
            metadatas=[{
                'date': parsed['date'],
                'payee': parsed['payee'],
                'narration': parsed['narration'],
                'expense_category': parsed['expense_category'] or '',
                'full_entry': parsed['full_entry']
            }],
            ids=[entry_id]
        )

    def search_similar(self, query: str, n_results: int = 5) -> List[Dict]:
        """Search for similar entries based on merchant name or description.

        Args:
            query: Search query (usually merchant name)
            n_results: Number of results to return

        Returns:
            List of similar entries with metadata
        """
        logger.debug(f"Searching for similar entries: '{query}' (n={n_results})")

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )

        similar_entries = []

        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                similar_entries.append({
                    'id': results['ids'][0][i],
                    'payee': results['metadatas'][0][i].get('payee', ''),
                    'expense_category': results['metadatas'][0][i].get('expense_category', ''),
                    'narration': results['metadatas'][0][i].get('narration', ''),
                    'full_entry': results['metadatas'][0][i].get('full_entry', ''),
                    'distance': results['distances'][0][i] if 'distances' in results else 0
                })

        logger.debug(f"Found {len(similar_entries)} similar entries")
        return similar_entries

    def ingest_bean_file(self, file_path: str) -> int:
        """Ingest a .bean file and add all entries to the vector database.

        Args:
            file_path: Path to .bean file

        Returns:
            Number of entries added
        """
        logger.info(f"Ingesting bean file: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Split by transaction entries (lines starting with date pattern)
        # Match: YYYY-MM-DD * or YYYY-MM-DD !
        entries = re.findall(
            r'(\d{4}-\d{2}-\d{2}\s+[*!][^\n]+(?:\n(?!\d{4}-\d{2}-\d{2})[^\n]+)*)',
            content,
            re.MULTILINE
        )

        count = 0
        for entry in entries:
            entry = entry.strip()
            if entry:
                self.add_entry(entry)
                count += 1

        logger.info(f"Ingested {count} entries from {os.path.basename(file_path)}")
        return count

    def ingest_directory(self, directory: str) -> Dict[str, int]:
        """Ingest all .bean files from a directory.

        Args:
            directory: Path to directory containing .bean files

        Returns:
            Dictionary mapping filename to number of entries added
        """
        logger.info(f"Ingesting directory: {directory}")

        results = {}

        if not os.path.exists(directory):
            return results

        for filename in os.listdir(directory):
            if filename.endswith('.bean'):
                file_path = os.path.join(directory, filename)
                try:
                    count = self.ingest_bean_file(file_path)
                    results[filename] = count
                except Exception as e:
                    log_exception(logger, e, f"Error ingesting {filename}")
                    results[filename] = 0

        return results

    def get_collection_stats(self) -> Dict:
        """Get statistics about the vector database collection.

        Returns:
            Dictionary with collection statistics
        """
        count = self.collection.count()

        return {
            'total_entries': count,
            'collection_name': self.collection.name
        }
