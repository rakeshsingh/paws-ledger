"""Shared helpers for the pet profile package."""

import os
from contextlib import asynccontextmanager

from nicegui import ui

from ..common import (
    SPECIES_ICONS, SPECIES_ICON_DEFAULT, SPECIES_BG, SPECIES_BG_DEFAULT,
    SPECIES_FG, SPECIES_FG_DEFAULT,
)


def with_loading(button):
    """Context manager that disables a button during an async operation."""
    @asynccontextmanager
    async def _ctx():
        button.disable()
        try:
            yield
        finally:
            button.enable()

    return _ctx()


def obfuscate(value: str) -> str:
    """Show first character followed by asterisks for privacy."""
    if not value:
        return '***'
    return value[0] + '***'


def pet_avatar(pet, size: int = 128):
    """Render pet photo or species icon placeholder."""
    if pet.photo_url:
        photo_src = f'/api/v1/pets/{pet.id}/photo'
        ui.image(photo_src).classes('rounded-full').style(
            f'width: {size}px; height: {size}px; object-fit: cover; '
            'border: 4px solid white; box-shadow: 0 4px 12px rgba(0,0,0,0.1);'
        )
    else:
        species = pet.pet_species or 'DOG'
        bg = SPECIES_BG.get(species, SPECIES_BG_DEFAULT)
        fg = SPECIES_FG.get(species, SPECIES_FG_DEFAULT)
        icon_name = SPECIES_ICONS.get(species, SPECIES_ICON_DEFAULT)
        with ui.element('div').classes(
            'flex items-center justify-center rounded-full'
        ).style(
            f'width: {size}px; height: {size}px; background: {bg}; '
            'border: 4px solid white; box-shadow: 0 4px 12px rgba(0,0,0,0.1);'
        ):
            ui.icon(icon_name).style(f'font-size: {size // 2}px; color: {fg};')


def get_user_tier(user_id, session) -> str:
    """Get subscription tier for a user."""
    from ...models import Subscription  # noqa: E402
    from sqlmodel import select
    sub = session.exec(
        select(Subscription).where(Subscription.user_id == user_id)
    ).first()
    if not sub or sub.status != "active":
        return "free"
    return sub.tier


def render_leaflet_map(div_id: str, markers: list, fit_bounds: bool = True, zoom: int = 11):
    """Inject a Leaflet map with circle markers.

    markers: list of dicts with keys: lat, lon, popup (optional), color (optional)
    """
    import json as _json
    import uuid as _uuid

    ui.add_head_html(
        '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>'
    )
    ui.add_head_html(
        '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
    )

    markers_json = _json.dumps(markers)
    fit_str = 'true' if fit_bounds else 'false'

    ui.run_javascript(f'''
        (function() {{
            var markers = {markers_json};
            var fitBounds = {fit_str};
            var defaultZoom = {zoom};
            function initMap() {{
                var el = document.getElementById("{div_id}");
                if (!el) return setTimeout(initMap, 100);
                if (el._leaflet_id) return;
                var map = L.map("{div_id}", {{
                    zoomControl: true,
                    attributionControl: false,
                    dragging: true,
                    scrollWheelZoom: false,
                }}).setView([20, 0], 2);
                L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
                    maxZoom: 18,
                }}).addTo(map);
                var bounds = [];
                markers.forEach(function(m) {{
                    var latlng = [m.lat, m.lon];
                    bounds.push(latlng);
                    var color = m.color || "#a03a21";
                    var marker = L.circleMarker(latlng, {{
                        radius: m.radius || 8,
                        color: color,
                        fillColor: m.fillColor || "#ffdad2",
                        fillOpacity: m.fillOpacity || 0.5,
                        weight: 2,
                    }}).addTo(map);
                    if (m.popup) marker.bindPopup(m.popup);
                }});
                if (fitBounds && bounds.length > 0) {{
                    map.fitBounds(bounds, {{padding: [30, 30], maxZoom: 13}});
                }} else if (bounds.length === 1) {{
                    map.setView(bounds[0], defaultZoom);
                }}
            }}
            initMap();
        }})();
    ''')
