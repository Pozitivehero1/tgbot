"""Abstract interfaces for repositories and services."""

from football_bot.core.interfaces.repository import (
    AbstractNewsRepository,
    AbstractMatchRepository,
    AbstractPublicationRepository,
)
from football_bot.core.interfaces.service import (
    AbstractLLMService,
    AbstractParserService,
    AbstractPublisherService,
)

__all__ = [
    "AbstractNewsRepository",
    "AbstractMatchRepository",
    "AbstractPublicationRepository",
    "AbstractLLMService",
    "AbstractParserService",
    "AbstractPublisherService",
]
