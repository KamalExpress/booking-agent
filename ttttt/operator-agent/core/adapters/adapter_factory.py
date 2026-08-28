from typing import Type, Dict, Optional
from core.adapters.base_adapter import BasePortalAdapter

class AdapterFactory:
    """
    Registry pattern for Portal Adapters.
    Adapters can self-register, and the execution engine can retrieve them dynamically
    without relying on hardcoded if/else statements.
    """
    
    _registry: Dict[str, Type[BasePortalAdapter]] = {}

    @classmethod
    def register(cls, provider_name: str):
        """
        Decorator to register a portal adapter class.
        Usage:
            @AdapterFactory.register("GVC")
            class GVCAdapter(BasePortalAdapter):
                ...
        """
        def wrapper(adapter_class: Type[BasePortalAdapter]):
            cls._registry[provider_name.upper()] = adapter_class
            return adapter_class
        return wrapper

    @classmethod
    def get_adapter(cls, provider_name: str, **kwargs) -> BasePortalAdapter:
        """
        Retrieve and instantiate the adapter for the given provider name.
        """
        adapter_class = cls._registry.get(provider_name.upper())
        if not adapter_class:
            raise ValueError(f"No adapter registered for provider: {provider_name}")
        return adapter_class(**kwargs)

    @classmethod
    def list_providers(cls) -> list[str]:
        """Return a list of all registered providers."""
        return list(cls._registry.keys())
