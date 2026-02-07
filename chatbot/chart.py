"""Portfolio NAV chart rendering."""

import io
import logging
from typing import List, Optional

import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")  # Non-GUI backend

logger = logging.getLogger(__name__)


def render_nav_chart(
    nav_data: List[tuple],
    title: str = "Portfolio NAV",
    figsize: tuple = (10, 6),
) -> Optional[bytes]:
    """
    Render portfolio NAV as PNG image.
    
    Args:
        nav_data: List of (date_str, value) tuples
        title: Chart title
        figsize: Figure size (width, height) in inches
        
    Returns:
        PNG bytes or None on error
    """
    if not nav_data or len(nav_data) < 2:
        logger.debug("Not enough NAV data points to render chart")
        return None
    
    try:
        dates = [item[0] for item in nav_data]
        values = [item[1] for item in nav_data]
        
        fig, ax = plt.subplots(figsize=figsize)
        ax.plot(dates, values, marker='o', linewidth=2, markersize=4, color='#1f77b4')
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Portfolio Value (USD)', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
        
        # Format y-axis as currency
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
        
        plt.tight_layout()
        
        # Convert to bytes
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        plt.close(fig)
        
        logger.debug("NAV chart rendered with %d data points", len(nav_data))
        return buf.getvalue()
        
    except Exception as exc:
        logger.error("Failed to render NAV chart: %s", exc)
        return None
