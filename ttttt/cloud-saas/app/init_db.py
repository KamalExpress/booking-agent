import os
from sqlalchemy.orm import Session
from models import Base, engine, Tenant, User, RoleEnum, MonitorConfig, ScraperAccount, SystemSetting
from auth import get_password_hash
from sqlalchemy import text

def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
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
