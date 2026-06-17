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
from .privacy import init_privacy_page
from .terms import init_terms_page
from .subscription import init_subscription_pages
from .lookup import init_lookup_page
from .manage_shared_access import init_shared_access_management_page
from .manage_tags import init_manage_tags_page
from .nudge_reply import init_nudge_reply_page
from .nudge_history import init_nudge_history_page


def init_pages():
    app.add_static_files('/static', _STATIC_DIR)

    # Google Analytics (gtag.js) — shared=True ensures it's in every page's initial HTML response
    ga_id = os.getenv('GA_MEASUREMENT_ID', 'G-VQSSWXZFKL')
    if ga_id:
        ui.add_head_html(
            f'<script async src="https://www.googletagmanager.com/gtag/js?id={ga_id}"></script>\n'
            f'<script>\n'
            f'  window.dataLayer = window.dataLayer || [];\n'
            f'  function gtag(){{dataLayer.push(arguments);}}\n'
            f'  gtag(\'js\', new Date());\n'
            f'  gtag(\'config\', \'{ga_id}\');\n'
            f'</script>',
            shared=True,
        )

    ui.add_head_html(GLOBAL_CSS_LINK)

    # Auto-reload fallback: if NiceGUI WebSocket doesn't connect within 3s,
    # clear stale storage and reload (fixes blank page from corrupt session state)
    ui.add_head_html(
        '<script>\n'
        'setTimeout(function() {\n'
        '  var content = document.querySelector(".nicegui-content");\n'
        '  if (!content || content.children.length === 0) {\n'
        '    // Clear NiceGUI localStorage that may hold stale state\n'
        '    try {\n'
        '      Object.keys(localStorage).forEach(function(key) {\n'
        '        if (key.startsWith("nicegui")) localStorage.removeItem(key);\n'
        '      });\n'
        '    } catch(e) {}\n'
        '    window.location.reload();\n'
        '  }\n'
        '}, 3000);\n'
        '</script>\n'
    )

    # ── SEO: Global meta tags (for NiceGUI-rendered pages like /, /login, /dashboard) ──
    # Note: Public content pages (/about, /faq, /pricing, etc.) are served as
    # pre-rendered HTML by FastAPI routes in seo_pages.py with per-page meta.
    ui.add_head_html(
        '<meta name="google-site-verification" content="tVpTG1skwcyW0gOUWbWUS50-MtKx0mYu86mlUmP4ePA">\n'
        '<meta name="author" content="PawsLedger">\n'
        '<meta property="og:site_name" content="PawsLedger">\n'
        '<meta property="og:image" content="https://www.pawsledger.com/assets/og-image.png">\n'
        '<meta name="twitter:image" content="https://www.pawsledger.com/assets/og-image.png">\n'
    )

    # JSON-LD Structured Data (Organization + WebSite)
    ui.add_head_html(
        '<script type="application/ld+json">\n'
        '{\n'
        '  "@context": "https://schema.org",\n'
        '  "@type": "Organization",\n'
        '  "name": "PawsLedger",\n'
        '  "url": "https://www.pawsledger.com",\n'
        '  "description": "Universal pet microchip registry and recovery network",\n'
        '  "sameAs": []\n'
        '}\n'
        '</script>\n'
        '<script type="application/ld+json">\n'
        '{\n'
        '  "@context": "https://schema.org",\n'
        '  "@type": "WebSite",\n'
        '  "name": "PawsLedger",\n'
        '  "url": "https://www.pawsledger.com",\n'
        '  "potentialAction": {\n'
        '    "@type": "SearchAction",\n'
        '    "target": "https://www.pawsledger.com/?q={search_term_string}",\n'
        '    "query-input": "required name=search_term_string"\n'
        '  }\n'
        '}\n'
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
    init_privacy_page()
    init_terms_page()
    init_subscription_pages()
    init_lookup_page()
    init_shared_access_management_page()
    init_manage_tags_page()
    init_nudge_reply_page()
    init_nudge_history_page()
