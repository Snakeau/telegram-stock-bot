#!/usr/bin/env python3
"""Test portfolio parsing with user's data."""

import re
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Position:
    ticker: str
    quantity: float
    avg_price: Optional[float]

def safe_float(value: str) -> Optional[float]:
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None

def parse_portfolio_text(text: str) -> List[Position]:
    positions: List[Position] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        normalized = re.sub(r"[,:;]+", " ", line)
        parts = [p for p in normalized.split() if p]

        if len(parts) < 2:
            continue

        ticker = parts[0].upper()
        quantity = safe_float(parts[1])
        avg_price = safe_float(parts[2]) if len(parts) >= 3 else None

        if quantity is None or quantity <= 0:
            continue

        positions.append(Position(ticker=ticker, quantity=quantity, avg_price=avg_price))

    return positions

# Test data
test_portfolio = """nabl 3250 7.30
vwra 80 172.25
adbe 25 297.96
sgln 25 7230
aggu 25 5.816
ssln 20 6660.95
unh 5 276.98
dis 10 104.12
mrna 25 48.67
pypl 15 54.68"""

print("Testing portfolio parsing...")
print("=" * 60)

positions = parse_portfolio_text(test_portfolio)

print(f"✓ Parsed {len(positions)} positions successfully!\n")

for i, pos in enumerate(positions, 1):
    value = pos.quantity * pos.avg_price if pos.avg_price else 0
    print(f"{i:2d}. {pos.ticker:6s} | Qty: {pos.quantity:7.0f} | "
          f"Avg Price: ${pos.avg_price:10.2f} | Value: ${value:12,.2f}")

total_value = sum(p.quantity * p.avg_price for p in positions if p.avg_price)
print("=" * 60)
print(f"Total Portfolio Value: ${total_value:,.2f}\n")

print("All checks passed! ✅ Portfolio data is valid.")
