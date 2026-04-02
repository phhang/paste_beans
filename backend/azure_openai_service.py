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
2. Merchant/Payee name
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
                max_completion_tokens=4096
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

    def generate_beancount_entries(
        self,
        transactions: List[Dict],
        account_name: str
    ) -> List[str]:
        """Generate Beancount entries for all transactions in a single API call.

        Args:
            transactions: List of extracted transaction data (date, merchant, amount, description)
            account_name: The account name to use (e.g., "Assets:Bank:Checking")

        Returns:
            List of generated Beancount entries
        """
        logger.debug(f"Calling Azure OpenAI to generate {len(transactions)} beancount entries")

        if settings.debug:
            logger.debug(f"Transactions: {transactions}")
            logger.debug(f"Account name: {account_name}")

        # Build transaction list for prompt
        transactions_text = ""
        for idx, t in enumerate(transactions, 1):
            transactions_text += f"""
Transaction {idx}:
- Date: {t.get('date', 'UNKNOWN')}
- Merchant: {t.get('merchant', 'UNKNOWN')}
- Amount: {t.get('amount', 'UNKNOWN')}
- Description: {t.get('description', '')}
"""

        prompt = f"""Generate Beancount entries for the following {len(transactions)} transactions:
{transactions_text}
Account to use: {account_name}

Generate properly formatted Beancount entries following these rules:
1. Use the date in YYYY-MM-DD format
2. Use "*" for cleared transactions
3. Put the merchant/payee name in quotes as the first quoted string, with first letter upper case. Do not include additional information beyond the merchant name. For example: "HMART - REDMOND" would be just "Hmart".
4. Choose an appropriate expense category based on the merchant name
5. Format amounts with proper spacing and currency
6. Only generate description if there is additional information beyond merchant name. Do not add merchant phone numbers, locations, or other extraneous details in the description.

Example format for ONE entry:
2024-01-15 * "Safeway" "(optional) description"
  Expenses:Eat:Grocery
  {account_name}       -25.99 USD

Here are some common Beancount categories you can use:
** Income
Income:Paycheck ; Base salary
Income:Paycheck:Benefit
Income:Bonus
Income:RSU
Income:Match401k
Income:MatchHSA
Income:InterestIncome ; 利息
Income:Investment     ; 用于Wealthfront等auto investment
Income:RetailIncome ; 卖二手
Income:ReturnedPurchase
Income:CashBack ; 羊毛
Income:Family
;Income:Reimbursement

** Expenses
*** Transport 交通出行
Expenses:Transport:Auto:Gas
Expenses:Transport:Auto:Maint   ; 汽车保养维护等
Expenses:Transport:Auto:Parking ; 停车
Expenses:Transport:Taxi         ; 打车 Uber/Lyft
Expenses:Transport:Public       ; 公共交通
*** Utilities 水电网等
Expenses:Utilities:WaterSewer
Expenses:Utilities:GasElectric
Expenses:Utilities:Internet
Expenses:Utilities:Trash
*** Housing
Expenses:Housing:Furniture
Expenses:Housing:Tools
Expenses:Housing:Repair
Expenses:Housing:Comfort
Expenses:Housing:Consumable ; 耗材
*** Entertainment 文娱类
Expenses:Entertainment:Book
Expenses:Entertainment:Streaming  ; 电影 电视剧 流媒体订阅
Expenses:Entertainment:Toys
Expenses:Entertainment:Games
Expenses:Entertainment:Activity   ; 门票
Expenses:Entertainment:Guns
*** Appearance
Expenses:Appearance:Cloth
Expenses:Appearance:Hair
Expenses:Appearance:Skincare
Expenses:Appearance:Shoes
*** Fees
Expenses:FeesAndCharges:Financial ; 账户管理费
Expenses:FeesAndCharges:AnnualFee ; 信用卡年费
Expenses:FeesAndCharges:Subscription ; 订阅服务
Expenses:FeesAndCharges:Shipping  ; 运费
Expenses:FeesAndCharges:Insurance
Expenses:FeesAndCharges:Document  ; 签证等证件费用
*** Eat
Expenses:Eat:Grocery  ; 超市购物
Expenses:Eat:Meal     ; 出门吃正餐
Expenses:Eat:Fastfood ; 出门吃快餐
Expenses:Eat:Snack    ; 零食饮料
Expenses:Eat:Bakery   ; 面包
** Medical
Expenses:Medical:Medicine     ; 非处方药 维生素等
Expenses:Medical:Prescription ; 处方药
Expenses:Medical:Bill         ; 账单
** Gadget 数码产品
Expenses:Gadget:Accessory     ; 配件
Expenses:Gadget:PC            ; PC硬件
Expenses:Gadget:SmartHome
** Travel
Expenses:Travel:Transport
Expenses:Travel:Hotel
Expenses:Travel:Sightseeing   ; 门票 活动
Expenses:Travel:Shopping      ; 纪念品
** Tax
Expenses:Taxes:Federal
Expenses:Taxes:PropertyTax
Expenses:Taxes:SocialSecurity
Expenses:Taxes:Medicare
** 其他（以上均不适用时使用）
Expenses:GiftsAndDonations
Expenses:HealthAndFitness
Expenses:Education
Expenses:Services

Return ALL entries separated by a blank line. Return ONLY the Beancount entries, no additional text, numbering, or explanation."""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a Beancount accounting expert. "
                            "Generate properly formatted Beancount entries. "
                            "Be concise and return only the entries themselves."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_completion_tokens=4096,
                temperature=0.3
            )

            response_text = response.choices[0].message.content.strip()

            if settings.debug:
                logger.debug(f"LLM generation response:\n{response_text}")

            # Clean up the response (remove markdown code blocks if present)
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                response_text = '\n'.join(lines).strip()

            # Split into individual entries (entries are separated by blank lines)
            entries = self._split_beancount_entries(response_text)

            logger.debug(f"Parsed {len(entries)} beancount entries")
            return entries

        except Exception as e:
            log_exception(logger, e, "Error generating Beancount entries")
            raise Exception(f"Error generating Beancount entries: {str(e)}")

    def _split_beancount_entries(self, text: str) -> List[str]:
        """Split a text containing multiple Beancount entries into individual entries.

        Args:
            text: Text containing multiple Beancount entries separated by blank lines

        Returns:
            List of individual Beancount entries
        """
        entries = []
        current_entry_lines = []

        for line in text.split('\n'):
            # Check if this line starts a new entry (date pattern at start of line)
            if line and line[0].isdigit() and len(line) >= 10 and line[4] == '-' and line[7] == '-':
                # If we have a current entry, save it
                if current_entry_lines:
                    entries.append('\n'.join(current_entry_lines).strip())
                current_entry_lines = [line]
            else:
                current_entry_lines.append(line)

        # Don't forget the last entry
        if current_entry_lines:
            entries.append('\n'.join(current_entry_lines).strip())

        # Filter out empty entries
        return [e for e in entries if e.strip()]
