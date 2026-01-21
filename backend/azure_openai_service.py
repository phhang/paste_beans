"""Azure OpenAI service for processing screenshots and generating Beancount entries."""

import base64
import json
from typing import Dict, List
from openai import AzureOpenAI

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
        base64_image = self.encode_image_bytes(image_bytes)

        logger.debug("Calling Azure OpenAI vision API for extraction")
        extraction_prompt = """Analyze this bank statement screenshot and extract ALL transaction information visible in the image.

Please extract the following fields for EACH transaction:
1. Date (in YYYY-MM-DD format)
2. Merchant/Payee name, Use short payee name with first letter upper case. For exmaple: "HMART - REDMOND" would be just "Hmart".
3. Amount (as a positive number with currency), use USD as default currency. 
4. Any additional description or notes. For merchant name that is too long, put the rest of the information into description.

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
                max_tokens=4096
            )

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
            return [{
                'date': 'UNKNOWN',
                'merchant': 'UNKNOWN',
                'amount': 'UNKNOWN',
                'description': f'Error parsing response: {str(e)}'
            }]

    def generate_beancount_entry(
        self,
        transaction_data: Dict,
        account_name: str
    ) -> str:
        """Generate a Beancount entry from transaction data.

        Args:
            transaction_data: Extracted transaction data (date, merchant, amount, description)
            account_name: The account name to use (e.g., "Assets:Bank:Checking")

        Returns:
            Generated Beancount entry
        """
        logger.debug("Calling Azure OpenAI for beancount generation")

        if settings.debug:
            logger.debug(f"Transaction data: {transaction_data}")
            logger.debug(f"Account name: {account_name}")

        prompt = f"""Generate a Beancount entry for this transaction:

Date: {transaction_data.get('date', 'UNKNOWN')}
Merchant: {transaction_data.get('merchant', 'UNKNOWN')}
Amount: {transaction_data.get('amount', 'UNKNOWN')}
Description: {transaction_data.get('description', '')}
Account: {account_name}

Generate a properly formatted Beancount entry following these rules:
1. Use the date in YYYY-MM-DD format
2. Use "*" for cleared transactions
3. Put the merchant/payee in quotes as the first quoted string
4. Choose an appropriate expense category based on the merchant name (e.g., Expenses:Food:Restaurants, Expenses:Shopping:Groceries, Expenses:Transport, etc.)
5. Format amounts with proper spacing and currency

Example format:
2024-01-15 * "Amazon" "Online purchase"
  Expenses:Shopping:Online    25.99 USD
  Assets:Bank:Checking       -25.99 USD

Return ONLY the Beancount entry, no additional text or explanation."""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a Beancount accounting expert. "
                            "Generate properly formatted Beancount entries. "
                            "Be concise and return only the entry itself."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=300,
                temperature=0.3
            )

            beancount_entry = response.choices[0].message.content.strip()

            if settings.debug:
                logger.debug(f"LLM generation response:\n{beancount_entry}")

            # Clean up the response (remove markdown code blocks if present)
            if beancount_entry.startswith('```'):
                lines = beancount_entry.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                beancount_entry = '\n'.join(lines).strip()

            return beancount_entry

        except Exception as e:
            log_exception(logger, e, "Error generating Beancount entry")
            raise Exception(f"Error generating Beancount entry: {str(e)}")
