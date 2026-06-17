"""Server-rendered public pages for SEO crawlability.

These FastAPI routes serve fully-rendered HTML for public content pages,
ensuring search engines can index the content without executing JavaScript.
NiceGUI pages still exist for these routes but the FastAPI routes take
priority because they are registered first.
"""

import pathlib
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

_templates_dir = pathlib.Path(__file__).parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_templates_dir)), autoescape=True)

router = APIRouter()

# Page metadata for SEO
_PAGE_META = {
    "about": {
        "title": "About PawsLedger — Universal Pet Microchip Registry & Recovery",
        "description": "Learn how PawsLedger provides decoupled pet identity, trusted ownership transfers, and seamless caregiver access through ISO 11784/11785 compliant microchip registration.",
        "canonical_path": "/about",
    },
    "faq": {
        "title": "FAQ — Pet Microchip Registration, NFC Tags & Recovery | PawsLedger",
        "description": "Answers to common questions about pet microchipping, NFC/QR tag setup, registration, privacy, and how PawsLedger helps reunite lost pets with their owners.",
        "canonical_path": "/faq",
    },
    "pricing": {
        "title": "Pricing — Free Pet Microchip Registry | PawsLedger",
        "description": "PawsLedger registration is free. Compare Free, Verified ($1/mo or $9.99/yr), and Guardian ($4.99/mo or $49.99/yr) plans for vaccination records, NFC tags, and pet recovery features.",
        "canonical_path": "/pricing",
    },
    "verify": {
        "title": "Verify Vaccination Record — SHA-256 Document Verification | PawsLedger",
        "description": "Verify the authenticity of a PawsLedger vaccination PDF by entering its SHA-256 hash. Tamper-evident, cryptographically verifiable medical documentation.",
        "canonical_path": "/verify",
    },
    "contact": {
        "title": "Contact PawsLedger — Support & Help",
        "description": "Get in touch with PawsLedger for support, questions about microchip registration, NFC/QR tags, or account issues. We respond within five business days.",
        "canonical_path": "/contact",
    },
    "privacy": {
        "title": "Privacy Policy — PawsLedger",
        "description": "How PawsLedger collects, uses, and protects your personal information. We never sell your data. Owner information is never exposed to finders.",
        "canonical_path": "/privacy",
    },
    "terms": {
        "title": "Terms of Service — PawsLedger",
        "description": "Terms of Service for PawsLedger pet microchip registry. Covers acceptable use, pet data ownership, NFC/QR tags, shared access tokens, and liability.",
        "canonical_path": "/terms",
    },
}


@router.get("/about", response_class=HTMLResponse)
async def about_page():
    template = _jinja_env.get_template("about.html")
    return template.render(**_PAGE_META["about"])


@router.get("/faq", response_class=HTMLResponse)
async def faq_page():
    from .ui.faq import FAQ_SECTIONS
    template = _jinja_env.get_template("faq.html")
    return template.render(**_PAGE_META["faq"], faq_sections=FAQ_SECTIONS)




@router.get("/verify", response_class=HTMLResponse)
async def verify_page():
    template = _jinja_env.get_template("verify.html")
    return template.render(**_PAGE_META["verify"])


@router.get("/contact", response_class=HTMLResponse)
async def contact_page():
    template = _jinja_env.get_template("contact.html")
    return template.render(**_PAGE_META["contact"])


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page():
    template = _jinja_env.get_template("privacy.html")
    return template.render(**_PAGE_META["privacy"])


@router.get("/terms", response_class=HTMLResponse)
async def terms_page():
    template = _jinja_env.get_template("terms.html")
    return template.render(**_PAGE_META["terms"])
