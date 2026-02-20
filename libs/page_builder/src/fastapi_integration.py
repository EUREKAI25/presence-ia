"""
Helpers pour intégration FastAPI.
"""
from typing import Callable
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from .core.schemas import Page
from .builder import render_page


def create_page_route(
    app: FastAPI,
    path: str,
    page_factory: Callable[[], Page],
    **route_kwargs
):
    """
    Crée une route FastAPI qui rend une page.

    Args:
        app: Instance FastAPI
        path: Chemin de la route (ex: "/")
        page_factory: Fonction qui retourne une Page
        **route_kwargs: Arguments additionnels pour @app.get()

    Example:
        >>> def home_page():
        ...     return Page(
        ...         title="Home",
        ...         sections=[...]
        ...     )
        >>> create_page_route(app, "/", home_page)
    """
    @app.get(path, response_class=HTMLResponse, **route_kwargs)
    def route():
        page = page_factory()
        return HTMLResponse(render_page(page))

    return route


class PageRouter:
    """
    Router pour gérer plusieurs pages.

    Usage:
        >>> router = PageRouter()
        >>> router.add_page("/", lambda: Page(...))
        >>> router.add_page("/about", lambda: Page(...))
        >>> router.register(app)
    """

    def __init__(self):
        self.pages = {}

    def add_page(self, path: str, page_factory: Callable[[], Page]):
        """Ajoute une page au router."""
        self.pages[path] = page_factory

    def register(self, app: FastAPI):
        """Enregistre toutes les routes sur l'app FastAPI."""
        for path, factory in self.pages.items():
            create_page_route(app, path, factory)
