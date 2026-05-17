from nicegui import ui
from .header import nav_header
from .footer import nav_footer


def init_contact_page() -> None:
    @ui.page('/contact')
    async def contact_page() -> None:
        nav_header()

        with ui.element('main').classes('w-full max-w-4xl mx-auto px-6 py-12'):
            # Page header
            with ui.column().classes('w-full items-center mb-10'):
                ui.label('Contact Us').style(
                    "font-family: 'Plus Jakarta Sans'; font-size: 40px; "
                    "font-weight: 700; line-height: 1.2; letter-spacing: -0.02em; "
                    "color: #171c21;"
                )
                ui.label(
                    'Have a question, need support, or want to report an issue? '
                    "We're here to help."
                ).style(
                    'font-size: 18px; line-height: 1.6; color: #57423d; '
                    'text-align: center; margin-top: 4px; max-width: 600px;'
                )

            with ui.row().classes('w-full gap-6 flex-wrap items-start'):
                # Contact form
                with ui.element('div').classes('flex-1 p-8 rounded-xl').style(
                    'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05); '
                    'border-left: 4px solid #a03a21; min-width: 360px;'
                ):
                    ui.label('Send a Message').style(
                        "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                        "font-weight: 600; color: #171c21; margin-bottom: 1.5rem;"
                    )

                    with ui.column().classes('w-full gap-5'):
                        with ui.row().classes('w-full gap-4'):
                            with ui.column().classes('flex-1 gap-1'):
                                ui.label('First Name').style(
                                    'font-weight: 600; font-size: 14px; color: #171c21;'
                                )
                                name_input = ui.input(
                                    placeholder='Your first name'
                                ).classes('w-full').props('outlined dense')
                            with ui.column().classes('flex-1 gap-1'):
                                ui.label('Last Name').style(
                                    'font-weight: 600; font-size: 14px; color: #171c21;'
                                )
                                last_name_input = ui.input(
                                    placeholder='Your last name'
                                ).classes('w-full').props('outlined dense')

                        with ui.column().classes('w-full gap-1'):
                            ui.label('Email Address').style(
                                'font-weight: 600; font-size: 14px; color: #171c21;'
                            )
                            email_input = ui.input(
                                placeholder='you@example.com'
                            ).classes('w-full').props('outlined dense')

                        with ui.column().classes('w-full gap-1'):
                            ui.label('Subject').style(
                                'font-weight: 600; font-size: 14px; color: #171c21;'
                            )
                            subject_input = ui.select(
                                ['General Inquiry', 'Technical Support',
                                 'Account Issue', 'Report a Bug', 'Other'],
                                label='', value='General Inquiry',
                            ).classes('w-full').props('outlined dense')

                        with ui.column().classes('w-full gap-1'):
                            ui.label('Message').style(
                                'font-weight: 600; font-size: 14px; color: #171c21;'
                            )
                            message_input = ui.textarea(
                                placeholder='Describe your question or issue...'
                            ).classes('w-full').props('outlined rows=5')

                        async def send_message():
                            if not name_input.value or not email_input.value or not message_input.value:
                                ui.notify(
                                    'Please fill in all required fields.',
                                    type='warning',
                                )
                                return
                            ui.notify(
                                'Message sent successfully! '
                                "We'll respond within 24 hours.",
                                type='positive',
                            )
                            message_input.value = ''

                        ui.button(
                            'Send Message', icon='send', on_click=send_message,
                        ).classes('w-full mt-2').style(
                            'background: #a03a21; color: white; font-weight: 600; '
                            'padding: 12px 24px; border-radius: 8px;'
                        ).props('no-caps')

                # Sidebar info
                with ui.column().classes('gap-6').style(
                    'width: 280px; flex-shrink: 0;'
                ):
                    # Support info
                    with ui.element('div').classes('w-full p-6 rounded-xl').style(
                        'background: #fff7ed; border: 1px solid rgba(251,191,36,0.2);'
                    ):
                        with ui.row().classes('items-center gap-2 mb-4'):
                            ui.icon('support_agent').style(
                                'font-size: 24px; color: #9a3412;'
                            )
                            ui.label('Support').style(
                                "font-family: 'Plus Jakarta Sans'; font-size: 18px; "
                                "font-weight: 600; color: #9a3412;"
                            )
                        for icon_name, label, value in [
                            ('mail', 'Email', 'paws.ledger@gmail.com'),
                            ('schedule', 'Response Time', 'Within five business days'),
                            ('language', 'Languages', 'English'),
                        ]:
                            with ui.row().classes('items-center gap-3 py-2'):
                                ui.icon(icon_name).style(
                                    'font-size: 16px; color: #9a3412;'
                                )
                                with ui.column().classes('gap-0'):
                                    ui.label(label).style(
                                        'font-size: 11px; font-weight: 600; '
                                        'color: #8a716c; text-transform: uppercase;'
                                    )
                                    ui.label(value).style(
                                        'font-size: 14px; color: #171c21;'
                                    )

                    # FAQ link
                    with ui.element('div').classes('w-full p-6 rounded-xl').style(
                        'background: #f0f4fb; border: 1px solid rgba(222,192,185,0.3);'
                    ):
                        with ui.row().classes('items-center gap-2 mb-3'):
                            ui.icon('help_center').style(
                                'font-size: 20px; color: #a03a21;'
                            )
                            ui.label('Quick Answers').style(
                                'font-weight: 600; font-size: 16px; color: #171c21;'
                            )
                        ui.label(
                            'Check our FAQ for instant answers to common questions '
                            'about microchipping, registration, and tags.'
                        ).style('font-size: 13px; color: #57423d; margin-bottom: 1rem;')
                        ui.button(
                            'Visit FAQ', icon='arrow_forward',
                            on_click=lambda: ui.navigate.to('/faq'),
                        ).props('flat no-caps').style(
                            'color: #a03a21; font-weight: 600;'
                        )

        nav_footer()
