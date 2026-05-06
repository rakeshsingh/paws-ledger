from nicegui import ui
from .header import nav_header
from .footer import nav_footer


# FAQ data organized by category
FAQ_SECTIONS = [
    {
        'title': 'About Microchipping',
        'icon': 'pets',
        'items': [
            (
                'What is a microchip?',
                'A microchip is a tiny transponder about the size of a grain of rice that uses '
                'radio frequency waves to transmit a unique ID number associated with your pet. '
                "It's implanted just under the skin, between the shoulder blades by a veterinary professional."
            ),
            (
                'How does a microchip work?',
                'The microchip is passive — it has no battery or power supply. It is activated only when '
                'it comes in contact with a handheld scanner used by a trained animal professional. '
                'The scanner reads the radio frequency and displays your pet\'s unique 15-digit ID number, '
                'which is then searched in a registry like PawsLedger to find your contact information.'
            ),
            (
                'Will the microchip ever wear out or need to be replaced?',
                "Since there's no battery and no moving parts, there's nothing to wear out or replace. "
                "Microchips are designed to last your pet's entire lifetime."
            ),
            (
                'Does a microchip have GPS tracking?',
                'No. A microchip cannot provide location data. It is only when your lost pet is found, '
                'scanned, and searched in an online registry that someone will be able to contact you. '
                'This is why keeping your contact information current in PawsLedger is critical.'
            ),
            (
                'Can a microchip replace my pet\'s collar and tags?',
                'No. A microchip is a backup to collar tags, not a replacement. Your pet should continue '
                'to wear collar tags. The most important information on your pet\'s collar tag is your '
                'telephone number. PawsLedger also supports NFC and QR physical tags for instant digital identification.'
            ),
            (
                'Are there different kinds of microchips?',
                'Yes. There are three pet identification microchip frequencies: 125 kHz, 128 kHz, and 134.2 kHz. '
                'The 134.2 kHz ISO standard is the primary frequency used worldwide and is recommended by the '
                'AVMA, AAHA, HSUS, and ASPCA. If your pet does not have an ISO 134.2 kHz microchip, you may '
                'need one for international travel.'
            ),
            (
                'What does a microchip number look like?',
                'ISO microchips always contain exactly 15 digits, start with the number 9, and cannot contain '
                'letters, spaces, or dashes (e.g. 985000123456789). Non-ISO microchips have 9-10 characters '
                'and may contain a mix of numbers and letters. PawsLedger validates the format when you register.'
            ),
        ],
    },
    {
        'title': 'About PawsLedger',
        'icon': 'verified_user',
        'items': [
            (
                'What is PawsLedger?',
                'PawsLedger is a universal microchip registry and pet recovery network. We provide '
                'finders with tools to scan and contact owners instantly, and pet parents with peace '
                'of mind through secure digital identity management, vaccination records, and NFC/QR tag support.'
            ),
            (
                'How does PawsLedger work?',
                '1) Register your pet with their microchip number. '
                '2) If your pet gets lost and is scanned, the chip number is searched in PawsLedger. '
                '3) The finder can nudge you through our secure relay — you receive an instant alert. '
                '4) You coordinate a safe reunion without exposing your personal information.'
            ),
            (
                'Is PawsLedger compatible with the AAHA Universal Pet Microchip Lookup?',
                'Yes. PawsLedger integrates with the AAHA Universal Pet Microchip Lookup network, '
                'meaning your pet can be found through any participating registry or veterinary clinic.'
            ),
            (
                'How much does it cost to register my pet?',
                'PawsLedger offers a Forever Free tier that includes public identity lookup, emergency '
                'medical alerts, and basic ownership features. Premium tiers (Verified and Guardian) '
                'offer additional features like vaccination storage, sealed PDFs, and AI photo-matching.'
            ),
            (
                'How many pets can I register?',
                'You can register up to 5 pets per account on PawsLedger.'
            ),
        ],
    },
    {
        'title': 'Registration & Account',
        'icon': 'person_add',
        'items': [
            (
                'How do I register my pet on PawsLedger?',
                'Sign in with your Google account, then click "Register Pet" or the Protect button on the '
                'home page. Fill in your pet\'s name, species, breed, gender, birth date, and 15-digit '
                'microchip number. You can also add care information and link a physical NFC/QR tag during registration.'
            ),
            (
                'Do I need to register the microchip after implantation?',
                'Yes! Simply microchipping your pet is not enough — you must register the microchip number '
                'and your contact details in a database like PawsLedger so your information can be found '
                'if you are separated from your pet.'
            ),
            (
                'How do I update my contact information?',
                'Go to your Owner Profile (click your name in the header → My Profile) and click "Edit Profile" '
                'to update your name, email, phone, address, city, and country.'
            ),
            (
                'What if my pet has more than one microchip?',
                'If your pet has multiple microchips, we recommend registering each one separately. '
                'If your pet is lost and found, it is possible that only one chip will be read, '
                'so keeping each one registered and updated is important.'
            ),
            (
                'How do I transfer my pet to another person?',
                'PawsLedger supports ownership transfers. The new owner creates their own account '
                'and the transfer is recorded in the pet\'s audit trail for full provenance tracking.'
            ),
            (
                "What if I don't know my pet's microchip number?",
                'Contact the clinic or facility that implanted the microchip — they can look it up in '
                "your pet's medical records. If you're unsure where your pet was chipped, any vet or "
                'shelter with a universal scanner can read it for you.'
            ),
        ],
    },
    {
        'title': 'NFC & QR Tags',
        'icon': 'nfc',
        'items': [
            (
                'What are NFC/QR tags?',
                'Physical tags (on collars, harnesses, or keychains) that contain a unique code. '
                'When scanned with a phone (NFC tap or QR camera scan), they instantly pull up your '
                "pet's emergency profile on PawsLedger — no app download required for the finder."
            ),
            (
                'How do I link a tag to my pet?',
                "Go to your pet's profile page, scroll to the NFC/QR Tags section, and click "
                '"Add New Tag". Choose the tag type (QR, NFC, or Dual), enter the tag code '
                '(or let PawsLedger auto-generate one), and save.'
            ),
            (
                'What happens when someone scans my pet\'s tag?',
                "The scanner is taken to your pet's public emergency profile (with privacy-obfuscated "
                'owner info). The scan is logged in the audit trail and you receive an email notification '
                'that your pet\'s tag was scanned, along with the general location.'
            ),
            (
                'Can I deactivate a lost or replaced tag?',
                'Yes. From your pet\'s profile, you can deactivate any tag. Deactivated tags will no '
                'longer resolve to a profile when scanned. You can also reactivate them later if found.'
            ),
        ],
    },
    {
        'title': 'Privacy & Security',
        'icon': 'security',
        'items': [
            (
                'Is my personal information safe?',
                'Yes. PawsLedger encrypts your personal data and never exposes your name, address, '
                'phone, or email to finders. Communication happens through our secure relay system. '
                'Your information is only used for medical coordination and pet recovery.'
            ),
            (
                'Will I be solicited or have my data sold?',
                'No. PawsLedger maintains a strict non-solicitation policy. Your information will not '
                'be sold to third parties.'
            ),
            (
                'What can a finder see when they look up my pet?',
                "Finders see a privacy-obfuscated profile: the pet's species, breed, vaccination status, "
                'and general location area. They cannot see your name, address, phone, or email. '
                'They can send you a "nudge" through our secure system.'
            ),
        ],
    },
    {
        'title': 'Why Microchip Your Pet?',
        'icon': 'favorite',
        'items': [
            (
                'Why should I microchip my pet?',
                'Every year thousands of lost pets are taken in by shelters and never make it home '
                'because they cannot be identified. Microchipping is the only truly permanent method '
                'of identification — collar tags can break or become illegible, but a microchip lasts '
                "your pet's lifetime."
            ),
            (
                'Top 5 reasons to microchip your pet',
                '1) Only true permanent method of pet identification. '
                "2) Lasts for the lifetime of your pet. "
                '3) Quick and painless procedure, just like a vaccination. '
                '4) Best chance of your pet returning to you if they go missing. '
                '5) Recommended by the AVMA, AAHA, ASPCA, the Humane Society, and others.'
            ),
            (
                'How are pets microchipped?',
                'A veterinary professional implants the microchip using a sterile applicator — similar '
                'to administering a routine vaccination. The process takes only a few seconds, requires '
                'no anesthetic, and your pet will not react any more than they would to a standard shot.'
            ),
        ],
    },
]


def init_faq_page():
    @ui.page('/faq')
    async def faq_page():
        nav_header()

        with ui.element('main').classes('w-full max-w-4xl mx-auto px-6 py-16'):
            # Header
            with ui.column().classes('w-full items-center mb-12'):
                ui.label('Frequently Asked Questions').style(
                    "font-family: 'Plus Jakarta Sans'; font-size: 40px; "
                    "font-weight: 700; line-height: 1.2; letter-spacing: -0.02em; "
                    "color: #171c21; text-align: center;"
                )
                ui.label(
                    'Everything you need to know about microchipping, '
                    'pet registration, and PawsLedger.'
                ).style(
                    'font-size: 18px; color: #57423d; text-align: center; '
                    'margin-top: 0.5rem; max-width: 600px;'
                )

            # FAQ sections
            for section in FAQ_SECTIONS:
                with ui.column().classes('w-full mb-10'):
                    # Section header
                    with ui.row().classes('items-center gap-3 mb-4'):
                        ui.icon(section['icon']).style(
                            'font-size: 24px; color: #a03a21;'
                        )
                        ui.label(section['title']).style(
                            "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                            "font-weight: 600; color: #171c21;"
                        )

                    # Questions
                    for question, answer in section['items']:
                        with ui.expansion(question).classes('w-full').props(
                            'dense header-class="text-weight-medium"'
                        ):
                            ui.label(answer).style(
                                'color: #57423d; font-size: 15px; '
                                'line-height: 1.6; padding: 8px 0;'
                            )

            # Source attribution
            with ui.row().classes('w-full items-center gap-2 mt-8 pt-8').style(
                'border-top: 1px solid #eaeef5;'
            ):
                ui.icon('info').style('font-size: 16px; color: #8a716c;')
                ui.html(
                    '<span style="font-size: 12px; color: #8a716c;">'
                    'Content was rephrased for compliance with licensing restrictions. '
                    'Microchipping information adapted from industry guidelines by '
                    '<a href="https://www.freepetchipregistry.com/faqs/" '
                    'style="color: #a03a21; text-decoration: underline;" '
                    'target="_blank">FreePetChipRegistry</a>, AAHA, and AVMA recommendations.'
                    '</span>'
                )

        nav_footer()
