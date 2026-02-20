"""
Protocol Renderer — interface pluggable pour les renderers (HTML, JSON, PDF…).
"""
from typing import Protocol, runtime_checkable
from ..core.schemas import Page
from ..blocks.base import BaseBlock


@runtime_checkable
class Renderer(Protocol):
    def render_page(self, page: Page) -> str: ...
    def render_block(self, block: BaseBlock) -> str: ...
