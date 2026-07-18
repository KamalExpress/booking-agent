from sqladmin import ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse
import jwt
from models import User, Tenant, Assignment, WorkerNode, EventLog, Lease, PortalAccount, SlotAvailability, WorkerLog, SystemSetting, WorkerVersion, PushSubscription, AuditLog, SessionLocal

# Custom Auth Backend for sqladmin
class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        # Login is handled by the main app, so we just redirect
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        # Check standard JWT token logic from our app
        token = request.cookies.get("token")
        if not token:
            return False
            
        from models import RoleEnum
        from auth import SECRET_KEY, ALGORITHM
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            if user_id is None:
                return False
                
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if not user or not user.is_active:
                    return False
                # IMPORTANT: Only SUPER_ADMIN can access the DBMS
                if user.role != RoleEnum.SUPER_ADMIN:
                    return False
                return True
            finally:
                db.close()
        except jwt.PyJWTError:
            return False

# Model Views
class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.email, User.full_name, User.role, User.tenant_id, User.is_active]
    column_searchable_list = [User.email, User.full_name]
    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True

class TenantAdmin(ModelView, model=Tenant):
    column_list = [Tenant.id, Tenant.name, Tenant.is_active, Tenant.created_at]
    column_searchable_list = [Tenant.name]

class PortalAccountAdmin(ModelView, model=PortalAccount):
    column_list = [PortalAccount.id, PortalAccount.username, PortalAccount.status, PortalAccount.supports_scraping, PortalAccount.supports_booking]
    column_searchable_list = [PortalAccount.username]

class WorkerNodeAdmin(ModelView, model=WorkerNode):
    column_list = [WorkerNode.worker_id, WorkerNode.status, WorkerNode.scheduling_state, WorkerNode.public_ip, WorkerNode.last_heartbeat]
    column_searchable_list = [WorkerNode.worker_id, WorkerNode.public_ip]

class AssignmentAdmin(ModelView, model=Assignment):
    column_list = [Assignment.id, Assignment.visa_center, Assignment.date_from, Assignment.date_to, Assignment.status]
    column_searchable_list = [Assignment.visa_center]

class LeaseAdmin(ModelView, model=Lease):
    column_list = [Lease.id, Lease.assignment_id, Lease.worker_id, Lease.status, Lease.expires_at]

class EventLogAdmin(ModelView, model=EventLog):
    column_list = [EventLog.id, EventLog.event_type, EventLog.severity, EventLog.worker_id, EventLog.assignment_id, EventLog.created_at]
    column_searchable_list = [EventLog.event_type, EventLog.worker_id]
    column_default_sort = [("created_at", True)]

class SlotAvailabilityAdmin(ModelView, model=SlotAvailability):
    column_list = [SlotAvailability.id, SlotAvailability.visa_center, SlotAvailability.date, SlotAvailability.found_by, SlotAvailability.created_at]
    column_default_sort = [("created_at", True)]

class SystemSettingAdmin(ModelView, model=SystemSetting):
    column_list = [SystemSetting.key, SystemSetting.value, SystemSetting.updated_at]
    column_searchable_list = [SystemSetting.key]

class PushSubscriptionAdmin(ModelView, model=PushSubscription):
    column_list = [PushSubscription.id, PushSubscription.user_id, PushSubscription.endpoint, PushSubscription.ip_address, PushSubscription.created_at]
    column_searchable_list = [PushSubscription.endpoint]

# List of all views to register
views = [
    TenantAdmin,
    UserAdmin,
    PortalAccountAdmin,
    WorkerNodeAdmin,
    AssignmentAdmin,
    LeaseAdmin,
    EventLogAdmin,
    SlotAvailabilityAdmin,
    SystemSettingAdmin,
    PushSubscriptionAdmin,
]
