"""
Canonical DHB → NZHS health region mapping (2022 Health NZ restructure).

Shared by nzdep.py and boundaries.py to avoid duplication.
"""

DHB_TO_REGION = {
    "Northland": "Northern | Te Tai Tokerau",
    "Waitemata": "Northern | Te Tai Tokerau",
    "Auckland": "Northern | Te Tai Tokerau",
    "Counties Manukau": "Northern | Te Tai Tokerau",
    "Waikato": "Midland | Te Manawa Taki",
    "Lakes": "Midland | Te Manawa Taki",
    "Bay of Plenty": "Midland | Te Manawa Taki",
    "Tairawhiti": "Midland | Te Manawa Taki",
    "Tairāwhiti": "Midland | Te Manawa Taki",
    "Taranaki": "Midland | Te Manawa Taki",
    "Hawke's Bay": "Central | Te Ikaroa",
    "Hawkes Bay": "Central | Te Ikaroa",
    "Whanganui": "Central | Te Ikaroa",
    "MidCentral": "Central | Te Ikaroa",
    "Capital and Coast": "Central | Te Ikaroa",
    "Capital & Coast": "Central | Te Ikaroa",
    "Capital Coast": "Central | Te Ikaroa",
    "Hutt Valley": "Central | Te Ikaroa",
    "Wairarapa": "Central | Te Ikaroa",
    "Nelson Marlborough": "South Island | Te Waipounamu",
    "West Coast": "South Island | Te Waipounamu",
    "Canterbury": "South Island | Te Waipounamu",
    "South Canterbury": "South Island | Te Waipounamu",
    "Southern": "South Island | Te Waipounamu",
}
