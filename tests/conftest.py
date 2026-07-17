"""Force a local SQLite DB for tests so importing app modules never needs Postgres."""
import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_sarbon.db"
