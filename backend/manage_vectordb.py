#!/usr/bin/env python3
"""Management script for the vector database.

This script provides a CLI interface for managing the ChromaDB vector database
used to store Beancount entries for RAG operations.
"""

import argparse
import sys
import os
from typing import Optional
import shutil

from config import settings
from vector_db import VectorDatabase
from logger import setup_logging, log_exception

logger = setup_logging(__name__)


def load_bean_files(vector_db: VectorDatabase, path: Optional[str] = None):
    """Load .bean files into the vector database.

    Args:
        vector_db: VectorDatabase instance
        path: Optional specific file or directory path. If None, uses default bean_files directory
    """
    print("\n" + "=" * 60)
    print("Loading Bean Files")
    print("=" * 60)

    if path is None:
        path = settings.bean_files_directory
        print(f"Using default directory: {path}")

    if not os.path.exists(path):
        print(f"❌ Error: Path does not exist: {path}")
        return False

    try:
        if os.path.isfile(path):
            # Load single file
            if not path.endswith('.bean'):
                print(f"❌ Error: File must have .bean extension: {path}")
                return False

            print(f"Loading file: {path}")
            count = vector_db.ingest_bean_file(path)
            print(f"✓ Successfully loaded {count} entries from {os.path.basename(path)}")

        elif os.path.isdir(path):
            # Load directory
            bean_files = [f for f in os.listdir(path) if f.endswith('.bean')]

            if not bean_files:
                print(f"⚠ No .bean files found in {path}")
                return False

            print(f"Found {len(bean_files)} .bean files")
            print("Loading files...")

            results = vector_db.ingest_directory(path)

            total_entries = sum(results.values())
            successful_files = len([c for c in results.values() if c > 0])

            print("\nResults:")
            for filename, count in sorted(results.items()):
                status = "✓" if count > 0 else "✗"
                print(f"  {status} {filename}: {count} entries")

            print(f"\n✓ Successfully loaded {total_entries} total entries from {successful_files}/{len(results)} files")

        # Show updated stats
        stats = vector_db.get_collection_stats()
        print(f"\nTotal entries in database: {stats['total_entries']}")
        print("=" * 60)
        return True

    except Exception as e:
        log_exception(logger, e, "Error loading bean files")
        print(f"❌ Error: {str(e)}")
        return False


def show_stats(vector_db: VectorDatabase, verbose: bool = False):
    """Show statistics about the vector database.

    Args:
        vector_db: VectorDatabase instance
        verbose: If True, show additional details
    """
    print("\n" + "=" * 60)
    print("Vector Database Statistics")
    print("=" * 60)

    try:
        stats = vector_db.get_collection_stats()

        print(f"Collection Name: {stats['collection_name']}")
        print(f"Total Entries:   {stats['total_entries']}")
        print(f"Persist Dir:     {vector_db.persist_directory}")

        # Check if persist directory exists and show size
        if os.path.exists(vector_db.persist_directory):
            size = get_directory_size(vector_db.persist_directory)
            print(f"Database Size:   {format_bytes(size)}")

        if verbose and stats['total_entries'] > 0:
            # Show sample entries
            print("\nSample Entries:")
            try:
                # Query for a few random entries
                sample_results = vector_db.search_similar("*", n_results=5)
                for i, entry in enumerate(sample_results[:5], 1):
                    payee = entry.get('payee', 'N/A')
                    category = entry.get('expense_category', 'N/A')
                    print(f"\n  {i}. Payee: {payee}")
                    print(f"     Category: {category}")
                    if entry.get('narration'):
                        print(f"     Narration: {entry['narration']}")
            except Exception as e:
                logger.debug(f"Could not fetch sample entries: {e}")

        print("=" * 60)
        return True

    except Exception as e:
        log_exception(logger, e, "Error getting stats")
        print(f"❌ Error: {str(e)}")
        return False


def cleanup_database(vector_db: VectorDatabase, confirm: bool = False):
    """Cleanup (delete) the vector database.

    Args:
        vector_db: VectorDatabase instance
        confirm: If True, skip confirmation prompt
    """
    print("\n" + "=" * 60)
    print("Cleanup Vector Database")
    print("=" * 60)

    stats = vector_db.get_collection_stats()

    print(f"⚠️  WARNING: This will delete ALL data from the vector database!")
    print(f"   Current entries: {stats['total_entries']}")
    print(f"   Location: {vector_db.persist_directory}")

    if not confirm:
        response = input("\nAre you sure you want to continue? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("❌ Cleanup cancelled")
            return False

    try:
        print("\nDeleting vector database...")

        # Delete the collection
        try:
            vector_db.client.delete_collection(vector_db.collection.name)
            logger.info(f"Deleted collection: {vector_db.collection.name}")
        except Exception as e:
            logger.debug(f"Error deleting collection: {e}")

        # Remove the persist directory
        if os.path.exists(vector_db.persist_directory):
            shutil.rmtree(vector_db.persist_directory)
            print(f"✓ Removed directory: {vector_db.persist_directory}")

        print("✓ Vector database cleaned up successfully")
        print("\nNote: The database will be recreated on next server start or load operation")
        print("=" * 60)
        return True

    except Exception as e:
        log_exception(logger, e, "Error cleaning up database")
        print(f"❌ Error: {str(e)}")
        return False


def get_directory_size(path: str) -> int:
    """Calculate total size of directory in bytes.

    Args:
        path: Directory path

    Returns:
        Size in bytes
    """
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.exists(filepath):
                total_size += os.path.getsize(filepath)
    return total_size


def format_bytes(bytes_count: int) -> str:
    """Format bytes into human-readable string.

    Args:
        bytes_count: Number of bytes

    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.1f} TB"


def main():
    """Main entry point for the management script."""
    parser = argparse.ArgumentParser(
        description='Manage the Paste Beans vector database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show database statistics
  python manage_vectordb.py --stats

  # Load all .bean files from default directory
  python manage_vectordb.py --load

  # Load a specific .bean file
  python manage_vectordb.py --load path/to/file.bean

  # Load from a specific directory
  python manage_vectordb.py --load path/to/directory

  # Show detailed statistics
  python manage_vectordb.py --stats --verbose

  # Cleanup database (with confirmation)
  python manage_vectordb.py --cleanup

  # Cleanup database (skip confirmation)
  python manage_vectordb.py --cleanup --yes
        """
    )

    parser.add_argument(
        '--load',
        nargs='?',
        const='',
        metavar='PATH',
        help='Load .bean files into database. Optionally specify a file or directory path. If not specified, uses default bean_files directory.'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show database statistics'
    )

    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Delete all data from the vector database'
    )

    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompts (use with --cleanup)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed information'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    # If debug flag is set, update logger level
    if args.debug:
        logger.setLevel('DEBUG')
        logger.debug("Debug mode enabled")

    # Show help if no arguments provided
    if not any([args.load is not None, args.stats, args.cleanup]):
        parser.print_help()
        return 0

    # Initialize vector database
    print("Initializing vector database...")
    try:
        vector_db = VectorDatabase(settings.chroma_persist_directory)
        print(f"✓ Connected to database at: {settings.chroma_persist_directory}")
    except Exception as e:
        log_exception(logger, e, "Failed to initialize vector database")
        print(f"❌ Error: Could not initialize vector database: {str(e)}")
        return 1

    success = True

    # Execute commands
    if args.load is not None:
        # If --load was provided without a path, use empty string which will trigger default directory
        path = args.load if args.load else None
        success = load_bean_files(vector_db, path) and success

    if args.stats:
        success = show_stats(vector_db, args.verbose) and success

    if args.cleanup:
        success = cleanup_database(vector_db, args.yes) and success

    return 0 if success else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        log_exception(logger, e, "Unexpected error")
        print(f"\n❌ Unexpected error: {str(e)}")
        sys.exit(1)
