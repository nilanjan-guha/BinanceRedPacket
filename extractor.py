import re
from typing import List, Set

# Standard Binance Crypto Box format: exactly 8 uppercase alphanumeric characters
# Examples often look like BPXXXXXX or generic 8 chars e.g. 7U39XKL2, BPU9QW1Z
CRYPTOBOX_REGEX = re.compile(r'\b[A-Za-z0-9]{8}\b')

# Words to filter out common 8-character false positives in English/Crypto chat
EXCLUDED_WORDS: Set[str] = {
    "ETHEREUM", "BINANCEE", "TRANSFER", "AIRDROPS", "BITCOINS", 
    "WITHDRAW", "DEPOSITS", "DISCOUNT", "VOUCHERS", "TELEGRAM",
    "RECEIVED", "SENDINGS", "EXCHANGE", "CAMPAIGN", "PLATFORM",
    "REMINDER", "REGISTER", "SECURITY", "PASSWORD", "SETTINGS",
    "ACTIVITY", "OFFICIAL", "ANNOUNCE", "TOMORROW", "YESTERDAY"
}

def extract_codes(text: str) -> List[str]:
    """
    Extracts potential 8-character Binance Crypto Box codes from input text.
    Normalizes them to uppercase and discards common non-code dictionary words.
    """
    if not text:
        return []

    found = CRYPTOBOX_REGEX.findall(text)
    candidates = []

    for code in found:
        upper_code = code.upper()
        # Filter out obvious dictionary words
        if upper_code in EXCLUDED_WORDS:
            continue
        
        # Crypto Box codes almost always contain at least one digit (or starts with 'BP')
        # Pure alpha 8-letter English words (like CHATTING, MULTIPLE) are almost always false positives
        has_digit = any(c.isdigit() for c in upper_code)
        starts_with_bp = upper_code.startswith("BP")
        
        if not (has_digit or starts_with_bp):
            continue
            
        candidates.append(upper_code)

    return list(dict.fromkeys(candidates))  # Preserves order while deduplicating
