"""Bloc NavBar — navigation sticky/fixed/relative."""
from typing import List, Literal, Optional
from pydantic import BaseModel
from .base import BaseBlock, BlockStructure, BlockSeed


class NavLink(BaseModel):
    label: str
    href: str
    target: Optional[str] = None


class NavBarStructure(BlockStructure):
    position: Literal["sticky", "fixed", "relative"] = "sticky"
    style: Literal["transparent", "white", "primary"] = "white"


class NavBarSeed(BlockSeed):
    logo_text: str = ""
    logo_href: str = "/"
    logo_img: Optional[str] = None
    links: List[NavLink] = []


class NavBarBlock(BaseBlock):
    block_type: Literal["navbar_block"] = "navbar_block"
    structure: NavBarStructure = NavBarStructure()
    seed: NavBarSeed = NavBarSeed()
