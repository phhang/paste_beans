# Vector Database Management Guide

This guide explains how to use the `manage_vectordb.py` script to manage the ChromaDB vector database used by Paste Beans.

## Quick Start

All commands should be run from the `backend` directory with the virtual environment activated:

```bash
cd backend
source ../venv/bin/activate
python manage_vectordb.py [options]
```

## Commands

### 1. Load .bean Files

Load Beancount files into the vector database for RAG context.

**Load from default directory** (`data/bean_files/`):
```bash
python manage_vectordb.py --load
```

**Load a specific file**:
```bash
python manage_vectordb.py --load /path/to/transactions.bean
```

**Load from a specific directory**:
```bash
python manage_vectordb.py --load /path/to/bean_directory/
```

Example output:
```
============================================================
Loading Bean Files
============================================================
Using default directory: /home/user/paste_beans/data/bean_files
Found 1 .bean files
Loading files...

Results:
  ✓ example.bean: 10 entries

✓ Successfully loaded 10 total entries from 1/1 files

Total entries in database: 10
============================================================
```

### 2. Show Statistics

Display information about the current vector database status.

**Basic statistics**:
```bash
python manage_vectordb.py --stats
```

**Detailed statistics with sample entries**:
```bash
python manage_vectordb.py --stats --verbose
```

Example output:
```
============================================================
Vector Database Statistics
============================================================
Collection Name: beancount_entries
Total Entries:   10
Persist Dir:     ./data/chroma_db
Database Size:   1.8 MB

Sample Entries:

  1. Payee: Netflix
     Category: Expenses:Entertainment:Streaming
     Narration: Monthly subscription

  2. Payee: Amazon
     Category: Expenses:Shopping:Electronics
     Narration: Tech accessories
============================================================
```

### 3. Cleanup Database

Delete all data from the vector database. This is useful when you want to start fresh or reset the database.

**Cleanup with confirmation prompt**:
```bash
python manage_vectordb.py --cleanup
```

**Cleanup without confirmation** (useful for scripts):
```bash
python manage_vectordb.py --cleanup --yes
```

Example output:
```
============================================================
Cleanup Vector Database
============================================================
⚠️  WARNING: This will delete ALL data from the vector database!
   Current entries: 10
   Location: ./data/chroma_db

Are you sure you want to continue? (yes/no): yes

Deleting vector database...
✓ Removed directory: ./data/chroma_db
✓ Vector database cleaned up successfully

Note: The database will be recreated on next server start or load operation
============================================================
```

## Common Workflows

### Reset and reload database
Clean up the existing database and load fresh data:
```bash
python manage_vectordb.py --cleanup --yes --load --stats
```

### Add new transactions to existing database
Load additional .bean files without removing existing data:
```bash
python manage_vectordb.py --load /path/to/new_transactions.bean --stats
```

### Check database status
View current statistics and sample entries:
```bash
python manage_vectordb.py --stats --verbose
```

### Migrate bean files
Move your .bean files to the default location and load them:
```bash
cp ~/accounting/*.bean ../data/bean_files/
python manage_vectordb.py --load
```

## Additional Options

### Debug mode
Enable verbose logging for troubleshooting:
```bash
python manage_vectordb.py --debug --load
```

### Combine multiple operations
You can combine multiple operations in a single command:
```bash
# Cleanup, load, and show stats
python manage_vectordb.py --cleanup --yes --load --stats

# Load and show verbose stats
python manage_vectordb.py --load --stats --verbose
```

## Troubleshooting

### "Path does not exist" error
Make sure your .bean files are in the correct location:
```bash
ls ../data/bean_files/
```

If the directory doesn't exist:
```bash
mkdir -p ../data/bean_files/
cp ~/your/bean/files/*.bean ../data/bean_files/
```

### "No .bean files found" warning
The directory exists but contains no .bean files. Add some files and try again:
```bash
cp ~/accounting/*.bean ../data/bean_files/
```

### ChromaDB telemetry errors
You may see warnings like:
```
Failed to send telemetry event ClientStartEvent: ...
```
These are harmless ChromaDB telemetry warnings and can be ignored.

### Database size concerns
Check the database size:
```bash
python manage_vectordb.py --stats
```

If the database becomes too large, consider:
1. Removing duplicate entries from your .bean files
2. Cleaning up and reloading only recent transactions
3. Using a subset of your historical data

## Integration with Paste Beans

The vector database is automatically loaded when the Paste Beans server starts (via `main.py`). However, you can use this management script to:

1. **Pre-load data** before starting the server
2. **Update the database** while the server is running (requires server restart to use new data)
3. **Debug RAG issues** by inspecting what's in the database
4. **Reset the database** if you encounter corruption or want to start fresh

## File Locations

- **Bean files directory**: `../data/bean_files/`
- **Vector database**: `../data/chroma_db/`
- **Configuration**: `../.env` (CHROMA_PERSIST_DIRECTORY setting)

## Tips

1. **Regular updates**: When you add new transactions to your .bean files, reload them into the database for better RAG suggestions.

2. **Quality over quantity**: It's better to have well-formatted, consistent .bean files than a large number of poorly formatted ones.

3. **Test your data**: Use `--stats --verbose` to see sample entries and verify they're being parsed correctly.

4. **Backup important data**: Before running `--cleanup`, make sure you have backups of your .bean files. The cleanup only deletes the vector database, not your source files.

5. **Server restart**: After modifying the database, restart the Paste Beans server to ensure it uses the updated data.
