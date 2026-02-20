"""Bloc Testimonial — témoignages en grille ou carousel."""
from typing import List, Literal, Optional
from pydantic import BaseModel
from .base import BaseBlock, BlockStructure, BlockSeed


class TestimonialItemSeed(BaseModel):
    name: str
    role: Optional[str] = None
    content: str
    avatar: Optional[str] = None


class TestimonialStructure(BlockStructure):
    layout: Literal["grid", "carousel"] = "grid"
    columns: int = 3


class TestimonialSeed(BlockSeed):
    title: Optional[str] = None
    items: List[TestimonialItemSeed] = []


class TestimonialBlock(BaseBlock):
    block_type: Literal["testimonial_block"] = "testimonial_block"
    structure: TestimonialStructure = TestimonialStructure()
    seed: TestimonialSeed = TestimonialSeed()
