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
from tempfile import NamedTemporaryFile
from typing import Dict, List, Optional, Tuple, Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from xml.etree import ElementTree

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
MENU_HELP = "ℹ️ Помощь"
MENU_CANCEL = "❌ Отмена"

CHOOSING, WAITING_STOCK, WAITING_PORTFOLIO, WAITING_COMPARISON = range(4)

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
    for ticker in tickers:
        data, reason = load_market_data(ticker, period=period, interval="1d", min_rows=30)
        if data is None or "Close" not in data.columns:
            return None, f"Не удалось загрузить данные для {ticker}"
        data_dict[ticker] = data["Close"]
    
    # Combine into single DataFrame
    prices_df = pd.DataFrame(data_dict).dropna()
    
    if len(prices_df) < 30:
        return None, "Недостаточно данных для сравнения (нужно минимум 30 дней)"
    
    # Calculate returns
    returns = prices_df.pct_change().dropna()
    
    # Correlation matrix
    corr_matrix = returns.corr()
    
    # Normalize prices to 100 at start (relative performance)
    normalized = (prices_df / prices_df.iloc[0]) * 100
    
    # Calculate statistics
    total_return = {}
    volatility = {}
    for ticker in tickers:
        total_return[ticker] = ((prices_df[ticker].iloc[-1] / prices_df[ticker].iloc[0]) - 1) * 100
        volatility[ticker] = returns[ticker].std() * np.sqrt(252) * 100  # Annualized
    
    # Create comparison chart
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [2, 1]})
    
    # Plot normalized prices
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    for i, ticker in enumerate(tickers):
        ax1.plot(normalized.index, normalized[ticker], label=ticker, 
                linewidth=2, color=colors[i % len(colors)])
    
    ax1.set_title("Относительная динамика акций (нормализовано к 100)", fontsize=14, fontweight='bold')
    ax1.set_ylabel("Индекс (старт = 100)")
    ax1.grid(alpha=0.3)
    ax1.legend(loc='best')
    ax1.axhline(100, color='gray', linestyle='--', linewidth=0.8, alpha=0.5)
    
    # Plot correlation heatmap
    im = ax2.imshow(corr_matrix, cmap='RdYlGn', vmin=-1, vmax=1, aspect='auto')
    ax2.set_xticks(range(len(tickers)))
    ax2.set_yticks(range(len(tickers)))
    ax2.set_xticklabels(tickers)
    ax2.set_yticklabels(tickers)
    ax2.set_title("Корреляция доходностей", fontsize=12)
    
    # Add correlation values
    for i in range(len(tickers)):
        for j in range(len(tickers)):
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
    lines.append(f"Период: {period}, точек данных: {len(prices_df)}\n")
    
    lines.append("Результаты:")
    sorted_by_return = sorted(total_return.items(), key=lambda x: x[1], reverse=True)
    for ticker, ret in sorted_by_return:
        vol = volatility[ticker]
        lines.append(f"- {ticker}: доходность {ret:+.2f}%, волатильность {vol:.1f}%")
    
    lines.append("\nКорреляция (наиболее интересные пары):")
    corr_pairs = []
    for i in range(len(tickers)):
        for j in range(i+1, len(tickers)):
            corr_pairs.append((tickers[i], tickers[j], corr_matrix.iloc[i, j]))
    
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

    if text == MENU_HELP:
        return await help_cmd(update, context)

    if text == MENU_CANCEL:
        await update.message.reply_text("Возврат в главное меню.", reply_markup=main_keyboard())
        return CHOOSING

    await update.message.reply_text("Выберите действие кнопкой.", reply_markup=main_keyboard())
    return CHOOSING


async def on_stock_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    
    # Check if it's a menu button BEFORE processing as ticker
    if text in {MENU_CANCEL, MENU_HELP, MENU_STOCK, MENU_PORTFOLIO, MENU_MY_PORTFOLIO, MENU_COMPARE}:
        return await on_choice(update, context)
    
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


async def on_portfolio_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    
    # Check if it's a menu button BEFORE processing as portfolio
    if text in {MENU_CANCEL, MENU_HELP, MENU_STOCK, MENU_PORTFOLIO, MENU_MY_PORTFOLIO, MENU_COMPARE}:
        return await on_choice(update, context)

    user_id = update.effective_user.id
    return await handle_portfolio_from_text(update, text, user_id)


async def on_comparison_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    
    # Check if it's a menu button BEFORE processing as tickers
    if text in {MENU_CANCEL, MENU_HELP, MENU_STOCK, MENU_PORTFOLIO, MENU_MY_PORTFOLIO, MENU_COMPARE}:
        return await on_choice(update, context)
    
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


def build_app(token: str) -> Application:
    app = Application.builder().token(token).build()

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
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_stock_input),
            ],
            WAITING_PORTFOLIO: [
                CommandHandler("start", start),
                CommandHandler("help", help_cmd),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_portfolio_input)
            ],
            WAITING_COMPARISON: [
                CommandHandler("start", start),
                CommandHandler("help", help_cmd),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_comparison_input)
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
