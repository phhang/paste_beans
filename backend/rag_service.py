"""RAG (Retrieval-Augmented Generation) service for Beancount entry consistency."""

from typing import Dict, List, Optional
from vector_db import VectorDatabase
from logger import setup_logging
from config import settings

logger = setup_logging(__name__)


class RAGService:
    """Handles RAG operations for maintaining consistency in Beancount entries."""

    def __init__(self, vector_db: VectorDatabase):
        """Initialize RAG service with vector database.

        Args:
            vector_db: VectorDatabase instance
        """
        logger.debug("RAG service initialized")
        self.vector_db = vector_db

    def get_merchant_context(self, merchant_name: str, n_results: int = 3) -> Dict:
        """Get context about a merchant from historical entries.

        Args:
            merchant_name: Name of the merchant from the screenshot
            n_results: Number of similar entries to retrieve

        Returns:
            Dictionary with merchant context and suggestions
        """
        logger.debug(f"Getting merchant context: '{merchant_name}'")

        # Search for similar entries
        similar_entries = self.vector_db.search_similar(merchant_name, n_results)

        if not similar_entries:
            logger.debug(f"No history found for merchant: {merchant_name}")
            return {
                'has_history': False,
                'suggested_payee': merchant_name,
                'suggested_category': None,
                'examples': []
            }

        # Analyze similar entries to determine patterns
        payees = {}
        categories = {}

        for entry in similar_entries:
            payee = entry.get('payee', '')
            category = entry.get('expense_category', '')

            if payee:
                payees[payee] = payees.get(payee, 0) + 1

            if category:
                categories[category] = categories.get(category, 0) + 1

        # Get most common payee and category
        suggested_payee = max(payees.items(), key=lambda x: x[1])[0] if payees else merchant_name
        suggested_category = max(categories.items(), key=lambda x: x[1])[0] if categories else None

        # Prepare example entries
        examples = [
            {
                'payee': entry.get('payee', ''),
                'category': entry.get('expense_category', ''),
                'narration': entry.get('narration', ''),
                'full_entry': entry.get('full_entry', '')
            }
            for entry in similar_entries[:3]
        ]

        logger.debug(f"Found {len(similar_entries)} historical entries")
        logger.debug(f"Suggested payee: {suggested_payee}")
        logger.debug(f"Suggested category: {suggested_category}")

        return {
            'has_history': True,
            'suggested_payee': suggested_payee,
            'suggested_category': suggested_category,
            'payee_variations': list(payees.keys()),
            'category_usage': dict(categories),
            'examples': examples
        }

    def build_rag_prompt(
        self,
        merchant_name: str,
        date: Optional[str] = None,
        amount: Optional[str] = None,
        account_name: str = "Assets:Bank:Checking"
    ) -> str:
        """Build a prompt with RAG context for the LLM.

        Args:
            merchant_name: Merchant name from screenshot
            date: Transaction date
            amount: Transaction amount
            account_name: Account name to use in the entry

        Returns:
            Enhanced prompt with historical context
        """
        logger.debug(f"Building RAG prompt for: {merchant_name}")

        context = self.get_merchant_context(merchant_name)

        prompt_parts = [
            "Generate a Beancount entry based on the following transaction information:",
            ""
        ]

        if date:
            prompt_parts.append(f"Date: {date}")
        if merchant_name:
            prompt_parts.append(f"Merchant: {merchant_name}")
        if amount:
            prompt_parts.append(f"Amount: {amount}")
        if account_name:
            prompt_parts.append(f"Source Account: {account_name}")

        prompt_parts.append("")

        # Add RAG context if we have historical data
        if context['has_history']:
            prompt_parts.append("IMPORTANT - Historical Context:")
            prompt_parts.append(f"Based on your previous entries, this merchant is typically recorded as:")
            prompt_parts.append(f"  - Payee: \"{context['suggested_payee']}\"")

            if context['suggested_category']:
                prompt_parts.append(f"  - Category: {context['suggested_category']}")

            if context.get('payee_variations'):
                variations = ', '.join(f'"{v}"' for v in context['payee_variations'])
                prompt_parts.append(f"  - Previous variations: {variations}")

            prompt_parts.append("")
            prompt_parts.append("Example entries from your history:")

            for i, example in enumerate(context['examples'], 1):
                prompt_parts.append(f"\nExample {i}:")
                prompt_parts.append(example['full_entry'])

            prompt_parts.append("")
            prompt_parts.append(
                f"Please use \"{context['suggested_payee']}\" as the payee name "
                "and follow the same category and formatting patterns shown above."
            )
        else:
            prompt_parts.append(
                "Note: No historical entries found for this merchant. "
                "Please use standard Beancount formatting."
            )

        prompt_parts.append("")
        prompt_parts.append("Requirements:")
        prompt_parts.append("1. Use the exact payee name from historical context if available")
        prompt_parts.append("2. Use the same expense category as historical entries")
        prompt_parts.append("3. Follow proper Beancount syntax")
        prompt_parts.append("4. Include appropriate narration")
        prompt_parts.append(f"5. Debit from {account_name}")
        prompt_parts.append("")
        prompt_parts.append("Generate ONLY the Beancount entry, no explanations.")

        prompt = "\n".join(prompt_parts)

        if settings.debug:
            logger.debug(f"RAG prompt built ({len(prompt)} chars)")

        return prompt

    def extract_standardized_info(
        self,
        extracted_data: Dict
    ) -> Dict:
        """Standardize extracted information using RAG context.

        Args:
            extracted_data: Raw data extracted from screenshot (date, amount, merchant)

        Returns:
            Standardized information with consistent merchant names and categories
        """
        merchant = extracted_data.get('merchant', '')

        if not merchant:
            return extracted_data

        context = self.get_merchant_context(merchant)

        # Return standardized version
        standardized = extracted_data.copy()

        if context['has_history']:
            standardized['merchant_standardized'] = context['suggested_payee']
            standardized['suggested_category'] = context['suggested_category']
            standardized['has_history'] = True
        else:
            standardized['merchant_standardized'] = merchant
            standardized['suggested_category'] = None
            standardized['has_history'] = False

        return standardized

    def get_category_suggestions(self, merchant_name: str) -> List[str]:
        """Get expense category suggestions for a merchant.

        Args:
            merchant_name: Name of the merchant

        Returns:
            List of suggested categories ordered by frequency
        """
        context = self.get_merchant_context(merchant_name, n_results=10)

        if not context['has_history']:
            return []

        # Sort categories by usage count
        category_usage = context.get('category_usage', {})
        sorted_categories = sorted(
            category_usage.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return [category for category, _ in sorted_categories]
