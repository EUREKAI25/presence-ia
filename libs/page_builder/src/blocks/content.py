"""Bloc Content — bloc générique dict key→ContentItem."""
from typing import Dict, Literal, Optional
from pydantic import BaseModel
from .base import BaseBlock, BlockStructure, BlockSeed


class ContentItem(BaseModel):
    type: Literal["text", "html", "image", "link"] = "text"
    value: str = ""
    alt: Optional[str] = None


class ContentStructure(BlockStructure):
    variant: Literal["default", "card", "highlight", "media_left", "media_right"] = "default"


class ContentSeed(BlockSeed):
    items: Dict[str, ContentItem] = {}


class ContentBlock(BaseBlock):
    block_type: Literal["content_block"] = "content_block"
    structure: ContentStructure = ContentStructure()
    seed: ContentSeed = ContentSeed()
