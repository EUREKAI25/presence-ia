"""Abstract email provider."""
from abc import ABC, abstractmethod
from typing import Optional
from ....models import SendingMailboxDB


class AbstractEmailProvider(ABC):

    @abstractmethod
    def send(self, mailbox: SendingMailboxDB, to_email: str, to_name: str,
             subject: str, body_html: str, body_text: Optional[str] = None,
             reply_to: Optional[str] = None, headers: Optional[dict] = None) -> dict:
        ...

    @abstractmethod
    def validate_domain(self, domain_name: str) -> dict:
        ...

    @abstractmethod
    def get_sending_stats(self, mailbox_email: str, window_hours: int = 24) -> dict:
        ...

    def name(self) -> str:
        return self.__class__.__name__
