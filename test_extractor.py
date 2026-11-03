import asyncio
import sys
from extractor import extract_codes

async def run_simulation():
    sample_messages = [
        "Guys here is a new Binance Crypto Box! Code: BP88ZKL9 claim fast!!",
        "Red packet dropped: 7XQ12WAA (0.5 USDT)",
        "Check this discount voucher or password settings reminder",
        "Multiple codes: BP11AA22 and 99KK88ZZ available now",
        "Just chatting about BITCOINS and ETHEREUM without any code"
    ]

    print("=== Testing Extractor Logic ===")
    for idx, msg in enumerate(sample_messages, 1):
        found = extract_codes(msg)
        print(f"\nMessage {idx}: {msg}")
        print(f"Extracted Codes: {found}")

if __name__ == "__main__":
    asyncio.run(run_simulation())
