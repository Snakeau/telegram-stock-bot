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
    lines = ["📊 Портфельный сканер", ""]
    
    for r in scan_output.results:
        if r.price == 0:
            lines.append(f"{r.emoji} {r.ticker}: н/д")
        else:
            day_str = f"{r.day_change:+.1f}%" if r.day_change != 0 else "0.0%"
            month_str = f"{r.month_change:+.1f}%" if r.month_change != 0 else "0.0%"
            mode_label = "FULL" if r.analysis_mode == "full" else "BASIC"
            lines.append(
                f"{r.emoji} {r.ticker}: ${r.price:.2f} | 5д: {day_str}, 1м: {month_str} | "
                f"{r.action} | Риск: {r.risk} | {mode_label}"
            )
    
    lines.append("")
    lines.append("Легенда:")
    lines.append("💎 качество+цена | 🟢 качество")
    lines.append("⏳ сильный, но дорого | 🚀 рост без запаса")
    lines.append("⚠️ цена завышена | 🔶 некомфортный вход")
    lines.append("🔴 повышенный риск | ⚪ смешанная ситуация")
    lines.append("FULL: полный разбор (топ-3 по весу) | BASIC: базовый режим")
    
    if scan_output.note:
        lines.append("")
        lines.append(scan_output.note)
    
    return "\n".join(lines)
