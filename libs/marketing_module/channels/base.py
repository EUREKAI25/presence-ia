"""Abstract channel interface — all channels must implement this."""
from abc import ABC, abstractmethod
from typing import Optional
from ..models import ProspectDeliveryDB


class AbstractChannel(ABC):

    @abstractmethod
    def send(self, delivery: ProspectDeliveryDB, rendered_content: dict) -> dict:
        """
        Send one message via this channel.
        rendered_content: {"subject": str, "body_html": str, "body_text": str, ...}
        Returns: {"success": bool, "message_id": str} | {"success": False, "error": str}
        """
        ...

    @abstractmethod
    def name(self) -> str:
        ...
