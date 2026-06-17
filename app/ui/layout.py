"""Page layout wrapper — consistent shell for all pages."""

from contextlib import contextmanager
from nicegui import ui
from .header import nav_header
from .footer import nav_footer


@contextmanager
def page_shell(max_width='4xl'):
    """Wrap page content with header, responsive main container, and footer.

    Usage:
        with page_shell():
            ui.label('Page content here')

        with page_shell(max_width='7xl'):
            ui.label('Wide page')
    """
    nav_header()
    with ui.element('main').classes(
        f'w-full max-w-{max_width} mx-auto px-4 md:px-6 py-8 md:py-12'
    ):
        yield
    nav_footer()
