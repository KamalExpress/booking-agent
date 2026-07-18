import os
from typing import Dict, Any

class EnvironmentBranding:
    def __init__(self, env: str = None):
        # Allow passing env, otherwise read from ENVIRONMENT or SAAS_ENVIRONMENT
        self.env = env or os.getenv("ENVIRONMENT") or os.getenv("SAAS_ENVIRONMENT", "production").lower()
        self.is_staging = self.env == "staging"
        
        self.app_name = "KE Agent Staging" if self.is_staging else "KE Agent"
        self.short_name = "KE Staging" if self.is_staging else "KE Agent"
        
        # UI Colors and Styling
        self.theme_color = "#f59e0b" if self.is_staging else "#4f46e5" # Amber for staging, indigo for prod
        self.border_class = "border-t-4 border-amber-500" if self.is_staging else ""
        self.badge_text = "STAGING" if self.is_staging else ""
        self.title_prefix = "[STAGING] " if self.is_staging else ""
        self.notification_prefix = "🧪 KE Agent Staging: " if self.is_staging else ""
        
        # PWA Unique ID
        self.manifest_id = "/?env=staging" if self.is_staging else "/?env=prod"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "env": self.env,
            "is_staging": self.is_staging,
            "app_name": self.app_name,
            "short_name": self.short_name,
            "theme_color": self.theme_color,
            "border_class": self.border_class,
            "badge_text": self.badge_text,
            "title_prefix": self.title_prefix,
            "notification_prefix": self.notification_prefix,
            "manifest_id": self.manifest_id
        }

_branding_instance = None

def get_env_branding() -> EnvironmentBranding:
    global _branding_instance
    if _branding_instance is None:
        _branding_instance = EnvironmentBranding()
    return _branding_instance
