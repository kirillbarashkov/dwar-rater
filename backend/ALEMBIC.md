# Alembic — Database Migrations

## Quick commands

```bash
cd backend

# Generate a new migration from model changes
alembic revision --autogenerate -m "describe the change"

# Apply all pending migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1

# Roll back to a specific revision
alembic downgrade <revision_id>

# Show current revision
alembic current

# Show migration history
alembic history
```

## Rules

1. **Every schema change = one migration** with a descriptive name.
2. **All migrations must be reversible** — `downgrade` must work.
3. **For data migrations** (moving data between columns), use a separate migration:
   ```python
   def upgrade():
       # 1. Add new column
       op.add_column('table', sa.Column('new_col', sa.Integer(), nullable=True))
       # 2. Fill it from existing data
       conn = op.get_bind()
       conn.execute(sa.text("UPDATE table SET new_col = old_col"))
       # 3. Make it NOT NULL after filling
       op.alter_column('table', 'new_col', nullable=False)

   def downgrade():
       op.drop_column('table', 'new_col')
   ```
4. **Before running on production** — dump the database.
5. **Test on a copy of production data** before applying.

## Migrating the existing database

The baseline migration (`001_initial_baseline`) matches the current schema exactly.

To migrate an existing SQLite/PostgreSQL database:

```bash
# 1. Back up the database
cp backend/instance/dwar_rater.db backend/instance/dwar_rater.db.bak

# 2. Stamp the database as being at the baseline revision
#    (this tells Alembic "all tables already exist, don't create them")
alembic stamp 001_initial_baseline

# 3. Future migrations will apply on top of the baseline
alembic upgrade head
```

## Directory structure

```
backend/
  alembic.ini                    # Alembic configuration
  migrations/
    env.py                       # Environment setup (imports all models)
    script.py.mako               # Template for new migrations
    versions/
      001_initial_baseline.py    # Baseline: all current tables
      002_add_<feature>.py       # Future migrations
```
