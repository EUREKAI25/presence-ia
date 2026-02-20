"""Bloc FAQ — accordion ou liste."""
from typing import List, Literal, Optional
from pydantic import BaseModel
from .base import BaseBlock, BlockStructure, BlockSeed


class FAQItem(BaseModel):
    question: str
    answer: str


class FAQStructure(BlockStructure):
    style: Literal["accordion", "list"] = "accordion"
    max_width: str = "800px"


class FAQSeed(BlockSeed):
    title: Optional[str] = None
    items: List[FAQItem] = []


class FAQBlock(BaseBlock):
    block_type: Literal["faq_block"] = "faq_block"
    structure: FAQStructure = FAQStructure()
    seed: FAQSeed = FAQSeed()
