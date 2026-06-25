"""Model routing behind a provider interface. Offline fallback always works."""
from .provider import Provider, route, available_providers
from .offline import OfflineProvider

__all__ = ["Provider", "route", "available_providers", "OfflineProvider"]
