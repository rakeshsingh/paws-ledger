from nicegui import ui
from .header import nav_header
from .footer import nav_footer


def init_terms_page() -> None:
    @ui.page('/terms')
    async def terms_page() -> None:
        nav_header()

        with ui.element('main').classes('w-full max-w-4xl mx-auto px-6 py-16'):
            with ui.column().classes('w-full items-center mb-12'):
                ui.label('Terms of Service').style(
                    "font-family: 'Plus Jakarta Sans'; font-size: 40px; "
                    "font-weight: 700; line-height: 1.2; letter-spacing: -0.02em; "
                    "color: #171c21; text-align: center;"
                )
                ui.label(
                    'Please read these terms carefully before using PawsLedger.'
                ).style(
                    'font-size: 18px; color: #57423d; text-align: center; '
                    'margin-top: 0.5rem; max-width: 600px;'
                )
                ui.label('Last updated: May 17, 2026').style(
                    'font-size: 14px; color: #8a716c; margin-top: 0.5rem;'
                )

            with ui.column().classes('w-full gap-10'):
                _section(
                    'Acceptance of Terms',
                    'handshake',
                    'By accessing or using PawsLedger ("the Service"), you agree to be bound '
                    'by these Terms of Service. If you do not agree, you may not use the Service. '
                    'We may update these terms from time to time; continued use after changes '
                    'constitutes acceptance.',
                )

                _section(
                    'Description of Service',
                    'pets',
                    'PawsLedger is a pet microchip registry and recovery platform. The Service '
                    'allows pet owners to register microchip numbers, manage vaccination records, '
                    'link NFC/QR identification tags, share time-limited access with caregivers, '
                    'and receive notifications when their pet is scanned by a finder.',
                )

                _section(
                    'Account Registration',
                    'person',
                    'You must sign in using a Google account. You are responsible for maintaining '
                    'the security of your Google account credentials. You must provide accurate '
                    'and current information. You may register up to 5 pets per account. One account '
                    'per person; shared or automated accounts are not permitted.',
                )

                _section(
                    'Acceptable Use',
                    'check_circle',
                    'You agree to use the Service only for lawful purposes related to pet '
                    'identification and recovery. You must not: (a) register pets you do not own '
                    'or have legal authority over; (b) submit false or misleading microchip or '
                    'vaccination information; (c) use the nudge system to harass, threaten, or '
                    'spam other users; (d) attempt to access another user\'s account or data; '
                    '(e) reverse-engineer, scrape, or overload the Service; or (f) use the '
                    'Service for any commercial purpose without prior written consent.',
                )

                _section(
                    'Pet Data & Ownership',
                    'verified_user',
                    'You represent that you are the legal owner (or authorized caregiver) of any '
                    'pet you register. PawsLedger does not adjudicate ownership disputes. If a '
                    'dispute arises, we may suspend access to the contested pet record pending '
                    'resolution. You are responsible for keeping your pet\'s information accurate '
                    'and up to date.',
                )

                _section(
                    'Shared Access & Tokens',
                    'share',
                    'You may generate time-limited access tokens to share pet information with '
                    'caregivers or veterinarians. Tokens expire automatically. You are responsible '
                    'for revoking tokens you no longer wish to be active. PawsLedger is not liable '
                    'for information accessed via valid, unexpired tokens.',
                )

                _section(
                    'NFC & QR Tags',
                    'nfc',
                    'Physical tags linked through the Service are provided as-is. PawsLedger is not '
                    'responsible for tag hardware failures, loss, or damage. You may deactivate tags '
                    'at any time through your dashboard. Scanning a tag constitutes consent to view '
                    'the public pet profile associated with it.',
                )

                _section(
                    'Privacy',
                    'lock',
                    'Your use of the Service is also governed by our Privacy Policy, available at '
                    'pawsledger.com/privacy. By using the Service, you consent to the collection '
                    'and use of information as described in the Privacy Policy.',
                )

                _section(
                    'Disclaimers',
                    'warning',
                    'The Service is provided "as is" and "as available" without warranties of any '
                    'kind, express or implied. PawsLedger does not guarantee that: (a) microchip '
                    'lookups will always succeed; (b) finders will use the nudge system; (c) the '
                    'Service will be uninterrupted or error-free; or (d) lost pets will be recovered. '
                    'PawsLedger is a communication tool, not an insurance or guarantee of pet recovery.',
                )

                _section(
                    'Limitation of Liability',
                    'shield',
                    'To the maximum extent permitted by law, PawsLedger and its operators shall not '
                    'be liable for any indirect, incidental, special, consequential, or punitive '
                    'damages arising from your use of the Service, including but not limited to loss '
                    'of a pet, unauthorized data access, or service interruptions.',
                )

                _section(
                    'Termination',
                    'block',
                    'We may suspend or terminate your access to the Service at any time for violation '
                    'of these terms or for any reason with reasonable notice. You may delete your '
                    'account at any time by contacting us at paws.ledger@gmail.com. Upon termination, '
                    'your data will be deleted within 30 days unless retention is required by law.',
                )

                _section(
                    'Governing Law',
                    'gavel',
                    'These terms are governed by the laws of Australia. Any disputes shall be resolved '
                    'in the courts of New South Wales, Australia.',
                )

                _section(
                    'Contact',
                    'mail',
                    'For questions about these terms, contact us at paws.ledger@gmail.com or visit '
                    'our Contact page at pawsledger.com/contact.',
                )

        nav_footer()


def _section(title: str, icon: str, text: str) -> None:
    with ui.column().classes('w-full'):
        with ui.row().classes('items-center gap-3 mb-3'):
            ui.icon(icon).style('font-size: 24px; color: #a03a21;')
            ui.label(title).style(
                "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                "font-weight: 600; color: #171c21;"
            )
        ui.label(text).classes('ml-9').style(
            'color: #57423d; font-size: 15px; line-height: 1.6;'
        )
