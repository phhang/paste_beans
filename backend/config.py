"""Configuration management for the application."""

import os
import argparse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        # Parse CLI arguments first
        self._parse_args()

        # Azure OpenAI Configuration
        self.azure_openai_api_key: str = os.getenv('AZURE_OPENAI_API_KEY', '')
        self.azure_openai_endpoint: str = os.getenv('AZURE_OPENAI_ENDPOINT', '')
        self.azure_openai_deployment_name: str = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', '')
        self.azure_openai_api_version: str = os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')

        # Server Configuration
        self.host: str = os.getenv('HOST', '0.0.0.0')
        self.port: int = int(os.getenv('PORT', '8000'))

        # Debug Configuration
        # CLI argument takes precedence over environment variable
        self.debug: bool = self._get_debug_setting()

        # Log level (INFO or DEBUG)
        self.log_level: str = 'DEBUG' if self.debug else 'INFO'

        # Log format
        self.log_format: str = os.getenv(
            'LOG_FORMAT',
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def _parse_args(self):
        """Parse command line arguments."""
        parser = argparse.ArgumentParser(
            description='Paste Beans - Beancount entry generator (no-vector-db mode)',
            add_help=True
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Enable debug mode with verbose logging and stack traces'
        )
        parser.add_argument(
            '--verbose', '-v',
            action='store_true',
            help='Alias for --debug'
        )

        # Parse known args to avoid conflicts with uvicorn args
        self.args, _ = parser.parse_known_args()

    def _get_debug_setting(self) -> bool:
        """Get debug setting from CLI args or environment.

        CLI argument takes precedence over environment variable.

        Returns:
            True if debug mode is enabled, False otherwise
        """
        # CLI argument takes precedence
        if self.args.debug or self.args.verbose:
            return True

        # Fall back to environment variable
        env_debug = os.getenv('DEBUG', '').lower()
        return env_debug in ('1', 'true', 'yes', 'on')

    def validate_azure_config(self) -> bool:
        """Validate that Azure OpenAI configuration is present.

        Returns:
            True if valid, False otherwise
        """
        required_fields = [
            self.azure_openai_api_key,
            self.azure_openai_endpoint,
            self.azure_openai_deployment_name
        ]

        return all(field for field in required_fields)


# Global settings instance
settings = Settings()
