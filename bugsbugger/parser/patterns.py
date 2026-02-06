"""Regex patterns for natural language parsing."""

import re

# Amount patterns - match currency and numbers
AMOUNT_PATTERNS = [
    re.compile(r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', re.IGNORECASE),  # $1,500.00
    re.compile(r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:dollars?|usd)', re.IGNORECASE),  # 1500 dollars
    re.compile(r'(USD|CAD|EUR|GBP)\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', re.IGNORECASE),  # USD 1500
]

# Date patterns
DATE_PATTERNS = [
    # Relative dates
    re.compile(r'\bin\s+(\d+)\s+(minute|min|hour|day|week|month)s?', re.IGNORECASE),
    re.compile(r'\b(tomorrow|today)', re.IGNORECASE),
    re.compile(r'\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', re.IGNORECASE),

    # Specific dates
    re.compile(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([A-Za-z]+)', re.IGNORECASE),  # 15th March
    re.compile(r'\b([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?', re.IGNORECASE),  # March 15th
    re.compile(r'\b(\d{4})-(\d{2})-(\d{2})', re.IGNORECASE),  # 2026-03-15

    # Day of month
    re.compile(r'\b(?:on\s+)?(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)', re.IGNORECASE),  # 1st, 15th
]

# Due keyword patterns
DUE_PATTERNS = [
    re.compile(r'\bdue\s+', re.IGNORECASE),
    re.compile(r'\bby\s+', re.IGNORECASE),
    re.compile(r'\bon\s+', re.IGNORECASE),
]

# Recurrence patterns
RECURRENCE_PATTERNS = [
    # Simple patterns
    re.compile(r'\bevery\s+(day|week|month|year)', re.IGNORECASE),
    re.compile(r'\b(daily|weekly|monthly|yearly|annually)', re.IGNORECASE),

    # Every N units
    re.compile(r'\bevery\s+(\d+)\s+(day|week|month|year)s?', re.IGNORECASE),

    # Every weekday
    re.compile(r'\bevery\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', re.IGNORECASE),

    # Specific day of month
    re.compile(r'\bevery\s+(\d{1,2})(?:st|nd|rd|th)', re.IGNORECASE),  # every 1st
]

# Category keywords
CATEGORY_KEYWORDS = {
    'bills': ['bill', 'utility', 'utilities', 'electric', 'water', 'gas', 'rent', 'mortgage', 'insurance'],
    'subscriptions': ['subscription', 'netflix', 'spotify', 'hulu', 'disney', 'amazon prime', 'apple', 'gym'],
    'birthdays': ['birthday', 'anniversary', 'bday'],
    'goals': ['goal', 'deadline', 'project', 'assignment', 'task'],
    'business_leads': ['lead', 'follow up', 'followup', 'call', 'meeting', 'client'],
}

# Time patterns (for specific times)
TIME_PATTERNS = [
    re.compile(r'\bat\s+(\d{1,2}):(\d{2})\s*(am|pm)?', re.IGNORECASE),
    re.compile(r'\bat\s+(\d{1,2})\s*(am|pm)', re.IGNORECASE),
]

# Month names
MONTH_NAMES = {
    'january': 1, 'jan': 1,
    'february': 2, 'feb': 2,
    'march': 3, 'mar': 3,
    'april': 4, 'apr': 4,
    'may': 5,
    'june': 6, 'jun': 6,
    'july': 7, 'jul': 7,
    'august': 8, 'aug': 8,
    'september': 9, 'sep': 9, 'sept': 9,
    'october': 10, 'oct': 10,
    'november': 11, 'nov': 11,
    'december': 12, 'dec': 12,
}

# Weekday names
WEEKDAY_NAMES = {
    'monday': 0,
    'tuesday': 1,
    'wednesday': 2,
    'thursday': 3,
    'friday': 4,
    'saturday': 5,
    'sunday': 6,
}
