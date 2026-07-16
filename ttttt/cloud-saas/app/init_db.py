import os
from sqlalchemy.orm import Session
from models import Base, engine, Tenant, User, RoleEnum, MonitorConfig, ScraperAccount, SystemSetting
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
            "ALTER TABLE scraper_accounts ADD COLUMN proxy_string VARCHAR",
            "ALTER TABLE assignments ADD COLUMN last_checked TIMESTAMP",
            # Sprint 5 schema changes
            "ALTER TABLE worker_nodes ADD COLUMN observed_ip VARCHAR",
            "ALTER TABLE worker_nodes ADD COLUMN public_ip VARCHAR",
            "ALTER TABLE worker_nodes ADD COLUMN local_ip VARCHAR",
            "ALTER TABLE worker_nodes ADD COLUMN os VARCHAR",
            "ALTER TABLE worker_nodes ADD COLUMN architecture VARCHAR",
            "ALTER TABLE worker_nodes ADD COLUMN chrome_version VARCHAR",
            "ALTER TABLE worker_nodes ADD COLUMN playwright_version VARCHAR",
            "ALTER TABLE worker_nodes ADD COLUMN python_version VARCHAR",
            "ALTER TABLE worker_nodes ADD COLUMN cpu_cores INTEGER",
            "ALTER TABLE worker_nodes ADD COLUMN ram VARCHAR",
            "ALTER TABLE worker_nodes ADD COLUMN max_concurrency INTEGER DEFAULT 1",
            "ALTER TABLE worker_nodes ADD COLUMN current_concurrency INTEGER DEFAULT 0",
            "ALTER TABLE worker_nodes ADD COLUMN scheduling_state VARCHAR DEFAULT 'Accepting Jobs'",
            "ALTER TABLE scraper_accounts ADD COLUMN proxy_mode VARCHAR DEFAULT 'LEGACY'",
            "ALTER TABLE assignments ADD COLUMN routing_policy_id INTEGER",
            "ALTER TABLE leases ADD COLUMN last_heartbeat TIMESTAMP",
            "ALTER TABLE leases ADD COLUMN status VARCHAR DEFAULT 'Pending'",
            # Sprint 7 schema changes
            "ALTER TABLE assignments ADD COLUMN required_labels JSONB DEFAULT '{}'::jsonb",
            "ALTER TABLE assignments DROP COLUMN IF EXISTS routing_policy_id",
            "ALTER TABLE users ADD COLUMN full_name VARCHAR"
        ]:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception as e:
                print(f"Migration error for '{stmt}': {e}")
                conn.rollback()

    # Pre-generate the SECRET_MASTER_KEY if missing
    from secrets_manager import secrets_manager
    
    with Session(engine) as db:
        # 1. Create Default Tenant if not exists
        default_tenant = db.query(Tenant).filter(Tenant.id == 1).first()
            
        if not default_tenant:
            default_tenant = Tenant(name="Default Tenant", is_active=True)
            db.add(default_tenant)
            db.commit()
            db.refresh(default_tenant)
            print(f"Created Default Tenant: {default_tenant.name} (ID: {default_tenant.id})")
        else:
            # Ensure it is NEVER suspended
            default_tenant.is_active = True
            
            # Reactivate ALL users under the default tenant to prevent lockouts
            for u in default_tenant.users:
                u.is_active = True
                
            db.commit()
            
        # 2. Create Super Admin User if not exists
        super_admin_email = os.getenv("SUPER_ADMIN_EMAIL", "superadmin@samwebdevs.dpdns.org")
        super_admin_password = os.getenv("SUPER_ADMIN_PASSWORD", "admin123")
        
        super_admin = db.query(User).filter(User.email == super_admin_email).first()
        if not super_admin:
            super_admin = User(
                tenant_id=default_tenant.id,
                email=super_admin_email,
                hashed_password=get_password_hash(super_admin_password),
                role=RoleEnum.SUPER_ADMIN,
                is_active=True
            )
            db.add(super_admin)
            db.commit()
            print(f"Created Super Admin: {super_admin.email} (Password: {super_admin_password})")
        else:
            # Ensure super admin is always active
            super_admin.is_active = True
            db.commit()
            
        # 2b. Seed requested user under default tenant
        devali_email = "devali@kamalexpress.com"
        devali = db.query(User).filter(User.email == devali_email).first()
        if not devali:
            devali = User(
                tenant_id=default_tenant.id,
                email=devali_email,
                hashed_password=get_password_hash("password123"), # Default password, they can reset it
                role=RoleEnum.TENANT_ADMIN,
                is_active=True
            )
            db.add(devali)
            db.commit()
            print(f"Seeded User: {devali_email}")
        else:
            devali.is_active = True
            db.commit()
            
        # 3. Create Default Global Monitor Config if not exists
        if not db.query(MonitorConfig).first():
            db.add(MonitorConfig(is_active=False))
            db.commit()
            print("Created default Monitor Config.")
            
        # 4. Create default system settings
        if not db.query(SystemSetting).filter(SystemSetting.key == "captcha.provider").first():
            db.add(SystemSetting(key="captcha.provider", value="capsolver", updated_by="system"))
            db.commit()

        print("Database initialization complete.")

        # 5. Create Default Scraper Accounts if not exists
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
