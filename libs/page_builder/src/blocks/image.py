"""Bloc Image — image seule avec caption optionnelle."""
from typing import Literal, Optional
from .base import BaseBlock, BlockStructure, BlockSeed


class ImageStructure(BlockStructure):
    size: Literal["full", "contained", "thumbnail"] = "contained"
    caption_position: Literal["below", "overlay", "none"] = "none"
    aspect_ratio: Optional[str] = None


class ImageSeed(BlockSeed):
    src: str = ""
    alt: str = ""
    caption: Optional[str] = None


class ImageBlock(BaseBlock):
    block_type: Literal["image_block"] = "image_block"
    structure: ImageStructure = ImageStructure()
    seed: ImageSeed = ImageSeed()
