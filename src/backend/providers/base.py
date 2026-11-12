"""Abstract base provider for metadata discovery."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.backend.models.unified import UnifiedShow


class BaseMetadataProvider(ABC):
    """Protocol defining required contracts for metadata discovery providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider implementation."""
        ...

    @abstractmethod
    async def search_shows(self, query: str) -> list[UnifiedShow]:
        """Search shows by title."""
        ...

    @abstractmethod
    async def get_show_details(self, show_id: int) -> UnifiedShow:
        """Fetch comprehensive show details including seasons."""
        ...

    @abstractmethod
    async def get_trending(self) -> list[UnifiedShow]:
        """Fetch currently trending shows."""
        ...
