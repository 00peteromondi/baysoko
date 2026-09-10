"""
Canonical definitions for Baysoko's seasonal marketing campaigns.

This mirrors the seasonal logic in templates/listings/home.html's
campaign countdown JS (kept in sync manually — the JS drives the
homepage banner's visuals/countdown, this module is the server-side
source of truth used to validate seller campaign enrollment and to
filter listings by campaign).
"""
from datetime import date, timedelta


CAMPAIGN_CHOICES = [
    ('backtoschool', 'Back to School Sale'),
    ('midyear', 'Mid Year Savings'),
    ('spring', 'Spring Deals'),
    ('blackfriday', 'Black Friday Blowout'),
    ('holiday', 'Holiday Specials'),
]

CAMPAIGN_LABELS = dict(CAMPAIGN_CHOICES)


def get_black_friday_window(year):
    """Black Friday is the day after the 4th Thursday of November.
    Returns (start_date, end_date) inclusive — Black Friday through
    the following Cyber Monday.
    """
    nov_1 = date(year, 11, 1)
    # weekday(): Monday=0 ... Sunday=6; Thursday=3
    days_to_first_thursday = (3 - nov_1.weekday()) % 7
    first_thursday = nov_1 + timedelta(days=days_to_first_thursday)
    fourth_thursday = first_thursday + timedelta(weeks=3)
    black_friday = fourth_thursday + timedelta(days=1)
    cyber_monday = black_friday + timedelta(days=3)
    return black_friday, cyber_monday


def get_current_campaign(today=None):
    """Returns the campaign slug that is active right now. Black Friday
    takes priority over the broader holiday season when it's within its
    own short window; otherwise falls back to the month-based seasons
    (matching getSeasonCampaignForMonth in home.html).
    """
    today = today or date.today()

    bf_start, bf_end = get_black_friday_window(today.year)
    if bf_start <= today <= bf_end:
        return 'blackfriday'

    month = today.month  # 1-indexed
    if month in (1, 2, 3):
        return 'backtoschool'
    if month in (4, 5, 6):
        return 'midyear'
    if month in (7, 8):
        return 'backtoschool'
    if month in (9, 10):
        return 'spring'
    return 'holiday'  # Nov, Dec (outside the Black Friday window)


def is_campaign_active(slug, today=None):
    """Whether the given campaign slug is the currently active one."""
    return slug == get_current_campaign(today)


def get_active_campaign_choice():
    """The (slug, label) pair for the currently active campaign, for
    rendering the single option a seller is allowed to enroll into."""
    slug = get_current_campaign()
    return slug, CAMPAIGN_LABELS.get(slug, slug)
