import os
from sqlalchemy.orm import Session
from models import Base, engine, Tenant, User, RoleEnum, MonitorConfig, ScraperAccount
from auth import get_password_hash
from sqlalchemy import text

def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    # Ensure new columns exist on older tables
    with engine.connect() as conn:
        for stmt in [
            "ALTER TABLE scraper_accounts ADD COLUMN status VARCHAR DEFAULT 'Idle'",
            "ALTER TABLE scraper_accounts ADD COLUMN last_login TIMESTAMP",
            "ALTER TABLE scraper_accounts ADD COLUMN preferred_worker_id VARCHAR",
            "ALTER TABLE scraper_accounts ADD COLUMN proxy_string VARCHAR"
        ]:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                conn.rollback()
    
    with Session(engine) as db:
        # 1. Create Default Tenant if not exists
        default_tenant = db.query(Tenant).filter(Tenant.name == "Kamal Express").first()
        if not default_tenant:
            default_tenant = Tenant(name="Kamal Express")
            db.add(default_tenant)
            db.commit()
            db.refresh(default_tenant)
            print(f"Created Default Tenant: {default_tenant.name} (ID: {default_tenant.id})")
            
        # 2. Create Super Admin User if not exists
        super_admin_email = os.getenv("SUPER_ADMIN_EMAIL", "superadmin@samwebdevs.dpdns.org")
        super_admin_password = os.getenv("SUPER_ADMIN_PASSWORD", "admin123")
        
        super_admin = db.query(User).filter(User.email == super_admin_email).first()
        if not super_admin:
            super_admin = User(
                tenant_id=default_tenant.id,
                email=super_admin_email,
                hashed_password=get_password_hash(super_admin_password),
                role=RoleEnum.SUPER_ADMIN
            )
            db.add(super_admin)
            db.commit()
            print(f"Created Super Admin: {super_admin.email} (Password: {super_admin_password})")
            
        # 3. Create Default Global Monitor Config if not exists
        config = db.query(MonitorConfig).first()
        if not config:
            config = MonitorConfig(is_active=False)
            db.add(config)
            db.commit()
            print("Created default Monitor Config.")

        # 4. Create Default Scraper Accounts if not exists
        if db.query(ScraperAccount).count() == 0:
            accounts = [
                ScraperAccount(username="mnoon2404@gmail.com", password="Shani@1122"),
                ScraperAccount(username="ammarashrafsialkot@gmail.com", password="Shani@1122")
            ]
            db.add_all(accounts)
            db.commit()
            print("Created default Scraper Accounts.")

if __name__ == "__main__":
    init_db()
