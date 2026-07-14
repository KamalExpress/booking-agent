import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/booking_saas")

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE scraper_accounts ADD COLUMN status VARCHAR DEFAULT 'Idle'"))
    except Exception as e:
        print("Status column might already exist:", e)
        
    try:
        conn.execute(text("ALTER TABLE scraper_accounts ADD COLUMN last_login TIMESTAMP"))
    except Exception as e:
        print("last_login column might already exist:", e)
        
    try:
        conn.execute(text("ALTER TABLE scraper_accounts ADD COLUMN consecutive_failures INTEGER DEFAULT 0"))
    except Exception as e:
        print("consecutive_failures column might already exist:", e)
        
    conn.commit()
    print("Migration complete!")
