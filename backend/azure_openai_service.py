"""Azure OpenAI service for processing screenshots and generating Beancount entries."""

import base64
import json
import os
from typing import Dict, List, Optional
from openai import AzureOpenAI
from PIL import Image
import io

from logger import setup_logging, log_exception
from config import settings

logger = setup_logging(__name__)


class AzureOpenAIService:
    """Handles Azure OpenAI API calls for vision and text generation."""

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        deployment_name: str,
        api_version: str = "2024-02-15-preview"
    ):
        """Initialize Azure OpenAI client.

        Args:
            api_key: Azure OpenAI API key
            endpoint: Azure OpenAI endpoint URL
            deployment_name: Deployment name (e.g., gpt-4-vision)
            api_version: API version
        """
        logger.debug("Initializing Azure OpenAI service")
        logger.debug(f"  Endpoint: {endpoint}")
        logger.debug(f"  Deployment: {deployment_name}")

        self.client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint
        )
        self.deployment_name = deployment_name

    def encode_image(self, image_path: str) -> str:
        """Encode image to base64 string.

        Args:
            image_path: Path to image file

        Returns:
            Base64 encoded image string
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def encode_image_bytes(self, image_bytes: bytes) -> str:
        """Encode image bytes to base64 string.

        Args:
            image_bytes: Image bytes

        Returns:
            Base64 encoded image string
        """
        return base64.b64encode(image_bytes).decode('utf-8')

    def extract_transaction_from_screenshot(
        self,
        image_bytes: bytes
    ) -> List[Dict]:
        """Extract transaction information from a bank statement screenshot.

        Args:
            image_bytes: Screenshot image as bytes

        Returns:
            List of dictionaries with extracted transaction data
        """
        logger.debug(f"Encoding image ({len(image_bytes)} bytes)")
        # Encode image
        base64_image = self.encode_image_bytes(image_bytes)

        logger.debug("Calling Azure OpenAI vision API for extraction")
        # Prepare prompt for extraction
        extraction_prompt = """Analyze this bank statement screenshot and extract ALL transaction information visible in the image.

Please extract the following fields for EACH transaction:
1. Date (in YYYY-MM-DD format)
2. Merchant/Payee name
3. Amount (as a positive number with currency)
4. Any additional description or notes

Return the information as a JSON array where each element represents one transaction entry.

Example format:
[
  {
    "date": "YYYY-MM-DD",
    "merchant": "merchant name",
    "amount": "amount currency",
    "description": "optional description"
  },
  {
    "date": "YYYY-MM-DD",
    "merchant": "another merchant",
    "amount": "amount currency",
    "description": "optional description"
  }
]

If any field is not clearly visible, use "UNKNOWN" for that field.
Return ONLY the JSON array, no additional text."""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": extraction_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500
            )

            # Parse response
            content = response.choices[0].message.content

            if settings.debug:
                logger.debug(f"LLM extraction response:\n{content}")

            parsed_data = self._parse_extraction_response(content)
            logger.debug(f"Parsed {len(parsed_data)} transaction(s)")

            return parsed_data

        except Exception as e:
            log_exception(logger, e, "Error extracting transaction data")
            raise Exception(f"Error extracting transaction data: {str(e)}")

    def _parse_extraction_response(self, response: str) -> List[Dict]:
        """Parse the extraction response from the LLM.

        Args:
            response: LLM response text (expected to be JSON array)

        Returns:
            List of dictionaries with parsed fields
        """
        try:
            # Clean up response - remove markdown code blocks if present
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            elif cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]

            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]

            cleaned_response = cleaned_response.strip()

            # Parse JSON
            parsed_data = json.loads(cleaned_response)

            # Ensure it's a list
            if isinstance(parsed_data, dict):
                parsed_data = [parsed_data]

            # Validate and normalize each entry
            normalized_data = []
            for entry in parsed_data:
                normalized_entry = {
                    'date': entry.get('date', 'UNKNOWN'),
                    'merchant': entry.get('merchant', 'UNKNOWN'),
                    'amount': entry.get('amount', 'UNKNOWN'),
                    'description': entry.get('description', '')
                }
                normalized_data.append(normalized_entry)

            return normalized_data

        except json.JSONDecodeError as e:
            # Fallback: return a single entry with error information
            return [{
                'date': 'UNKNOWN',
                'merchant': 'UNKNOWN',
                'amount': 'UNKNOWN',
                'description': f'Error parsing response: {str(e)}'
            }]

    def generate_beancount_with_context(
        self,
        transaction_data: Dict,
        rag_prompt: str
    ) -> str:
        """Generate a Beancount entry using RAG context.

        Args:
            transaction_data: Extracted transaction data
            rag_prompt: RAG-enhanced prompt with historical context

        Returns:
            Generated Beancount entry
        """
        logger.debug("Calling Azure OpenAI for beancount generation")

        if settings.debug:
            logger.debug(f"Transaction data: {transaction_data}")
            logger.debug(f"Prompt length: {len(rag_prompt)} chars")

        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a Beancount accounting expert. "
                            "Generate properly formatted Beancount entries following the user's "
                            "historical patterns and conventions. "
                            "Always use the exact payee names and categories from the provided examples."
                        )
                    },
                    {
                        "role": "user",
                        "content": rag_prompt
                    }
                ],
                max_tokens=500,
                temperature=0.3  # Lower temperature for more consistent output
            )

            beancount_entry = response.choices[0].message.content.strip()

            if settings.debug:
                logger.debug(f"LLM generation response:\n{beancount_entry}")

            # Clean up the response (remove markdown code blocks if present)
            if beancount_entry.startswith('```'):
                lines = beancount_entry.split('\n')
                # Remove first and last lines if they're code block markers
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                beancount_entry = '\n'.join(lines).strip()

            return beancount_entry

        except Exception as e:
            log_exception(logger, e, "Error generating Beancount entry")
            raise Exception(f"Error generating Beancount entry: {str(e)}")

    def generate_beancount_from_screenshot(
        self,
        image_bytes: bytes,
        account_name: str,
        rag_prompt: Optional[str] = None
    ) -> Dict:
        """Complete workflow: extract transaction and generate Beancount entry.

        Args:
            image_bytes: Screenshot image as bytes
            account_name: Account name to use
            rag_prompt: Optional RAG-enhanced prompt

        Returns:
            Dictionary with extracted data and generated Beancount entry
        """
        # Step 1: Extract transaction data
        transaction_data = self.extract_transaction_from_screenshot(image_bytes)

        # Step 2: Generate Beancount entry
        if rag_prompt:
            beancount_entry = self.generate_beancount_with_context(
                transaction_data,
                rag_prompt
            )
        else:
            # Fallback: generate without RAG context
            simple_prompt = f"""Generate a Beancount entry for this transaction:

Date: {transaction_data['date']}
Merchant: {transaction_data['merchant']}
Amount: {transaction_data['amount']}
Account: {account_name}

Use proper Beancount syntax."""

            beancount_entry = self.generate_beancount_with_context(
                transaction_data,
                simple_prompt
            )

        return {
            'extracted_data': transaction_data,
            'beancount_entry': beancount_entry
        }
