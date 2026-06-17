from nicegui import ui
from .layout import page_shell


def init_privacy_page() -> None:
    @ui.page('/privacy')
    async def privacy_page() -> None:
        with page_shell():
            with ui.column().classes('w-full items-center mb-12'):
                ui.label('Privacy Policy').classes('pl-heading-3xl').style(
                    'text-align: center;'
                )
                ui.label(
                    'How PawsLedger collects, uses, and protects your information.'
                ).style(
                    'font-size: 18px; color: #57423d; text-align: center; '
                    'margin-top: 0.5rem; max-width: 600px;'
                )
                ui.label('Last updated: May 17, 2026').style(
                    'font-size: 14px; color: #8a716c; margin-top: 0.5rem;'
                )

            with ui.column().classes('w-full gap-10'):
                _section(
                    'Information We Collect',
                    'account_circle',
                    [
                        (
                            'Account Information',
                            'When you sign in with Google, we receive your name, email address, '
                            'and a unique account identifier (Google "sub" ID). We do not receive '
                            'or store your Google password.',
                        ),
                        (
                            'Pet Information',
                            'You may voluntarily provide your pet\'s name, species, breed, date of birth, '
                            'microchip number, vaccination records, care details, and photos.',
                        ),
                        (
                            'Contact Details',
                            'You may optionally add a phone number, mailing address, city, and country '
                            'to your owner profile for pet recovery purposes.',
                        ),
                        (
                            'Usage Data',
                            'We use Google Analytics to collect anonymous usage statistics such as pages '
                            'visited, browser type, and device information. This data is not linked to '
                            'your identity.',
                        ),
                    ],
                )

                _section(
                    'How We Use Your Information',
                    'visibility',
                    [
                        (
                            'Pet Recovery',
                            'Your contact details are used solely to facilitate reunification if your '
                            'pet is found. Finders never see your personal information directly — '
                            'communication happens through our secure nudge relay.',
                        ),
                        (
                            'Account & Notifications',
                            'Your email is used to send you scan alerts, nudge notifications, and '
                            'critical service communications (e.g., security notices). We will never '
                            'send unsolicited marketing emails.',
                        ),
                        (
                            'Service Improvement',
                            'Aggregated, anonymized usage data helps us understand how the platform is '
                            'used so we can improve features and performance.',
                        ),
                    ],
                )

                _section(
                    'Information Sharing',
                    'share',
                    [
                        (
                            'No Sale of Data',
                            'We do not sell, rent, or trade your personal information to any third party.',
                        ),
                        (
                            'Limited Disclosure',
                            'We may share information only in the following cases: (1) with your explicit '
                            'consent, (2) to comply with legal obligations, or (3) to protect the safety '
                            'of users or the public.',
                        ),
                        (
                            'Public Pet Profiles',
                            'When a finder scans your pet\'s tag or looks up a microchip number, they see '
                            'a limited profile: pet species, breed, vaccination status, and general location '
                            'area. Your name, email, phone, and address are never exposed.',
                        ),
                    ],
                )

                _section(
                    'Cookies & Local Storage',
                    'cookie',
                    [
                        (
                            'Session Cookie',
                            'We set a signed "paws_user_id" cookie to keep you logged in. This cookie '
                            'is HTTP-only, uses the Lax same-site policy, and is secured with HTTPS in '
                            'production. It expires after 7 days.',
                        ),
                        (
                            'OAuth State',
                            'A temporary session cookie is used during the Google sign-in flow to prevent '
                            'cross-site request forgery. It is cleared after authentication completes.',
                        ),
                        (
                            'Analytics',
                            'Google Analytics sets its own cookies to distinguish unique visitors. '
                            'You can opt out by using a browser extension or disabling cookies.',
                        ),
                    ],
                )

                _section(
                    'Data Security',
                    'lock',
                    [
                        (
                            'Encryption',
                            'All connections to PawsLedger are encrypted via TLS (HTTPS). Session cookies '
                            'are cryptographically signed to prevent tampering.',
                        ),
                        (
                            'Access Controls',
                            'Only authenticated users can access their own data. Shared access tokens are '
                            'time-limited and revocable.',
                        ),
                        (
                            'Vaccination Integrity',
                            'Vaccination records are individually hashed (SHA-256) so any modification can '
                            'be detected.',
                        ),
                    ],
                )

                _section(
                    'Data Retention & Deletion',
                    'delete_forever',
                    [
                        (
                            'Retention',
                            'Your account and pet data are retained as long as your account is active. '
                            'Shared access tokens expire automatically based on the duration you set.',
                        ),
                        (
                            'Account Deletion',
                            'You may request deletion of your account and all associated data by '
                            'contacting us at paws.ledger@gmail.com. We will process deletion requests '
                            'within 30 days.',
                        ),
                    ],
                )

                _section(
                    'Your Rights',
                    'gavel',
                    [
                        (
                            'Access & Portability',
                            'You can view all your data through your dashboard at any time. You may '
                            'request an export of your data by contacting us.',
                        ),
                        (
                            'Correction',
                            'You can update your profile information and pet details directly through '
                            'the PawsLedger interface.',
                        ),
                        (
                            'Deletion',
                            'You may request complete deletion of your account and data as described above.',
                        ),
                    ],
                )

                _section(
                    'Changes to This Policy',
                    'update',
                    [
                        (
                            'Notification',
                            'We will notify you of material changes to this policy via email or a '
                            'prominent notice on the site. Continued use after changes constitutes '
                            'acceptance of the updated policy.',
                        ),
                    ],
                )

                _section(
                    'Contact',
                    'mail',
                    [
                        (
                            'Questions?',
                            'If you have questions about this privacy policy or your data, '
                            'contact us at paws.ledger@gmail.com or visit our Contact page.',
                        ),
                    ],
                )



def _section(title: str, icon: str, items: list) -> None:
    with ui.column().classes('w-full'):
        with ui.row().classes('items-center gap-3 mb-4'):
            ui.icon(icon).style('font-size: 24px; color: var(--pl-primary);')
            ui.label(title).classes('pl-heading-xl')
        for subtitle, text in items:
            with ui.column().classes('w-full ml-9 mb-3'):
                ui.label(subtitle).style(
                    'font-weight: 600; font-size: 15px; color: #171c21; '
                    'margin-bottom: 2px;'
                )
                ui.label(text).style(
                    'color: #57423d; font-size: 15px; line-height: 1.6;'
                )
