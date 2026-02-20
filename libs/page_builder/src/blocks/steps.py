"""Bloc Steps — étapes horizontales/verticales (cards, timeline, simple)."""
from typing import List, Literal, Optional
from pydantic import BaseModel
from .base import BaseBlock, BlockStructure, BlockSeed


class StepItem(BaseModel):
    title: Optional[str] = None
    description: str = ""
    icon: Optional[str] = None


class StepsStructure(BlockStructure):
    direction: Literal["horizontal", "vertical"] = "horizontal"
    numbering: Literal["numeric", "icon", "none"] = "numeric"
    variant: Literal["cards", "timeline", "simple"] = "cards"


class StepsSeed(BlockSeed):
    title: str = ""
    subtitle: Optional[str] = None
    steps: List[StepItem] = []


class StepsBlock(BaseBlock):
    block_type: Literal["steps_block"] = "steps_block"
    structure: StepsStructure = StepsStructure()
    seed: StepsSeed = StepsSeed()
