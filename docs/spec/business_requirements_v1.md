# Business Requirements

## Phase 0

1. As a pet owner, I should be able to register to this website using social login (Google)
2. As a pet owner, who is registered to the website, once I login, I should be able to add a pet to my profile.
3. As a registered pet owner, I should be able to add more than one (and a maximum of five) pets to my profile
4. As a registered pet owners, I should be able to see all the pets that I have register on this website on my dashboard
5. The Pet onboarding form should capture atleast pet name, species, breed, gender, and birth date, and microchip details
6. As a visitor, I should be able to search the microchip registry using a 15 digit microchip id
7. As a visitor, if I am able to find that the microchip is reisgered to the porta, I should get an option to register to the website
8. As a registered user of the website, once I search and find a microchip, I should be able to see a button to nudge the owner of that pet that I have found their pet
9. As a registered pet owner, I should be able to link one or more physical NFC/QR tags to each of my pets
10. Each tag should have a type (QR, NFC, or DUAL), a unique tag code, and optional metadata (serial number, manufacturer, label, notes)
11. For NFC tags, the system should capture the NFC UID and technology type (e.g. NTAG213, NTAG215, Mifare)
12. As a pet owner, I should be able to view all tags linked to my pet on the pet profile page
13. As a pet owner, I should be able to deactivate, reactivate, or remove a tag from my pet
14. When a physical QR/NFC tag is scanned by anyone, the system should resolve the tag code to the pet's public profile and log the scan event
15. The pet owner should be notified via email whenever one of their pet's tags is scanned
16. Deactivated or removed tags should no longer resolve to a pet profile when scanned
17. All tag lifecycle events (activation, deactivation, removal) should be recorded in the pet's audit trail
