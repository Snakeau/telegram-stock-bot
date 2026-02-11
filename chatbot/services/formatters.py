"""Output formatters for portfolio scanner (pure functions)."""

from ..domain.models import PortfolioScanOutput


def format_scanner_output(scan_output: PortfolioScanOutput) -> str:
    """
    Format PortfolioScanOutput into displayable text.
    
    Args:
        scan_output: PortfolioScanOutput object
    
    Returns:
        Formatted text string
    """
    lines = ["📊 Portfolio Scanner", ""]
    
    for r in scan_output.results:
        if r.price == 0:
            lines.append(f"{r.emoji} {r.ticker}: n/a")
        else:
            day_str = f"{r.day_change:+.1f}%" if r.day_change != 0 else "0.0%"
            month_str = f"{r.month_change:+.1f}%" if r.month_change != 0 else "0.0%"
            mode_label = "FULL" if r.analysis_mode == "full" else "BASIC"
            lines.append(
                f"{r.emoji} {r.ticker}: ${r.price:.2f} | 5d: {day_str}, 1m: {month_str} | "
                f"{r.action} | Risk: {r.risk} | {mode_label}"
            )
    
    lines.append("")
    lines.append("Legend:")
    lines.append("💎 quality+price | 🟢 quality")
    lines.append("⏳ strong, but expensive | 🚀 growth without margin")
    lines.append("⚠️ overvalued price | 🔶 uncomfortable entry")
    lines.append("🔴 elevated risk | ⚪ mixed situation")
    lines.append("FULL: full review (top-3 by weight) | BASIC: basic mode")
    
    if scan_output.note:
        lines.append("")
        lines.append(scan_output.note)
    
    return "\n".join(lines)
