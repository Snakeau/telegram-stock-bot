import asyncio
import json
import logging
import os
import re
import signal
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from tempfile import NamedTemporaryFile
from typing import Dict, List, Optional, Tuple, Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from xml.etree import ElementTree

import httpx

import matplotlib
matplotlib.use('Agg')  # Non-GUI backend for Render.com
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pandas_datareader.data as web
import requests
import yfinance as yf
from dotenv import load_dotenv
from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),  # For Render.com logs
    ]
)
logger = logging.getLogger(__name__)


# ============ CACHE SYSTEM ============
class SimpleCache:
    """Simple in-memory cache with TTL (time-to-live) support."""
    
    def __init__(self):
        self.cache: Dict[str, Tuple[Any, float]] = {}
    
    def get(self, key: str, ttl_seconds: int = 600) -> Optional[Any]:
        """Get cached value if it exists and is not expired."""
        if key not in self.cache:
            return None
        
        value, timestamp = self.cache[key]
        if time.time() - timestamp > ttl_seconds:
            del self.cache[key]
            return None
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """Store value in cache with current timestamp."""
        self.cache[key] = (value, time.time())
    
    def clear(self) -> None:
        """Clear all cache."""
        self.cache.clear()
    
    def cleanup(self, ttl_seconds: int = 600) -> int:
        """Remove expired items, return count of removed items."""
        now = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self.cache.items()
            if now - timestamp > ttl_seconds
        ]
        for key in expired_keys:
            del self.cache[key]
        return len(expired_keys)


# Global cache instances
market_data_cache = SimpleCache()
news_cache = SimpleCache()

# Cache TTL settings (in seconds)
MARKET_DATA_CACHE_TTL = int(os.getenv("MARKET_DATA_CACHE_TTL", "600"))  # 10 minutes
NEWS_CACHE_TTL = int(os.getenv("NEWS_CACHE_TTL", "1800"))  # 30 minutes

MENU_STOCK = "📈 Анализ акции"
MENU_PORTFOLIO = "💼 Анализ портфеля"
MENU_MY_PORTFOLIO = "📂 Мой портфель"
MENU_COMPARE = "🔄 Сравнение акций"
MENU_BUFFETT = "💎 Баффет Анализ"
MENU_SCANNER = "🔍 Портфельный Сканер"
MENU_HELP = "ℹ️ Помощь"
MENU_CANCEL = "❌ Отмена"

CHOOSING, WAITING_STOCK, WAITING_PORTFOLIO, WAITING_COMPARISON, WAITING_BUFFETT = range(5)

DB_PATH = os.getenv("PORTFOLIO_DB_PATH", "portfolio.db")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


@dataclass
class Position:
    ticker: str
    quantity: float
    avg_price: Optional[float]


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(MENU_STOCK), KeyboardButton(MENU_PORTFOLIO)],
            [KeyboardButton(MENU_MY_PORTFOLIO), KeyboardButton(MENU_COMPARE)],
            [KeyboardButton(MENU_BUFFETT), KeyboardButton(MENU_SCANNER)],
            [KeyboardButton(MENU_HELP), KeyboardButton(MENU_CANCEL)],
        ],
        resize_keyboard=True,
    )


def safe_float(value: str) -> Optional[float]:
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_portfolios (
                user_id INTEGER PRIMARY KEY,
                raw_text TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def save_portfolio(user_id: int, raw_text: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO user_portfolios(user_id, raw_text, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                raw_text=excluded.raw_text,
                updated_at=excluded.updated_at
            """,
            (user_id, raw_text, now),
        )
        conn.commit()


def get_saved_portfolio(user_id: int) -> Optional[str]:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT raw_text FROM user_portfolios WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row[0] if row else None


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


def load_data_from_stooq(ticker: str, period: str) -> Optional[pd.DataFrame]:
    """Загрузка данных из Stooq через pandas_datareader."""
    try:
        # Определяем даты на основе периода
        from datetime import datetime, timedelta
        end_date = datetime.now()
        period_days = {
            "1d": 1, "5d": 5, "1mo": 30, "3mo": 90,
            "6mo": 180, "1y": 365, "2y": 730, "5y": 1825, "max": 3650
        }
        days = period_days.get(period, 180)
        start_date = end_date - timedelta(days=days)
        
        logger.info("Trying to load %s from Stooq (fallback)", ticker)
        df = web.DataReader(ticker, 'stooq', start_date, end_date)
        
        if df.empty:
            return None
            
        # Stooq возвращает данные с другими названиями колонок, нужно привести к стандарту
        df.columns = [col.capitalize() for col in df.columns]
        
        # Сортируем по дате (Stooq может возвращать в обратном порядке)
        df = df.sort_index()
        
        if 'Close' in df.columns and len(df) >= 1:
            logger.info("Successfully loaded %d rows from Stooq for %s", len(df), ticker)
            return df.dropna()
        return None
    except Exception as exc:
        logger.warning("Stooq fallback failed for %s: %s", ticker, exc)
        return None


def load_data_from_sec_edgar(ticker: str) -> Optional[pd.DataFrame]:
    """Попытка загрузить данные из SEC EDGAR (работает только для US компаний)."""
    try:
        # SEC EDGAR Company Tickers API
        logger.info("Trying to get company info from SEC EDGAR for %s", ticker)
        
        # Получаем CIK (Central Index Key) компании
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; FinBot/1.0; +http://example.com/bot)',
            'Accept': 'application/json'
        }
        
        # Сначала получаем список компаний
        tickers_url = "https://www.sec.gov/files/company_tickers.json"
        response = requests.get(tickers_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None
            
        companies = response.json()
        cik = None
        
        # Ищем CIK для нашего тикера
        for company in companies.values():
            if company.get('ticker', '').upper() == ticker.upper():
                cik = str(company['cik_str']).zfill(10)
                break
        
        if not cik:
            logger.info("Ticker %s not found in SEC database (may be non-US)", ticker)
            return None
        
        # Получаем финансовые данные компании
        facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        response = requests.get(facts_url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return None
            
        logger.info("SEC EDGAR data available for %s (CIK: %s)", ticker, cik)
        # SEC EDGAR не предоставляет исторические цены, только фундаментальные данные
        # Поэтому возвращаем None и полагаемся на Stooq
        return None
        
    except Exception as exc:
        logger.warning("SEC EDGAR lookup failed for %s: %s", ticker, exc)
        return None


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = pd.Series(close).astype(float)
    delta = close.diff()
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = pd.Series(gain, index=close.index).rolling(period).mean()
    avg_loss = pd.Series(loss, index=close.index).rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def load_market_data(
    ticker: str, period: str, interval: str, min_rows: int = 1
) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    last_exc: Optional[Exception] = None
    rate_limited = False
    
    # Check cache first
    cache_key = f"{ticker}_{period}_{interval}"
    cached_data = market_data_cache.get(cache_key, MARKET_DATA_CACHE_TTL)
    if cached_data is not None:
        logger.info("Cache hit for %s (period=%s, interval=%s)", ticker, period, interval)
        return cached_data, None
    
    # Сначала пробуем yfinance
    for attempt in range(3):
        try:
            data = yf.download(
                ticker,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,
                threads=False,
            )
            if not data.empty and "Close" in data.columns and len(data.dropna()) >= min_rows:
                data = data.dropna().copy()
                market_data_cache.set(cache_key, data)
                return data, None
        except Exception as exc:
            last_exc = exc
            if "rate limit" in str(exc).lower() or "too many requests" in str(exc).lower():
                rate_limited = True
                break

        try:
            data = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
            if not data.empty and "Close" in data.columns and len(data.dropna()) >= min_rows:
                data = data.dropna().copy()
                market_data_cache.set(cache_key, data)
                return data, None
        except Exception as exc:
            last_exc = exc
            if "rate limit" in str(exc).lower() or "too many requests" in str(exc).lower():
                rate_limited = True
                break

        time.sleep(1.2 * (attempt + 1))

    # Если получили rate limit, пробуем альтернативные источники
    if rate_limited:
        logger.warning("Rate limit detected for %s, trying fallback sources", ticker)
        
        # Пробуем SEC EDGAR (в основном для проверки, что это US компания)
        sec_data = load_data_from_sec_edgar(ticker)
        
        # Пробуем Stooq
        stooq_data = load_data_from_stooq(ticker, period)
        if stooq_data is not None and "Close" in stooq_data.columns and len(stooq_data) >= min_rows:
            logger.info("Successfully loaded data from Stooq for %s", ticker)
            market_data_cache.set(cache_key, stooq_data)
            return stooq_data, None
        
        # Если ничего не помогло, возвращаем rate_limit
        logger.warning("All fallback sources failed for %s", ticker)
        return None, "rate_limit"

    if last_exc is not None:
        logger.warning("Cannot load market data for %s: %s", ticker, last_exc)
    return None, "not_found_or_no_data"


def stock_snapshot(ticker: str) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    data, reason = load_market_data(ticker, period="6mo", interval="1d", min_rows=30)
    if data is None or "Close" not in data.columns:
        return None, reason or "not_found_or_no_data"
    if isinstance(data["Close"], pd.DataFrame):
        data["Close"] = data["Close"].iloc[:, 0]
    data["SMA20"] = data["Close"].rolling(20).mean()
    data["SMA50"] = data["Close"].rolling(50).mean()
    data["RSI14"] = compute_rsi(data["Close"], 14)
    return data, None


def stock_analysis_text(ticker: str, df: pd.DataFrame) -> str:
    last = df.iloc[-1]
    prev = df.iloc[-2]

    close = float(last["Close"])
    daily_change = (close / float(prev["Close"]) - 1) * 100
    sma20 = float(last["SMA20"])
    sma50 = float(last["SMA50"])
    rsi = float(last["RSI14"])

    trend = "восходящий" if sma20 > sma50 else "нисходящий"

    signals = []
    if rsi > 70:
        signals.append("RSI выше 70: актив может быть перекуплен.")
    elif rsi < 30:
        signals.append("RSI ниже 30: актив может быть перепродан.")
    else:
        signals.append("RSI в нейтральной зоне.")

    if close > sma20 > sma50:
        signals.append("Цена выше SMA20 и SMA50: технически сильная динамика.")
    elif close < sma20 < sma50:
        signals.append("Цена ниже SMA20 и SMA50: технически слабая динамика.")
    else:
        signals.append("Сигналы смешанные: подтверждение тренда слабое.")

    risk_line = (
        "Идея: использовать лимиты риска и не принимать решение только по одному индикатору."
    )

    return (
        f"{ticker}\n"
        f"Цена: {close:.2f}\n"
        f"Изменение за день: {daily_change:+.2f}%\n"
        f"Тренд по SMA(20/50): {trend}\n"
        f"RSI(14): {rsi:.1f}\n\n"
        "Ключевые наблюдения:\n"
        f"- {signals[0]}\n"
        f"- {signals[1]}\n"
        f"- {risk_line}\n"
    )


def render_stock_chart(ticker: str, df: pd.DataFrame) -> str:
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(10, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )

    ax1.plot(df.index, df["Close"], label="Close", linewidth=1.8)
    ax1.plot(df.index, df["SMA20"], label="SMA20", linestyle="--", linewidth=1.2)
    ax1.plot(df.index, df["SMA50"], label="SMA50", linestyle="--", linewidth=1.2)
    ax1.set_title(f"{ticker}: цена и скользящие средние (6 месяцев)")
    ax1.grid(alpha=0.25)
    ax1.legend()

    ax2.plot(df.index, df["RSI14"], label="RSI14", color="purple", linewidth=1.2)
    ax2.axhline(70, color="red", linestyle="--", linewidth=0.8)
    ax2.axhline(30, color="green", linestyle="--", linewidth=0.8)
    ax2.set_ylim(0, 100)
    ax2.grid(alpha=0.25)
    ax2.legend()

    fig.tight_layout()
    with NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        fig.savefig(tmp.name, dpi=140)
        chart_path = tmp.name
    plt.close(fig)
    return chart_path


def compare_stocks(tickers: List[str], period: str = "6mo") -> tuple[Optional[str], Optional[str]]:
    """Compare multiple stocks: correlation, relative performance, chart."""
    if len(tickers) < 2:
        return None, "Нужно минимум 2 тикера для сравнения"
    
    if len(tickers) > 5:
        return None, "Максимум 5 тикеров для сравнения"
    
    # Load data for all tickers
    data_dict = {}
    failed_tickers = []
    
    for ticker in tickers:
        data, reason = load_market_data(ticker, period=period, interval="1d", min_rows=30)
        if data is None or data.empty or "Close" not in data.columns:
            failed_tickers.append(ticker)
            continue
        
        close_series = data["Close"]
        
        # Ensure we have a proper Series with enough data
        if not isinstance(close_series, pd.Series) or len(close_series) < 30:
            failed_tickers.append(ticker)
            continue
            
        data_dict[ticker] = close_series
    
    # Check if we have enough tickers
    if len(data_dict) < 2:
        if failed_tickers:
            return None, f"Не удалось загрузить данные для: {', '.join(failed_tickers)}"
        return None, "Недостаточно данных для сравнения"
    
    # Combine into single DataFrame and align dates
    try:
        prices_df = pd.DataFrame(data_dict).dropna()
    except Exception as e:
        logger.error(f"Error creating comparison DataFrame: {e}")
        return None, f"Ошибка при объединении данных: {str(e)}"
    
    if len(prices_df) < 30:
        return None, "Недостаточно данных для сравнения (нужно минимум 30 дней)"
    
    # Get list of successfully loaded tickers
    successful_tickers = list(prices_df.columns)
    
    # Calculate returns
    returns = prices_df.pct_change().dropna()
    
    # Correlation matrix
    corr_matrix = returns.corr()
    
    # Normalize prices to 100 at start (relative performance)
    normalized = (prices_df / prices_df.iloc[0]) * 100
    
    # Calculate statistics
    total_return = {}
    volatility = {}
    for ticker in successful_tickers:
        total_return[ticker] = ((prices_df[ticker].iloc[-1] / prices_df[ticker].iloc[0]) - 1) * 100
        volatility[ticker] = returns[ticker].std() * np.sqrt(252) * 100  # Annualized
    
    # Create comparison chart
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [2, 1]})
    
    # Plot normalized prices
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    for i, ticker in enumerate(successful_tickers):
        ax1.plot(normalized.index, normalized[ticker], label=ticker, 
                linewidth=2, color=colors[i % len(colors)])
    
    ax1.set_title("Относительная динамика акций (нормализовано к 100)", fontsize=14, fontweight='bold')
    ax1.set_ylabel("Индекс (старт = 100)")
    ax1.grid(alpha=0.3)
    ax1.legend(loc='best')
    ax1.axhline(100, color='gray', linestyle='--', linewidth=0.8, alpha=0.5)
    
    # Plot correlation heatmap
    im = ax2.imshow(corr_matrix, cmap='RdYlGn', vmin=-1, vmax=1, aspect='auto')
    ax2.set_xticks(range(len(successful_tickers)))
    ax2.set_yticks(range(len(successful_tickers)))
    ax2.set_xticklabels(successful_tickers)
    ax2.set_yticklabels(successful_tickers)
    ax2.set_title("Корреляция доходностей", fontsize=12)
    
    # Add correlation values
    for i in range(len(successful_tickers)):
        for j in range(len(successful_tickers)):
            text = ax2.text(j, i, f'{corr_matrix.iloc[i, j]:.2f}',
                           ha="center", va="center", color="black", fontsize=9)
    
    fig.colorbar(im, ax=ax2, label='Корреляция')
    fig.tight_layout()
    
    with NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        fig.savefig(tmp.name, dpi=140)
        chart_path = tmp.name
    plt.close(fig)
    
    # Generate text summary
    lines = ["📊 Сравнительный анализ акций\n"]
    
    if failed_tickers:
        lines.append(f"⚠️ Не удалось загрузить: {', '.join(failed_tickers)}\n")
    
    lines.append(f"Период: {period}, точек данных: {len(prices_df)}\n")
    
    lines.append("Результаты:")
    sorted_by_return = sorted(total_return.items(), key=lambda x: x[1], reverse=True)
    for ticker, ret in sorted_by_return:
        vol = volatility[ticker]
        lines.append(f"- {ticker}: доходность {ret:+.2f}%, волатильность {vol:.1f}%")
    
    lines.append("\nКорреляция (наиболее интересные пары):")
    corr_pairs = []
    for i in range(len(successful_tickers)):
        for j in range(i+1, len(successful_tickers)):
            corr_pairs.append((successful_tickers[i], successful_tickers[j], corr_matrix.iloc[i, j]))
    
    corr_pairs = sorted(corr_pairs, key=lambda x: abs(x[2]), reverse=True)
    for t1, t2, corr in corr_pairs[:3]:
        lines.append(f"- {t1} ↔ {t2}: {corr:.2f}")
    
    lines.append("\nВыводы:")
    if max(abs(c[2]) for c in corr_pairs) > 0.7:
        lines.append("- Высокая корреляция: акции движутся похоже (диверсификация низкая)")
    elif max(abs(c[2]) for c in corr_pairs) < 0.3:
        lines.append("- Низкая корреляция: хорошая диверсификация портфеля")
    
    best_ticker = sorted_by_return[0][0]
    worst_ticker = sorted_by_return[-1][0]
    lines.append(f"- Лидер: {best_ticker} (+{sorted_by_return[0][1]:.1f}%)")
    lines.append(f"- Аутсайдер: {worst_ticker} ({sorted_by_return[-1][1]:+.1f}%)")
    
    lines.append("\nНе является индивидуальной инвестиционной рекомендацией.")
    
    return chart_path, "\n".join(lines)


def ticker_news(ticker: str, limit: int = 5) -> List[Dict[str, str]]:
    # Check cache first
    cache_key = f"news_{ticker}_{limit}"
    cached_news = news_cache.get(cache_key, NEWS_CACHE_TTL)
    if cached_news is not None:
        logger.info("Cache hit for news: %s", ticker)
        return cached_news
    
    try:
        raw_news = yf.Ticker(ticker).news or []
    except Exception as exc:
        logger.warning("Cannot load news for %s: %s", ticker, exc)
        raw_news = []

    items: List[Dict[str, str]] = []
    for item in raw_news:
        parsed = _parse_yf_news_item(item)
        if parsed:
            items.append(parsed)
        if len(items) >= limit:
            break

    if len(items) < limit:
        for item in yahoo_rss_news(ticker, limit=limit * 2):
            if not _is_duplicate_news(items, item):
                items.append(item)
            if len(items) >= limit:
                break

    result = items[:limit]
    news_cache.set(cache_key, result)
    return result


def _parse_yf_news_item(item: Dict) -> Optional[Dict[str, str]]:
    content = item.get("content") if isinstance(item.get("content"), dict) else {}
    canonical = content.get("canonicalUrl") if isinstance(content.get("canonicalUrl"), dict) else {}
    clickthrough = item.get("clickThroughUrl") if isinstance(item.get("clickThroughUrl"), dict) else {}
    provider = content.get("provider") if isinstance(content.get("provider"), dict) else {}

    title = (
        item.get("title")
        or content.get("title")
        or content.get("description")
        or "Без заголовка"
    )
    publisher = item.get("publisher") or provider.get("displayName") or "Источник"
    link = (
        item.get("link")
        or canonical.get("url")
        or clickthrough.get("url")
        or ""
    )

    date = ""
    ts = item.get("providerPublishTime")
    if isinstance(ts, (int, float)):
        date = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
    elif isinstance(content.get("pubDate"), str):
        raw = content["pubDate"].replace("Z", "+00:00")
        try:
            date = datetime.fromisoformat(raw).strftime("%Y-%m-%d")
        except ValueError:
            date = content["pubDate"][:10]

    if not title and not link:
        return None
    return {"title": title, "publisher": publisher, "date": date, "link": link}


def _is_duplicate_news(existing: List[Dict[str, str]], candidate: Dict[str, str]) -> bool:
    c_title = candidate.get("title", "").strip().lower()
    c_link = candidate.get("link", "").strip().lower()
    for item in existing:
        title_match = c_title and item.get("title", "").strip().lower() == c_title
        link_match = c_link and item.get("link", "").strip().lower() == c_link
        if title_match or link_match:
            return True
    return False


def yahoo_rss_news(ticker: str, limit: int = 5) -> List[Dict[str, str]]:
    url = (
        "https://feeds.finance.yahoo.com/rss/2.0/headline"
        f"?s={quote_plus(ticker)}&region=US&lang=en-US"
    )
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
        },
        method="GET",
    )
    try:
        with urlopen(req, timeout=12) as resp:
            payload = resp.read()
        root = ElementTree.fromstring(payload)
    except Exception as exc:
        logger.warning("RSS news fallback failed for %s: %s", ticker, exc)
        return []

    items: List[Dict[str, str]] = []
    for node in root.findall("./channel/item"):
        title = (node.findtext("title") or "").strip() or "Без заголовка"
        link = (node.findtext("link") or "").strip()
        pub = (node.findtext("pubDate") or "").strip()
        date = ""
        if pub:
            try:
                date = datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %z").strftime("%Y-%m-%d")
            except ValueError:
                date = pub[:16]
        item = {"title": title, "publisher": "Yahoo Finance", "date": date, "link": link}
        items.append(item)
        if len(items) >= limit:
            break

    return items


def fallback_news_summary(news: List[Dict[str, str]]) -> str:
    if not news:
        return "AI-обзор новостей: данных мало, анализ по новостям недоступен."

    lines = ["AI-обзор новостей (базовый):"]
    for item in news[:3]:
        source = f"{item['publisher']} {item['date']}".strip()
        lines.append(f"- {item['title']} ({source})")

    lines.append("Вывод: проверь, как эти события влияют на выручку, маржу и прогноз компании.")
    return "\n".join(lines)


def ai_news_analysis(ticker: str, tech_summary: str, news: List[Dict[str, str]]) -> str:
    if not news:
        return "AI-обзор новостей: по этому тикеру не нашлось свежих материалов."

    if not OPENAI_API_KEY:
        return fallback_news_summary(news)

    news_block = "\n".join(
        [
            f"{idx + 1}. {n['title']} | {n['publisher']} | {n['date']} | {n['link']}"
            for idx, n in enumerate(news[:5])
        ]
    )

    system_prompt = (
        "Ты финансовый аналитик. Дай краткий и осторожный обзор без категоричных советов. "
        "Структура: 1) Что важно в новостях, 2) Возможное влияние на акцию, 3) Риски, "
        "4) Что проверить инвестору. Пиши по-русски, до 1200 символов."
    )
    user_prompt = (
        f"Тикер: {ticker}\n\n"
        f"Техсводка:\n{tech_summary}\n\n"
        f"Новости:\n{news_block}\n\n"
        "Сделай краткий AI-обзор."
    )

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }

    req = Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=25) as resp:
            parsed = json.loads(resp.read().decode("utf-8"))
        content = parsed["choices"][0]["message"]["content"].strip()
        return f"AI-обзор новостей:\n{content}"
    except (HTTPError, URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.warning("OpenAI news analysis failed for %s: %s", ticker, exc)
        return fallback_news_summary(news)


def compute_portfolio_risk(rows: List[Dict[str, float]], total_value: float) -> Dict[str, Optional[float]]:
    tickers = [r["ticker"] for r in rows]
    closes: Dict[str, pd.Series] = {}

    for t in tickers:
        data, _ = load_market_data(t, period="1y", interval="1d", min_rows=30)
        if data is None or "Close" not in data.columns:
            continue
        closes[t] = data["Close"].dropna()

    if len(closes) < 1:
        return {"vol_ann": None, "beta": None, "var_95_usd": None, "var_95_pct": None}

    price_df = pd.DataFrame(closes).dropna(how="any")
    if len(price_df) < 30:
        return {"vol_ann": None, "beta": None, "var_95_usd": None, "var_95_pct": None}

    returns = price_df.pct_change().dropna()
    valid_tickers = [t for t in tickers if t in returns.columns]
    if not valid_tickers:
        return {"vol_ann": None, "beta": None, "var_95_usd": None, "var_95_pct": None}

    weights_map = {
        r["ticker"]: (r["value"] / total_value) if total_value > 0 else 0.0
        for r in rows
        if r["ticker"] in valid_tickers
    }
    weight_sum = sum(weights_map.values())
    if weight_sum <= 0:
        return {"vol_ann": None, "beta": None, "var_95_usd": None, "var_95_pct": None}

    normalized_weights = {k: v / weight_sum for k, v in weights_map.items()}
    w = np.array([normalized_weights[t] for t in valid_tickers])

    port_returns = returns[valid_tickers].dot(w)
    if port_returns.empty:
        return {"vol_ann": None, "beta": None, "var_95_usd": None, "var_95_pct": None}

    vol_ann = float(port_returns.std(ddof=1) * np.sqrt(252) * 100)
    var_95_pct = float(max(0.0, -np.percentile(port_returns, 5) * 100))
    var_95_usd = float(total_value * var_95_pct / 100)

    beta = None
    try:
        spy, _ = load_market_data("SPY", period="1y", interval="1d", min_rows=30)
        if spy is not None and "Close" in spy.columns:
            mkt = spy["Close"].pct_change().dropna().rename("mkt")
            aligned = pd.concat([port_returns.rename("port"), mkt], axis=1).dropna()
            if len(aligned) > 20 and aligned["mkt"].var(ddof=1) > 0:
                cov = aligned[["port", "mkt"]].cov().loc["port", "mkt"]
                beta = float(cov / aligned["mkt"].var(ddof=1))
    except Exception as exc:
        logger.warning("Cannot compute beta: %s", exc)

    return {
        "vol_ann": vol_ann,
        "beta": beta,
        "var_95_usd": var_95_usd,
        "var_95_pct": var_95_pct,
    }


def analyze_portfolio(positions: List[Position]) -> str:
    rows = []
    for p in positions:
        data, _ = load_market_data(p.ticker, period="7d", interval="1d", min_rows=2)
        if data is None or "Close" not in data.columns:
            continue

        close_col = data["Close"]
        if isinstance(close_col, pd.DataFrame):
            close_col = close_col.iloc[:, 0]
        current_price = float(close_col.dropna().iloc[-1])
        market_value = current_price * p.quantity

        pnl_abs = None
        pnl_pct = None
        if p.avg_price and p.avg_price > 0:
            pnl_abs = (current_price - p.avg_price) * p.quantity
            pnl_pct = ((current_price / p.avg_price) - 1) * 100

        rows.append(
            {
                "ticker": p.ticker,
                "qty": p.quantity,
                "avg": p.avg_price,
                "price": current_price,
                "value": market_value,
                "pnl_abs": pnl_abs,
                "pnl_pct": pnl_pct,
            }
        )

    if not rows:
        return (
            "Не удалось получить данные по портфелю. Проверь формат и тикеры.\n"
            "Пример: AAPL 5 170"
        )

    total_value = sum(r["value"] for r in rows)
    risk = compute_portfolio_risk(rows, total_value)

    lines = ["Анализ портфеля", f"Текущая оценка: {total_value:,.2f}", ""]

    for r in sorted(rows, key=lambda x: x["value"], reverse=True):
        weight = (r["value"] / total_value) * 100 if total_value > 0 else 0
        if r["pnl_abs"] is None:
            pnl_line = "PnL: n/a"
        else:
            pnl_line = f"PnL: {r['pnl_abs']:+.2f} ({r['pnl_pct']:+.2f}%)"

        lines.append(
            f"- {r['ticker']}: qty {r['qty']}, price {r['price']:.2f}, value {r['value']:.2f} ({weight:.1f}%), {pnl_line}"
        )

    lines.append("")
    lines.append("Риск-метрики (1Y):")
    if risk["vol_ann"] is None:
        lines.append("- Недостаточно данных для расчета риска.")
    else:
        lines.append(f"- Годовая волатильность: {risk['vol_ann']:.2f}%")
        lines.append(
            f"- Исторический VaR 95% (1 день): {risk['var_95_pct']:.2f}% (~{risk['var_95_usd']:.2f})"
        )
        if risk["beta"] is None:
            lines.append("- Бета к SPY: n/a")
        else:
            lines.append(f"- Бета к SPY: {risk['beta']:.2f}")

    top_weight = max((r["value"] / total_value) * 100 for r in rows)
    lines.append("")
    lines.append("Что можно улучшить:")
    if top_weight > 40:
        lines.append("- Концентрация высокая: одна позиция >40%. Рассмотреть диверсификацию.")
    else:
        lines.append("- Концентрация умеренная: структура близка к более устойчивой.")

    if risk["vol_ann"] is not None and risk["vol_ann"] > 35:
        lines.append("- Волатильность высокая: сократить долю самых рискованных бумаг или добавить защитные активы.")

    if risk["beta"] is not None and risk["beta"] > 1.2:
        lines.append("- Бета выше рынка: портфель сильнее реагирует на падения индекса.")

    losers = [r for r in rows if r["pnl_pct"] is not None and r["pnl_pct"] < -10]
    if losers:
        lines.append("- Есть позиции с просадкой >10%: полезно пересмотреть инвестиционный тезис.")

    gainers = [r for r in rows if r["pnl_pct"] is not None and r["pnl_pct"] > 25]
    if gainers:
        lines.append("- Есть лидеры >25%: можно частично фиксировать и ребалансировать доли.")

    lines.append("")
    lines.append("Не является индивидуальной инвестиционной рекомендацией.")

    return "\n".join(lines)


# ============ BUFFETT ANALYSIS SYSTEM ============

async def get_price_history_stooq(ticker: str) -> Optional[pd.DataFrame]:
    """Загрузка исторических данных цен из Stooq API."""
    try:
        url = "https://stooq.com/q/d/l/"
        params = {"s": f"{ticker.upper()}.US", "i": "d"}
        
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            
            # Парсим CSV
            df = pd.read_csv(StringIO(response.text))
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date', ascending=True).reset_index(drop=True)
            
            if len(df) < 1 or 'Close' not in df.columns:
                return None
            
            logger.info("Loaded %d rows from Stooq for %s", len(df), ticker)
            return df
    except Exception as exc:
        logger.warning("Stooq API failed for %s: %s", ticker, exc)
        return None


async def get_cik_from_ticker(ticker: str) -> Optional[str]:
    """Получение CIK (Central Index Key) по тикеру из SEC EDGAR."""
    try:
        url = "https://www.sec.gov/files/company_tickers.json"
        headers = {"User-Agent": "InvestCheck/1.0 (contact@example.com)"}
        
        async with httpx.AsyncClient(timeout=30, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Ищем тикер в данных
            for entry in data.values():
                if entry.get('ticker', '').upper() == ticker.upper():
                    cik = str(entry.get('cik_str'))
                    logger.info("Found CIK %s for ticker %s", cik, ticker)
                    return cik
            
            logger.warning("No CIK found for ticker %s in SEC database", ticker)
            return None
    except httpx.HTTPStatusError as exc:
        logger.warning("HTTP error getting CIK for %s: %s", ticker, exc)
        return None
    except Exception as exc:
        logger.warning("Failed to get CIK for %s: %s", ticker, exc)
        return None


async def get_company_facts(cik: str) -> Optional[dict]:
    """Получение фундаментальных данных компании из SEC EDGAR."""
    try:
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json"
        headers = {"User-Agent": "InvestCheck/1.0 (contact@example.com)"}
        
        # Retry logic для SEC API
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=30, headers=headers) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    data = response.json()
                    logger.info("Successfully fetched company facts for CIK %s", cik)
                    return data
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    logger.warning("No company facts found for CIK %s (404)", cik)
                    return None
                elif attempt == 0:
                    logger.warning("HTTP error on attempt %d for CIK %s: %s, retrying...", attempt + 1, cik, exc)
                    await asyncio.sleep(1)
                else:
                    logger.warning("HTTP error on final attempt for CIK %s: %s", cik, exc)
                    return None
            except Exception as exc:
                if attempt == 0:
                    logger.warning("Error on attempt %d for CIK %s: %s, retrying...", attempt + 1, cik, exc)
                    await asyncio.sleep(1)
                else:
                    logger.warning("Failed to get company facts for CIK %s: %s", cik, exc)
                    return None
        
        return None
    except Exception as exc:
        logger.warning("Unexpected error getting company facts for CIK %s: %s", cik, exc)
        return None


def extract_fundamental_data(facts: dict) -> dict:
    """Извлечение фундаментальных метрик из SEC EDGAR данных."""
    fundamentals = {}
    
    if not facts or 'facts' not in facts:
        logger.warning("No facts data in response")
        return fundamentals
    
    us_gaap = facts['facts'].get('us-gaap', {})
    
    if not us_gaap:
        logger.warning("No us-gaap data found in facts")
        return fundamentals
    
    # Определяем теги для извлечения (с расширенным списком альтернатив)
    tags_map = {
        'revenue': [
            'Revenues', 
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'SalesRevenueNet',
            'RevenueFromContractWithCustomerIncludingAssessedTax'
        ],
        'operating_cash_flow': [
            'NetCashProvidedByUsedInOperatingActivities',
            'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'
        ],
        'capex': [
            'PaymentsToAcquirePropertyPlantAndEquipment',
            'PaymentsForCapitalImprovements', 
            'PaymentsToAcquireProductiveAssets'
        ],
        'cash': [
            'CashAndCashEquivalentsAtCarryingValue',
            'Cash',
            'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents'
        ],
        'debt': [
            'LongTermDebt',
            'DebtCurrent',
            'LongTermDebtAndCapitalLeaseObligations'
        ],
        'shares_outstanding': [
            'CommonStockSharesOutstanding',
            'WeightedAverageNumberOfSharesOutstandingBasic',
            'CommonStockSharesIssued'
        ]
    }
    
    for metric, possible_tags in tags_map.items():
        for tag in possible_tags:
            if tag in us_gaap:
                # Извлекаем данные только для 10-K (annual reports)
                units = us_gaap[tag].get('units', {})
                
                # Для revenue, capex, operating_cash_flow используем USD
                # Для shares используем shares
                if metric == 'shares_outstanding':
                    unit_key = 'shares'
                else:
                    unit_key = 'USD'
                
                if unit_key in units:
                    # Фильтруем только 10-K формы
                    annual_data = [
                        item for item in units[unit_key]
                        if item.get('form') in ['10-K', '10-K/A'] and item.get('fy')
                    ]
                    
                    if not annual_data:
                        logger.debug("No 10-K data found for %s using tag %s", metric, tag)
                        continue
                    
                    # Сортируем по fiscal year (от новых к старым)
                    annual_data.sort(key=lambda x: (x.get('fy', 0), x.get('filed', '')), reverse=True)
                    
                    # Убираем дубликаты по fiscal year (берем самый свежий filing)
                    seen_years = set()
                    unique_data = []
                    for item in annual_data:
                        fy = item.get('fy')
                        if fy and fy not in seen_years:
                            seen_years.add(fy)
                            unique_data.append({
                                'year': fy,
                                'value': item.get('val'),
                                'filed': item.get('filed')
                            })
                    
                    if unique_data:
                        fundamentals[metric] = unique_data
                        logger.info("Extracted %s: %d years of data using tag %s", metric, len(unique_data), tag)
                        break
    
    logger.info("Total metrics extracted: %d", len(fundamentals))
    return fundamentals


def calculate_technical_metrics(price_history: pd.DataFrame) -> dict:
    """Расчет технических метрик из ценовых данных."""
    metrics = {}
    
    if len(price_history) < 1:
        return metrics
    
    # Текущая цена
    metrics['current_price'] = price_history.iloc[-1]['Close']
    
    # Изменение за 5 дней
    if len(price_history) >= 6:
        price_5d_ago = price_history.iloc[-6]['Close']
        metrics['change_5d_pct'] = ((metrics['current_price'] - price_5d_ago) / price_5d_ago) * 100
        
        if metrics['change_5d_pct'] >= 1.0:
            metrics['arrow_5d'] = "↑"
        elif metrics['change_5d_pct'] <= -1.0:
            metrics['arrow_5d'] = "↓"
        else:
            metrics['arrow_5d'] = "→"
    else:
        metrics['change_5d_pct'] = 0
        metrics['arrow_5d'] = "→"
    
    # Изменение за 1 месяц
    if len(price_history) >= 21:
        price_1m_ago = price_history.iloc[-21]['Close']
        metrics['change_1m_pct'] = ((metrics['current_price'] - price_1m_ago) / price_1m_ago) * 100
    else:
        metrics['change_1m_pct'] = None
    
    # SMA 200
    if len(price_history) >= 200:
        metrics['sma_200'] = price_history['Close'].tail(200).mean()
    else:
        metrics['sma_200'] = None
    
    # Maximum Drawdown
    running_max = price_history['Close'].expanding().max()
    drawdown = ((price_history['Close'] - running_max) / running_max) * 100
    metrics['max_drawdown'] = abs(drawdown.min())
    
    return metrics


def calculate_trend_score(current_price: float, sma_200: Optional[float], price_history: pd.DataFrame) -> float:
    """Расчет Trend Score (0-10)."""
    if sma_200 is not None:
        price_vs_sma = ((current_price - sma_200) / sma_200) * 100
        
        if price_vs_sma > 20:
            return 9.0
        elif price_vs_sma > 10:
            return 8.0
        elif price_vs_sma > 5:
            return 7.0
        elif price_vs_sma > 0:
            return 6.0
        elif price_vs_sma > -5:
            return 5.0
        elif price_vs_sma > -10:
            return 4.0
        elif price_vs_sma > -20:
            return 3.0
        else:
            return 2.0
    
    # Fallback: 6-месячный тренд
    if len(price_history) >= 126:
        price_6m_ago = price_history.iloc[-126]['Close']
        change_6m = ((current_price - price_6m_ago) / price_6m_ago) * 100
        
        if change_6m > 30:
            return 8.0
        elif change_6m > 15:
            return 7.0
        elif change_6m > 0:
            return 6.0
        elif change_6m > -15:
            return 4.0
        else:
            return 3.0
    
    return 5.0


def calculate_momentum_score(change_5d_pct: float, change_1m_pct: Optional[float] = None) -> float:
    """Расчет Momentum Score (0-10)."""
    score = 5.0
    
    # Моментум за 5 дней
    if change_5d_pct > 5:
        score += 3
    elif change_5d_pct > 2:
        score += 2
    elif change_5d_pct > 0:
        score += 1
    elif change_5d_pct < -5:
        score -= 3
    elif change_5d_pct < -2:
        score -= 2
    elif change_5d_pct < 0:
        score -= 1
    
    # Моментум за 1 месяц
    if change_1m_pct is not None:
        if change_1m_pct > 10:
            score += 1
        elif change_1m_pct < -10:
            score -= 1
    
    return max(0.0, min(10.0, score))


def calculate_risk_score(max_drawdown: Optional[float]) -> float:
    """Расчет Risk Score (0-10)."""
    if max_drawdown is None:
        return 5.0
    
    if max_drawdown < 10:
        return 9.0
    elif max_drawdown < 20:
        return 8.0
    elif max_drawdown < 30:
        return 7.0
    elif max_drawdown < 40:
        return 6.0
    elif max_drawdown < 50:
        return 5.0
    elif max_drawdown < 60:
        return 4.0
    elif max_drawdown < 70:
        return 3.0
    else:
        return 2.0


def calculate_overall_score(trend_score: float, momentum_score: float, risk_score: float) -> float:
    """Расчет Overall Score (1-10)."""
    overall = trend_score * 0.4 + momentum_score * 0.3 + risk_score * 0.3
    return round(max(1.0, min(10.0, overall)), 1)


def determine_market_picture(current_price: float, sma_200: Optional[float], 
                            change_5d_pct: float, price_history: pd.DataFrame) -> str:
    """Определение рыночной картины."""
    is_uptrend = False
    is_downtrend = False
    
    if sma_200 is not None:
        price_vs_sma = ((current_price - sma_200) / sma_200) * 100
        is_uptrend = price_vs_sma > 5
        is_downtrend = price_vs_sma < -5
    else:
        if len(price_history) >= 126:
            price_6m_ago = price_history.iloc[-126]['Close']
            change_6m = ((current_price - price_6m_ago) / price_6m_ago) * 100
            is_uptrend = change_6m > 10
            is_downtrend = change_6m < -10
    
    if is_uptrend and change_5d_pct > 0:
        return "🟢 Стабильный рост"
    elif is_uptrend and change_5d_pct < 0:
        return "🟢 Восстановление идёт, но с волатильностью"
    elif is_downtrend:
        return "🔴 Устойчивое снижение"
    else:
        return "⚪ Боковик, рынок сомневается"


def determine_action(market_picture: str, overall_score: float) -> str:
    """Определение рекомендуемого действия."""
    is_downtrend = "🔴" in market_picture
    is_sideways = "⚪" in market_picture
    is_uptrend = "🟢" in market_picture
    
    if is_downtrend:
        return "ВЫХОДИТЬ"
    elif is_sideways:
        return "ДЕРЖАТЬ / НАБЛЮДАТЬ"
    elif is_uptrend and overall_score >= 7.0:
        return "ДЕРЖАТЬ / ДОКУПАТЬ НА ПРОСАДКАХ"
    else:
        return "ДЕРЖАТЬ / ЖДАТЬ ПРОСАДКУ"


def determine_risk_level(max_drawdown: Optional[float]) -> str:
    """Определение уровня риска."""
    if max_drawdown is None:
        return "Средний"
    
    if max_drawdown > 50:
        return "Средний–высокий"
    else:
        return "Средний"


def calculate_fcf(fundamentals: dict) -> tuple[Optional[float], str]:
    """Расчет Free Cash Flow."""
    cfo_data = fundamentals.get('operating_cash_flow', [])
    capex_data = fundamentals.get('capex', [])
    
    if not cfo_data or not capex_data:
        return None, "unknown"
    
    latest_cfo = cfo_data[0]['value']
    latest_capex = abs(capex_data[0]['value'])
    
    fcf = latest_cfo - latest_capex
    
    if fcf > 0:
        return fcf, "положительный"
    elif fcf < 0:
        return fcf, "отрицательный"
    else:
        return fcf, "нестабильный/unknown"


def calculate_dilution_level(fundamentals: dict) -> str:
    """Расчет уровня размытия акционеров."""
    shares_data = fundamentals.get('shares_outstanding', [])
    
    if len(shares_data) < 2:
        return "unknown"
    
    latest_shares = shares_data[0]['value']
    prev_shares = shares_data[1]['value']
    
    dilution_pct = ((latest_shares - prev_shares) / prev_shares) * 100
    
    if dilution_pct < 2:
        return "низкое"
    elif dilution_pct <= 6:
        return "умеренное"
    else:
        return "высокое"


def calculate_revenue_growth(fundamentals: dict) -> float:
    """Расчет роста выручки (CAGR)."""
    revenue_data = fundamentals.get('revenue', [])
    
    if len(revenue_data) < 2:
        return 0
    
    latest_rev = revenue_data[0]['value']
    
    # Пытаемся получить данные за 3 года назад
    if len(revenue_data) >= 4:
        old_rev = revenue_data[3]['value']
        years = 3
    else:
        old_rev = revenue_data[-1]['value']
        years = len(revenue_data) - 1
    
    if years > 0 and old_rev > 0:
        growth_rate = (((latest_rev / old_rev) ** (1 / years)) - 1) * 100
    else:
        growth_rate = 0
    
    return growth_rate


def determine_buffett_tag(fcf: Optional[float], cash_flow_status: str, 
                         dilution_level: str, market_picture: str) -> tuple[str, str]:
    """Определение тега Баффета."""
    # Проверка доступности данных
    no_data = "н/д" in cash_flow_status or dilution_level == "н/д"
    
    if no_data:
        # Если нет фундаментальных данных, оценка только по тренду
        is_uptrend = "🟢" in market_picture
        is_downtrend = "🔴" in market_picture
        
        if is_downtrend:
            return "Risky", "нисходящий тренд без возможности оценить фундамент"
        elif is_uptrend:
            return "OK", "восходящий тренд, но фундамент неизвестен (нет SEC данных)"
        else:
            return "OK", "боковое движение, фундамент неизвестен (нужны SEC данные)"
    
    # Стандартная логика с данными
    is_fcf_positive = cash_flow_status == "положительный"
    is_dilution_high = dilution_level == "высокое"
    is_uptrend_strong = "🟢" in market_picture
    is_dilution_moderate = dilution_level == "умеренное"
    
    # RISKY
    if not is_fcf_positive or is_dilution_high:
        if not is_fcf_positive:
            explanation = "отрицательный свободный денежный поток или высокая дилюция акционеров"
        else:
            explanation = "высокая дилюция акционеров ослабляет качество бизнеса"
        return "Risky", explanation
    
    # EXPENSIVE
    if is_fcf_positive and is_uptrend_strong and (is_dilution_moderate or is_dilution_high):
        explanation = "бизнес генерирует кэш, но цена может быть завышена из-за роста"
        return "Expensive", explanation
    
    # OK
    if is_fcf_positive and not is_dilution_high:
        explanation = "стабильный кэш-поток, умеренная дилюция, качество есть"
        return "OK", explanation
    
    explanation = "приемлемое качество бизнеса, но требует внимания"
    return "OK", explanation


def determine_lynch_tag(revenue_growth_rate: float, buffett_tag: str, has_revenue_data: bool = True) -> tuple[str, str]:
    """Определение тега Линча."""
    is_risky = buffett_tag == "Risky"
    
    # Если нет данных о выручке
    if not has_revenue_data or revenue_growth_rate == 0:
        if is_risky:
            explanation = "риски перевешивают потенциал роста"
            return "Expensive", explanation
        else:
            explanation = "оценка невозможна без данных о выручке (нет SEC данных)"
            return "Fair", explanation
    
    if is_risky:
        explanation = "риски перевешивают потенциал роста"
        return "Expensive", explanation
    
    if revenue_growth_rate >= 15:
        explanation = f"рост выручки ~{revenue_growth_rate:.1f}% годовых — хороший потенциал"
        return "Cheap", explanation
    
    elif revenue_growth_rate >= 8:
        explanation = f"умеренный рост выручки ~{revenue_growth_rate:.1f}% годовых"
        return "Fair", explanation
    
    else:
        explanation = f"слабый рост выручки (~{revenue_growth_rate:.1f}% годовых)"
        return "Expensive", explanation


def get_micro_summary(buffett_tag: str, lynch_tag: str) -> tuple[str, str]:
    """Получение микро-вывода (emoji + описание)."""
    if buffett_tag == "OK" and lynch_tag == "Cheap":
        return "💎", "редкая комбинация качества и привлекательной цены"
    
    if buffett_tag == "OK" and lynch_tag == "Fair":
        return "🟢", "качественный бизнес по разумной цене"
    
    if buffett_tag == "OK" and lynch_tag == "Expensive":
        return "⏳", "бизнес сильный, но лучше дождаться отката"
    
    if buffett_tag == "Expensive" and lynch_tag == "Cheap":
        return "🚀", "ростовая история с потенциалом, но без запаса прочности"
    
    if buffett_tag == "Expensive" and lynch_tag == "Fair":
        return "⚠️", "бизнес хороший, но цена уже учитывает ожидания"
    
    if buffett_tag == "Expensive" and lynch_tag == "Expensive":
        return "🔶", "хорошая компания, но точка входа сейчас некомфортная"
    
    if buffett_tag == "Risky":
        return "🔴", "повышенный риск, требует осторожности"
    
    return "⚪", "ситуация смешанная, требует наблюдения"


async def buffett_analysis(ticker: str) -> str:
    """Основная функция Баффет Анализа."""
    try:
        ticker = ticker.upper().strip()
        logger.info("Starting Buffett analysis for %s", ticker)
        
        # 1. Получение ценовых данных
        price_history = await get_price_history_stooq(ticker)
        if price_history is None or len(price_history) < 30:
            logger.warning("Insufficient price data for %s", ticker)
            return f"❌ Не удалось загрузить ценовые данные для {ticker}. Проверьте тикер."
        
        logger.info("Price history loaded: %d days for %s", len(price_history), ticker)
        
        # 2. Получение фундаментальных данных
        cik = await get_cik_from_ticker(ticker)
        fundamentals = {}
        has_fundamentals = False
        
        if cik:
            logger.info("CIK found: %s for %s, fetching company facts...", cik, ticker)
            facts = await get_company_facts(cik)
            if facts:
                logger.info("Company facts received for %s, extracting data...", ticker)
                fundamentals = extract_fundamental_data(facts)
                has_fundamentals = bool(fundamentals.get('revenue') or fundamentals.get('operating_cash_flow'))
                logger.info("Fundamentals extracted for %s: has_data=%s, metrics=%s", 
                           ticker, has_fundamentals, list(fundamentals.keys()))
            else:
                logger.warning("No company facts received from SEC for %s (CIK: %s)", ticker, cik)
        else:
            logger.info("No CIK found for %s (likely non-US company)", ticker)
        
        # 3. Расчет технических метрик
        tech_metrics = calculate_technical_metrics(price_history)
        
        # 4. Расчет скоринга
        trend_score = calculate_trend_score(
            tech_metrics['current_price'],
            tech_metrics['sma_200'],
            price_history
        )
        momentum_score = calculate_momentum_score(
            tech_metrics['change_5d_pct'],
            tech_metrics.get('change_1m_pct')
        )
        risk_score = calculate_risk_score(tech_metrics.get('max_drawdown'))
        overall_score = calculate_overall_score(trend_score, momentum_score, risk_score)
        
        # 5. Определение рыночной картины и действия
        market_picture = determine_market_picture(
            tech_metrics['current_price'],
            tech_metrics['sma_200'],
            tech_metrics['change_5d_pct'],
            price_history
        )
        action = determine_action(market_picture, overall_score)
        risk_level = determine_risk_level(tech_metrics.get('max_drawdown'))
        
        # 6. Фундаментальный анализ
        if has_fundamentals:
            fcf, cash_flow_status = calculate_fcf(fundamentals)
            dilution_level = calculate_dilution_level(fundamentals)
            revenue_growth = calculate_revenue_growth(fundamentals)
            data_note = ""
        else:
            fcf, cash_flow_status = None, "н/д (не US компания или нет 10-K)"
            dilution_level = "н/д"
            revenue_growth = 0
            data_note = "\n⚠️ Фундаментальные данные недоступны (только для US компаний с SEC filings)"
        
        # 7. Теги Баффета и Линча
        buffett_tag, buffett_explanation = determine_buffett_tag(
            fcf, cash_flow_status, dilution_level, market_picture
        )
        lynch_tag, lynch_explanation = determine_lynch_tag(
            revenue_growth, buffett_tag, has_revenue_data=has_fundamentals and bool(fundamentals.get('revenue'))
        )
        
        # 8. Микро-вывод
        emoji_marker, micro_summary = get_micro_summary(buffett_tag, lynch_tag)
        
        # 9. Confidence level
        fundamentals_quality = "good" if (fundamentals.get('revenue') and fundamentals.get('operating_cash_flow')) else ("partial" if has_fundamentals else "none")
        if fundamentals_quality == "good":
            confidence = "HIGH"
        elif fundamentals_quality == "partial":
            confidence = "MEDIUM"
        else:
            confidence = "LOW (только технический анализ)"
        
        # 10. Формирование сообщения
        change_str = f"+{tech_metrics['change_5d_pct']:.2f}%" if tech_metrics['change_5d_pct'] >= 0 else f"{tech_metrics['change_5d_pct']:.2f}%"
        
        message = f"""{ticker} — ${tech_metrics['current_price']:.2f}  ({tech_metrics['arrow_5d']} {change_str} за 5 дней)

Общая картина: {market_picture}
Оценка: {overall_score} / 10
Действие: {action}
Риск: {risk_level}

Кэш-поток: {cash_flow_status}
Dilution: {dilution_level}
Recent filings: {"доступна SEC отчетность" if has_fundamentals else "н/д"}{data_note}

Инвест-взгляд
• Buffett: {buffett_tag} — {buffett_explanation}
• Lynch: {lynch_tag} — {lynch_explanation}

{emoji_marker} Вывод: {micro_summary}

🟨 Data confidence: {confidence}

Баффет — смотрит на качество и безопасность бизнеса.
Линч — сравнивает рост компании с текущей ценой.
Основано на динамике цены и данных SEC (free sources).
Сценарий ломается при устойчивом падении цены."""
        
        return message
        
    except Exception as exc:
        logger.error("Error in buffett_analysis for %s: %s", ticker, exc)
        return f"❌ Ошибка при анализе {ticker}: {exc}"


async def portfolio_scanner(user_id: int) -> str:
    """Портфельный сканер - упрощенный анализ всех позиций."""
    try:
        # Получаем сохраненный портфель
        raw_text = get_saved_portfolio(user_id)
        if not raw_text:
            return "❌ У вас нет сохраненного портфеля. Сначала используйте '📂 Мой портфель'."
        
        positions = parse_portfolio_text(raw_text)
        if not positions:
            return "❌ Не удалось распарсить портфель."
        
        # Emoji приоритеты для сортировки
        EMOJI_PRIORITY = {
            "💎": 1, "🟢": 2, "⏳": 3, "🚀": 4,
            "⚠️": 5, "🔶": 6, "🔴": 7, "⚪": 8
        }
        
        results = []
        
        # Анализируем каждую позицию параллельно
        async def analyze_position(pos: Position):
            ticker = pos.ticker
            try:
                # Загружаем данные
                price_history = await get_price_history_stooq(ticker)
                if price_history is None or len(price_history) < 5:
                    return {
                        'ticker': ticker,
                        'emoji': '⚪',
                        'price': 0,
                        'day_change': 0,
                        'month_change': 0,
                        'action': 'н/д',
                        'risk': 'н/д',
                        'sort_priority': 999
                    }
                
                # Получаем CIK для определения типа (акция vs ETF)
                cik = await get_cik_from_ticker(ticker)
                is_etf = cik is None  # Если нет CIK, скорее всего ETF
                
                # Расчет метрик
                tech_metrics = calculate_technical_metrics(price_history)
                current_price = tech_metrics['current_price']
                day_change = tech_metrics['change_5d_pct']
                month_change = tech_metrics.get('change_1m_pct', 0) or 0
                
                if is_etf:
                    # Упрощенная логика для ETF
                    emoji = '⚪'
                    action = 'ДЕРЖАТЬ' if month_change >= 0 else 'НАБЛЮДАТЬ'
                    risk = 'Средний'
                else:
                    # Полный анализ для акций
                    trend_score = calculate_trend_score(current_price, tech_metrics['sma_200'], price_history)
                    momentum_score = calculate_momentum_score(day_change, month_change)
                    risk_score = calculate_risk_score(tech_metrics.get('max_drawdown'))
                    overall_score = calculate_overall_score(trend_score, momentum_score, risk_score)
                    
                    market_picture = determine_market_picture(
                        current_price, tech_metrics['sma_200'], day_change, price_history
                    )
                    
                    # Получаем фундаментальные данные (если доступны)
                    fundamentals = {}
                    if cik:
                        facts = await get_company_facts(cik)
                        if facts:
                            fundamentals = extract_fundamental_data(facts)
                    
                    fcf, cash_flow_status = calculate_fcf(fundamentals) if fundamentals else (None, "н/д")
                    dilution_level = calculate_dilution_level(fundamentals) if fundamentals else "н/д"
                    revenue_growth = calculate_revenue_growth(fundamentals) if fundamentals else 0
                    
                    buffett_tag, _ = determine_buffett_tag(fcf, cash_flow_status, dilution_level, market_picture)
                    lynch_tag, _ = determine_lynch_tag(
                        revenue_growth, buffett_tag, 
                        has_revenue_data=bool(fundamentals and fundamentals.get('revenue'))
                    )
                    
                    emoji, _ = get_micro_summary(buffett_tag, lynch_tag)
                    action = determine_action(market_picture, overall_score)
                    risk = determine_risk_level(tech_metrics.get('max_drawdown'))
                
                # Сокращаем риск для компактности
                risk_short = risk.replace('Средний–высокий', 'Ср-Выс').replace('Средний', 'Ср')
                
                return {
                    'ticker': ticker,
                    'emoji': emoji,
                    'price': current_price,
                    'day_change': day_change,
                    'month_change': month_change,
                    'action': action,
                    'risk': risk_short,
                    'sort_priority': EMOJI_PRIORITY.get(emoji, 8)
                }
                
            except Exception as exc:
                logger.warning("Failed to analyze %s in portfolio scanner: %s", ticker, exc)
                return {
                    'ticker': ticker,
                    'emoji': '⚪',
                    'price': 0,
                    'day_change': 0,
                    'month_change': 0,
                    'action': 'ошибка',
                    'risk': 'н/д',
                    'sort_priority': 999
                }
        
        # Параллельный анализ всех позиций
        results = await asyncio.gather(*[analyze_position(pos) for pos in positions])
        
        # Сортировка: по приоритету emoji, затем по месячному изменению, затем по дневному
        results.sort(key=lambda x: (x['sort_priority'], -x['month_change'], -x['day_change']))
        
        # Формирование сообщения
        lines = ["🔍 Портфельный сканер\n"]
        for r in results:
            day_str = f"+{r['day_change']:.1f}%" if r['day_change'] >= 0 else f"{r['day_change']:.1f}%"
            month_str = f"+{r['month_change']:.1f}%" if r['month_change'] >= 0 else f"{r['month_change']:.1f}%"
            
            if r['price'] > 0:
                lines.append(
                    f"{r['emoji']} {r['ticker']}  ${r['price']:.2f}  "
                    f"{day_str} / {month_str}  {r['action']}  ({r['risk']})"
                )
            else:
                lines.append(f"{r['emoji']} {r['ticker']}  н/д")
        
        lines.append("\nБаффет — качество бизнеса.")
        lines.append("Линч — рост vs цена.")
        
        return "\n".join(lines)
        
    except Exception as exc:
        logger.error("Error in portfolio_scanner: %s", exc)
        return f"❌ Ошибка при сканировании портфеля: {exc}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Разбудить сайт на Render (неблокирующий запрос)
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.get("https://telegram-stock-bot-90v1.onrender.com/", follow_redirects=False)
            logger.info("Pinged Render website to keep it alive")
    except Exception as exc:
        logger.debug("Could not ping website: %s", exc)
    
    await update.message.reply_text(
        "Я финансовый помощник по акциям.\n"
        "Могу сделать теханализ акции, AI-обзор новостей и разбор портфеля.\n\n"
        "Выберите действие кнопкой ниже.",
        reply_markup=main_keyboard(),
    )
    return CHOOSING


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Форматы ввода:\n"
        "1) Анализ акции: отправьте тикер, например AAPL или MSFT.\n"
        "2) Портфель: по одной позиции в строке: TICKER QTY AVG_PRICE\n"
        "   Пример:\n"
        "   AAPL 10 170\n"
        "   MSFT 4 320\n"
        "   TSLA 3\n\n"
        "3) Сравнение акций: 2-5 тикеров через пробел или запятую\n"
        "   Пример: AAPL MSFT GOOGL\n\n"
        "4) 💎 Баффет Анализ: глубокий анализ акции по методике Баффета и Линча\n"
        "   - Оценка качества бизнеса (FCF, dilution)\n"
        "   - Анализ роста выручки\n"
        "   - Скоринг 1-10 и рекомендации\n\n"
        "5) 🔍 Портфельный Сканер: быстрый анализ всех позиций портфеля\n"
        "   - Требует предварительно сохраненный портфель\n\n"
        "Кнопка 'Мой портфель' использует последнее сохраненное состояние.\n"
        "Кнопка Отмена возвращает в меню.",
        reply_markup=main_keyboard(),
    )
    return CHOOSING


async def handle_portfolio_from_text(update: Update, text: str, user_id: int) -> int:
    positions = parse_portfolio_text(text)
    if not positions:
        await update.message.reply_text(
            "Не смог распарсить портфель. Используйте формат:\nAAPL 10 170"
        )
        return WAITING_PORTFOLIO

    save_portfolio(user_id, text)
    await update.message.reply_text("Анализирую портфель...")
    result = analyze_portfolio(positions)
    await update.message.reply_text(result)
    return WAITING_PORTFOLIO


async def on_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()

    if text == MENU_STOCK:
        await update.message.reply_text(
            "Отправьте тикер акции (например: AAPL).", reply_markup=main_keyboard()
        )
        return WAITING_STOCK

    if text == MENU_PORTFOLIO:
        await update.message.reply_text(
            "Отправьте портфель списком, каждая позиция с новой строки:\n"
            "TICKER QTY AVG_PRICE\n"
            "Пример:\n"
            "AAPL 10 170\nMSFT 4 320",
            reply_markup=main_keyboard(),
        )
        return WAITING_PORTFOLIO
    
    if text == MENU_COMPARE:
        await update.message.reply_text(
            "Отправьте 2-5 тикеров через пробел или запятую для сравнения.\n"
            "Пример: AAPL MSFT GOOGL\n"
            "или: TSLA, NFLX, NVDA",
            reply_markup=main_keyboard(),
        )
        return WAITING_COMPARISON

    if text == MENU_MY_PORTFOLIO:
        user_id = update.effective_user.id
        saved = get_saved_portfolio(user_id)
        if not saved:
            await update.message.reply_text(
                "Сохраненного портфеля пока нет. Сначала нажмите 'Анализ портфеля' и отправьте список."
            )
            return CHOOSING
        await update.message.reply_text("Загружаю сохраненный портфель...")
        return await handle_portfolio_from_text(update, saved, user_id)
    
    if text == MENU_BUFFETT:
        await update.message.reply_text(
            "💎 Баффет Анализ\n\n"
            "Отправьте тикер акции для глубокого анализа по методике Баффета и Линча.\n"
            "Пример: AAPL",
            reply_markup=main_keyboard()
        )
        return WAITING_BUFFETT
    
    if text == MENU_SCANNER:
        user_id = update.effective_user.id
        saved = get_saved_portfolio(user_id)
        if not saved:
            await update.message.reply_text(
                "❌ У вас нет сохраненного портфеля.\n"
                "Сначала используйте '💼 Анализ портфеля' или '📂 Мой портфель'.",
                reply_markup=main_keyboard()
            )
            return CHOOSING
        
        await update.message.reply_text("🔍 Запускаю портфельный сканер...")
        result = await portfolio_scanner(user_id)
        await update.message.reply_text(result, reply_markup=main_keyboard())
        return CHOOSING

    if text == MENU_HELP:
        return await help_cmd(update, context)

    if text == MENU_CANCEL:
        await update.message.reply_text("Возврат в главное меню.", reply_markup=main_keyboard())
        return CHOOSING

    await update.message.reply_text("Выберите действие кнопкой.", reply_markup=main_keyboard())
    return CHOOSING


async def on_stock_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    ticker = text.upper().replace("$", "")

    if not re.fullmatch(r"[A-Z0-9.\-]{1,12}", ticker):
        await update.message.reply_text("Некорректный тикер. Пример: AAPL")
        return WAITING_STOCK

    await update.message.reply_text(f"Собираю данные по {ticker}...")

    df, reason = stock_snapshot(ticker)
    if df is None:
        if reason == "rate_limit":
            await update.message.reply_text(
                "Основной источник котировок временно ограничил запросы (rate limit).\n"
                "Попытка загрузки из альтернативных источников (SEC EDGAR, Stooq) также не удалась.\n"
                "Попробуйте через 1-2 минуты или используйте другой тикер."
            )
        else:
            await update.message.reply_text(
                "Не удалось загрузить данные по тикеру. Проверь символ и биржевой суффикс.\n"
                "Примеры: AAPL (US), NABL.NS (India), VOD.L (UK)."
            )
        return WAITING_STOCK

    technical = stock_analysis_text(ticker, df)
    chart_path = render_stock_chart(ticker, df)

    news = ticker_news(ticker)
    ai_text = ai_news_analysis(ticker, technical, news)
    final_caption = f"{technical}\n\nНе является индивидуальной инвестиционной рекомендацией."

    with open(chart_path, "rb") as f:
        await update.message.reply_photo(photo=f, caption=final_caption[:1000])

    await update.message.reply_text(ai_text[:3500])

    if news:
        lines = ["Ссылки на новости:"]
        for item in news[:5]:
            source = f"{item['publisher']} {item['date']}".strip()
            lines.append(f"- {item['title']} ({source})")
            if item["link"]:
                lines.append(item["link"])
        await update.message.reply_text("\n".join(lines)[:3500])
    else:
        await update.message.reply_text(
            "Свежие новости по тикеру не найдены ни в основном, ни в резервном источнике."
        )

    try:
        os.remove(chart_path)
    except OSError:
        pass

    return WAITING_STOCK


async def on_buffett_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода тикера для Баффет Анализа."""
    text = (update.message.text or "").strip()
    ticker = text.upper().replace("$", "")

    if not re.fullmatch(r"[A-Z0-9.\-]{1,12}", ticker):
        await update.message.reply_text("Некорректный тикер. Пример: AAPL")
        return WAITING_BUFFETT

    await update.message.reply_text(f"💎 Провожу глубокий анализ {ticker} по методике Баффета и Линча...")
    
    result = await buffett_analysis(ticker)
    await update.message.reply_text(result, reply_markup=main_keyboard())
    
    return WAITING_BUFFETT


async def on_portfolio_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    user_id = update.effective_user.id
    return await handle_portfolio_from_text(update, text, user_id)


async def on_comparison_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    
    # Parse tickers (space or comma separated)
    tickers = re.split(r'[,\s]+', text.upper())
    tickers = [t.strip().replace("$", "") for t in tickers if t.strip()]
    
    # Validate tickers
    valid_tickers = []
    for ticker in tickers:
        if re.fullmatch(r"[A-Z0-9.\-]{1,12}", ticker):
            valid_tickers.append(ticker)
    
    if len(valid_tickers) < 2:
        await update.message.reply_text(
            "Нужно минимум 2 корректных тикера.\nПример: AAPL MSFT GOOGL"
        )
        return WAITING_COMPARISON
    
    if len(valid_tickers) > 5:
        await update.message.reply_text(
            "Максимум 5 тикеров за раз.\nПопробуйте уменьшить количество."
        )
        return WAITING_COMPARISON
    
    await update.message.reply_text(f"Сравниваю {', '.join(valid_tickers)}...")
    
    chart_path, result_text = compare_stocks(valid_tickers, period="6mo")
    
    if chart_path is None:
        await update.message.reply_text(f"Ошибка: {result_text}")
        return WAITING_COMPARISON
    
    # Send chart
    with open(chart_path, "rb") as f:
        await update.message.reply_photo(photo=f, caption=result_text[:1000])
    
    # Clean up
    try:
        os.remove(chart_path)
    except OSError:
        pass
    
    return WAITING_COMPARISON


async def my_portfolio_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    saved = get_saved_portfolio(user_id)
    if not saved:
        await update.message.reply_text("Сохраненного портфеля нет. Сначала отправьте его через 'Анализ портфеля'.")
        return
    await update.message.reply_text("Загружаю сохраненный портфель...")
    positions = parse_portfolio_text(saved)
    if not positions:
        await update.message.reply_text("Сохраненный портфель поврежден. Отправьте его заново.")
        return
    result = analyze_portfolio(positions)
    await update.message.reply_text(result)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Диалог завершён.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def cache_stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show cache statistics."""
    market_size = len(market_data_cache.cache)
    news_size = len(news_cache.cache)
    
    stats = (
        f"📊 Статистика кэша:\n\n"
        f"Котировок закэшировано: {market_size}\n"
        f"Новостей закэшировано: {news_size}\n"
        f"TTL котировок: {MARKET_DATA_CACHE_TTL}с ({MARKET_DATA_CACHE_TTL//60}м)\n"
        f"TTL новостей: {NEWS_CACHE_TTL}с ({NEWS_CACHE_TTL//60}м)\n\n"
        f"Используйте /clearcache для очистки кэша"
    )
    await update.message.reply_text(stats)


async def clear_cache_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear all cache."""
    market_data_cache.clear()
    news_cache.clear()
    await update.message.reply_text("✅ Кэш очищен!")
    logger.info("Cache cleared by user %s", update.effective_user.id)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled error while processing update: %s", context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Внутренняя ошибка обработки. Попробуйте еще раз через несколько секунд."
            )
        except Exception:
            pass


def is_menu_button(text: str) -> bool:
    """Check if text is a menu button."""
    return text in {MENU_CANCEL, MENU_HELP, MENU_STOCK, MENU_PORTFOLIO, MENU_MY_PORTFOLIO, MENU_COMPARE, MENU_BUFFETT, MENU_SCANNER}


async def ping_render_website(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Периодический пинг сайта на Render для предотвращения засыпания."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get("https://telegram-stock-bot-90v1.onrender.com/", follow_redirects=False)
            logger.info("Hourly ping to Render website: HTTP %d", response.status_code)
    except Exception as exc:
        logger.debug("Error during hourly website ping: %s", exc)


def build_app(token: str) -> Application:
    app = Application.builder().token(token).build()
    
    # Filter for menu buttons - matches exact button text
    menu_buttons = [MENU_CANCEL, MENU_HELP, MENU_STOCK, MENU_PORTFOLIO, MENU_MY_PORTFOLIO, MENU_COMPARE, MENU_BUFFETT, MENU_SCANNER]
    menu_button_filter = filters.Text(menu_buttons)

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [
                CommandHandler("start", start),
                CommandHandler("help", help_cmd),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_choice),
            ],
            WAITING_STOCK: [
                CommandHandler("start", start),
                CommandHandler("help", help_cmd),
                MessageHandler(menu_button_filter, on_choice),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_stock_input),
            ],
            WAITING_PORTFOLIO: [
                CommandHandler("start", start),
                CommandHandler("help", help_cmd),
                MessageHandler(menu_button_filter, on_choice),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_portfolio_input)
            ],
            WAITING_COMPARISON: [
                CommandHandler("start", start),
                CommandHandler("help", help_cmd),
                MessageHandler(menu_button_filter, on_choice),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_comparison_input)
            ],
            WAITING_BUFFETT: [
                CommandHandler("start", start),
                CommandHandler("help", help_cmd),
                MessageHandler(menu_button_filter, on_choice),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_buffett_input)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("myportfolio", my_portfolio_cmd))
    app.add_handler(CommandHandler("cachestats", cache_stats_cmd))
    app.add_handler(CommandHandler("clearcache", clear_cache_cmd))
    app.add_error_handler(on_error)
    
    # Add job to ping Render website every hour to prevent sleep
    job_queue = app.job_queue
    job_queue.run_repeating(ping_render_website, interval=3600, first=60)
    logger.info("Scheduled hourly website ping to keep Render service alive")
    
    return app


def main() -> None:
    load_dotenv()

    global DB_PATH, OPENAI_API_KEY, OPENAI_MODEL
    DB_PATH = os.getenv("PORTFOLIO_DB_PATH", "portfolio.db")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set. Put it in .env file.")

    init_db()

    logger.info("Starting bot at %s", datetime.now(timezone.utc).isoformat())
    app = build_app(token)
    
    # Graceful shutdown for Render.com (handle SIGTERM)
    def sig_handler(signum, frame):
        logger.info("Signal %d received, shutting down gracefully...", signum)
        app.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)
    
    try:
        app.run_polling(close_loop=False)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
