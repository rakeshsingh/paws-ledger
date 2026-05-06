from nicegui import app, ui
import os
from .common import GLOBAL_CSS_LINK, _STATIC_DIR
from .index import init_index_page
from .about import init_about_page
from .faq import init_faq_page
from .contact import init_contact_page
from .login import init_login_pages
from .owner_dashboard import init_dashboard_page
from .pet_register import init_register_page
from .pet_profile import init_pet_profile_page
from .shared_access import init_shared_access_page
from .qr_profile import init_qr_profile_page
from .lost import init_lost_page
from .verify import init_verify_page
from .owner_profile import init_owner_profile_page
from .pricing import init_pricing_page


def init_pages():
    app.add_static_files('/static', _STATIC_DIR)
    ui.add_head_html(GLOBAL_CSS_LINK)

    # Google Analytics (gtag.js)
    ga_id = os.getenv('GA_MEASUREMENT_ID', 'G-VQSSWXZFKL')
    if ga_id:
        ui.add_head_html(
            f'<script async src="https://www.googletagmanager.com/gtag/js?id={ga_id}"></script>'
            '<script>'
            '  window.dataLayer = window.dataLayer || [];'
            '  function gtag(){dataLayer.push(arguments);}'
            '  gtag("js", new Date());'
            f'  gtag("config", "{ga_id}");'
            '</script>'
        )
    init_index_page()
    init_about_page()
    init_faq_page()
    init_contact_page()
    init_login_pages()
    init_dashboard_page()
    init_register_page()
    init_pet_profile_page()
    init_shared_access_page()
    init_qr_profile_page()
    init_lost_page()
    init_verify_page()
    init_owner_profile_page()
    init_pricing_page()
