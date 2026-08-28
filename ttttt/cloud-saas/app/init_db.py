import os
from sqlalchemy.orm import Session
from models import Base, engine, Tenant, User, RoleEnum, MonitorConfig, PortalAccount, SystemSetting
from auth import get_password_hash
from sqlalchemy import text

def init_db():
    print("Database tables should already be created via entrypoint.")
    
    # Pre-generate the SECRET_MASTER_KEY if missing
    from secrets_manager import secrets_manager
    
    with Session(engine) as db:
        # Self-healing column additions for existing tables
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE slot_availability ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'AVAILABLE';"))
                conn.execute(text("ALTER TABLE slot_availability ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"))
                conn.execute(text("ALTER TABLE slot_availability ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE;"))
                conn.execute(text("ALTER TABLE slot_availability ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP;"))
                conn.execute(text("ALTER TABLE slot_availability ADD COLUMN IF NOT EXISTS archived_by_id INTEGER;"))
                conn.execute(text("ALTER TABLE portal_accounts ADD COLUMN IF NOT EXISTS account_name VARCHAR;"))
                conn.execute(text("ALTER TABLE portal_accounts ADD COLUMN IF NOT EXISTS phone_number VARCHAR;"))
                conn.execute(text("ALTER TABLE portal_accounts ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE;"))
                conn.execute(text("ALTER TABLE portal_accounts ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP;"))
                conn.execute(text("ALTER TABLE portal_accounts ADD COLUMN IF NOT EXISTS archived_by_id INTEGER;"))
                conn.execute(text("ALTER TABLE worker_nodes ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE;"))
                conn.execute(text("ALTER TABLE worker_nodes ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP;"))
                conn.execute(text("ALTER TABLE worker_nodes ADD COLUMN IF NOT EXISTS archived_by_id INTEGER;"))
                conn.execute(text("ALTER TABLE booking_tasks ADD COLUMN IF NOT EXISTS reference_number VARCHAR;"))
                conn.execute(text("ALTER TABLE booking_tasks ADD COLUMN IF NOT EXISTS confirmation_payload JSONB;"))
                conn.execute(text("ALTER TABLE booking_tasks ADD COLUMN IF NOT EXISTS confirmation_screenshot VARCHAR;"))
                conn.commit()
        except Exception as e:
            print(f"Self-healing column check warning: {e}")

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
        super_admin_email = os.getenv("SUPER_ADMIN_EMAIL", "amr.shah@gmail.com")
        super_admin_password = os.getenv("SUPER_ADMIN_PASSWORD", "Admin@123")
        
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
            # Ensure super admin is always active and sync password from env vars
            super_admin.is_active = True
            super_admin.hashed_password = get_password_hash(super_admin_password)
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
        if not db.query(SystemSetting).filter(SystemSetting.key == "testing.enable_mock_slots").first():
            db.add(SystemSetting(key="testing.enable_mock_slots", value="false", updated_by="system"))
            db.commit()
        if not db.query(SystemSetting).filter(SystemSetting.key == "otp.regex_pattern").first():
            db.add(SystemSetting(
                key="otp.regex_pattern",
                value=r"The OTP for your GVCW Appointment is:\s*(\d{4,8})|\b\d{5,6}\b",
                updated_by="system"
            ))
            db.commit()

        print("Database initialization complete.")

        # 5. Create Default Portal Accounts if not exists
        if db.query(PortalAccount).count() == 0:
            accounts = [
                PortalAccount(account_name="Jameel", username="mnoon2404@gmail.com", password="Shani@1122", supports_scraping=True, supports_booking=True, status="READY"),
                PortalAccount(account_name="Tayyab", username="ammarashrafsialkot@gmail.com", password="Shani@1122", supports_scraping=True, supports_booking=True, status="READY")
            ]
            db.add_all(accounts)
            db.commit()
            print("Created default Portal Accounts.")
        else:
            # Backfill default account names if missing
            acc1 = db.query(PortalAccount).filter(PortalAccount.username == "mnoon2404@gmail.com").first()
            if acc1 and not acc1.account_name:
                acc1.account_name = "Jameel"
            acc2 = db.query(PortalAccount).filter(PortalAccount.username == "ammarashrafsialkot@gmail.com").first()
            if acc2 and not acc2.account_name:
                acc2.account_name = "Tayyab"
            db.commit()

if __name__ == "__main__":
    init_db()
