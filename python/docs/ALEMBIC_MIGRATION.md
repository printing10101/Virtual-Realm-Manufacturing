# Alembic Database Migration Guide

This project uses [Alembic](https://alembic.sqlalchemy.org/) for database schema versioning and migration management.

## Overview

All database schema changes are tracked through Alembic migration scripts located in `python/alembic/versions/`. This replaces the previous approach of hardcoding DDL statements in application code.

## Configuration

### Database Connection

The database URL is configured in `python/alembic.ini`:

```ini
sqlalchemy.url = sqlite:///./data/process_rules.db
```

You can override this via environment variable:

```bash
# Windows PowerShell
$env:DB_URL="sqlite:///./data/custom.db"

# Linux/macOS
export DB_URL="postgresql+asyncpg://user:pass@localhost/dbname"
```

When `DB_URL` is set, it takes precedence over the value in `alembic.ini`.

### Default Database

If `DB_URL` is not set, the default database is `sqlite:///./data/process_rules.db` (relative to `python/`).

## Usage

All commands should be run from the `python/` directory:

```bash
cd python
```

### Check Current Version

```bash
python -m alembic current
```

Output example:
```
be7e8d82d196 (head)
```

### View Migration History

```bash
python -m alembic history --verbose
```

### Create a New Migration

1. **Modify your SQLAlchemy models** in `app/database/models.py` or `app/database/rule_models.py`.

2. **Generate the migration script**:
   ```bash
   python -m alembic revision --autogenerate -m "description_of_change"
   ```
   This compares your models against the current database and generates a migration script.

3. **Review the generated script** in `alembic/versions/`. Ensure it accurately reflects your intended changes. Pay special attention to:
   - Column type changes
   - Nullable changes
   - Index additions/removals
   - Foreign key changes

4. **Apply the migration**:
   ```bash
   python -m alembic upgrade head
   ```

### Upgrade/Downgrade

```bash
# Upgrade to the latest version
python -m alembic upgrade head

# Upgrade to a specific version
python -m alembic upgrade <revision_id>

# Downgrade by one version
python -m alembic downgrade -1

# Downgrade to a specific version
python -m alembic downgrade <revision_id>

# Downgrade to empty (remove all tables managed by Alembic)
python -m alembic downgrade base
```

### Auto-Migration on Startup

The application automatically runs `alembic upgrade head` on startup via `app/main.py`. This ensures the database schema is always up-to-date when the server starts. If migration fails, the application will log the error and refuse to start.

## Best Practices

1. **Always backup before migrating**: The `RuleDatabase` class provides a `backup_database()` method.
2. **Review auto-generated scripts**: Never blindly apply `--autogenerate` output.
3. **Test downgrades**: Always verify that downgrade scripts work correctly.
4. **One logical change per migration**: Keep migrations small and focused.
5. **Use descriptive names**: `python -m alembic revision --autogenerate -m "add_user_role_field"`

## Model Files

- `app/database/models.py` - Training tasks, RBAC (roles, permissions) models
- `app/database/rule_models.py` - Process rules and rule groups models

When adding new tables or modifying existing ones, update the appropriate model file and generate a new migration.

## Troubleshooting

### "Can't locate revision" error
This usually means the migration history has been modified. Use `alembic stamp head` to mark the current database state.

### SQLite ALTER TABLE limitations
SQLite has limited ALTER TABLE support. For complex changes (renaming columns, changing types), Alembic uses batch mode which recreates the table. Ensure `render_as_batch=True` is set in `alembic/env.py`.

### Migration fails on startup
Check the application logs for the specific error. Common causes:
- Missing database file (the directory must exist)
- Invalid DB_URL format
- Conflicting schema changes
