"""Bloc Stat — statistiques avec valeur + label + source optionnelle."""
from typing import List, Literal, Optional
from pydantic import BaseModel
from .base import BaseBlock, BlockStructure, BlockSeed


class StatItem(BaseModel):
    value: str
    label: str
    source_url: Optional[str] = None


class StatStructure(BlockStructure):
    layout: Literal["horizontal", "vertical"] = "horizontal"
    show_sources: bool = False


class StatSeed(BlockSeed):
    stats: List[StatItem] = []


class StatBlock(BaseBlock):
    block_type: Literal["stat_block"] = "stat_block"
    structure: StatStructure = StatStructure()
    seed: StatSeed = StatSeed()
