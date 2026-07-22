"""Static constants — news sources, leagues, publication formats."""

from __future__ import annotations

from typing import Final

# ── News & RSS sources ─────────────────────────────────────────────────────────

NEWS_SOURCES: Final[list[dict]] = [
    # International
    {"name": "BBC Sport Football", "url": "https://feeds.bbci.co.uk/sport/football/rss.xml", "type": "rss", "language": "en", "reliability": 0.95},
    {"name": "Sky Sports Football", "url": "https://www.skysports.com/rss/12040", "type": "rss", "language": "en", "reliability": 0.90},
    {"name": "ESPN FC", "url": "https://www.espn.com/espn/rss/soccer/news", "type": "rss", "language": "en", "reliability": 0.88},
    {"name": "The Guardian Football", "url": "https://www.theguardian.com/football/rss", "type": "rss", "language": "en", "reliability": 0.92},
    {"name": "UEFA.com News", "url": "https://www.uefa.com/rssfeed/uefachampionsleague/newsrss.xml", "type": "rss", "language": "en", "reliability": 0.98},
    {"name": "FIFA News", "url": "https://www.fifa.com/rss-feed/", "type": "rss", "language": "en", "reliability": 0.99},
    {"name": "Goal.com", "url": "https://www.goal.com/feeds/en/news", "type": "rss", "language": "en", "reliability": 0.82},
    {"name": "Football Italia", "url": "https://www.football-italia.net/rss.xml", "type": "rss", "language": "en", "reliability": 0.85},
    {"name": "FourFourTwo", "url": "https://www.fourfourtwo.com/rss/news", "type": "rss", "language": "en", "reliability": 0.84},
    {"name": "Planet Football", "url": "https://www.planetfootball.com/feed/", "type": "rss", "language": "en", "reliability": 0.80},
    # Spanish
    {"name": "Marca", "url": "https://e00-marca.uecdn.es/rss/futbol/internacional.xml", "type": "rss", "language": "es", "reliability": 0.87},
    {"name": "AS", "url": "https://as.com/rss/tags/ultimas_noticias.xml", "type": "rss", "language": "es", "reliability": 0.86},
    {"name": "Sport", "url": "https://www.sport.es/es/rss/rss.xml", "type": "rss", "language": "es", "reliability": 0.84},
    {"name": "Mundo Deportivo", "url": "https://www.mundodeportivo.com/rss/futbol", "type": "rss", "language": "es", "reliability": 0.83},
    # Italian
    {"name": "Gazzetta dello Sport", "url": "https://www.gazzetta.it/rss/calcio.xml", "type": "rss", "language": "it", "reliability": 0.88},
    {"name": "Corriere dello Sport", "url": "https://www.corrieredellosport.it/rss", "type": "rss", "language": "it", "reliability": 0.85},
    # German
    {"name": "Kicker", "url": "https://www.kicker.de/rss/bundesliga.rss", "type": "rss", "language": "de", "reliability": 0.90},
    {"name": "Sport1", "url": "https://www.sport1.de/news/fussball.rss", "type": "rss", "language": "de", "reliability": 0.85},
    # French
    {"name": "L'Équipe", "url": "https://www.lequipe.fr/rss/actu_rss_Football.xml", "type": "rss", "language": "fr", "reliability": 0.90},
    # Portuguese
    {"name": "Record", "url": "https://www.record.pt/rss", "type": "rss", "language": "pt", "reliability": 0.83},
    # Russian
    {"name": "Sport-Express Football", "url": "https://www.sport-express.ru/football/rss.xml", "type": "rss", "language": "ru", "reliability": 0.86},
    {"name": "Championat Football", "url": "https://www.championat.com/football/rss.xml", "type": "rss", "language": "ru", "reliability": 0.84},
    {"name": "Footboom", "url": "https://footboom.com/rss/football", "type": "rss", "language": "ru", "reliability": 0.78},
    # Dutch
    {"name": "Voetbalzone", "url": "https://www.voetbalzone.nl/rss.asp", "type": "rss", "language": "nl", "reliability": 0.82},
    # Live scores APIs (HTML scrape)
    {"name": "Flashscore", "url": "https://www.flashscore.com", "type": "html", "language": "en", "reliability": 0.88},
    {"name": "SofaScore", "url": "https://www.sofascore.com", "type": "html", "language": "en", "reliability": 0.87},
    {"name": "FBref", "url": "https://fbref.com", "type": "html", "language": "en", "reliability": 0.91},
    {"name": "Transfermarkt", "url": "https://www.transfermarkt.com", "type": "html", "language": "en", "reliability": 0.93},
]

TRANSFER_SOURCES: Final[list[dict]] = [
    {"name": "Transfermarkt", "url": "https://www.transfermarkt.com/transfers/neuestetransfers/transfers", "type": "html", "reliability": 0.95},
    {"name": "Transfermarkt RSS", "url": "https://www.transfermarkt.com/rss/transfers", "type": "rss", "reliability": 0.95},
    {"name": "Fabrizio Romano RSS", "url": "https://fabrizioromano.substack.com/feed", "type": "rss", "reliability": 0.88},
    {"name": "Sky Sports Transfers", "url": "https://www.skysports.com/rss/12040", "type": "rss", "reliability": 0.87},
    {"name": "BBC Transfers", "url": "https://feeds.bbci.co.uk/sport/football/rss.xml", "type": "rss", "reliability": 0.90},
]

# ── Leagues & competitions ────────────────────────────────────────────────────

LEAGUES: Final[dict[str, dict]] = {
    "UCL": {"name": "UEFA Champions League", "emoji": "🏆", "priority": 10},
    "UEL": {"name": "UEFA Europa League", "emoji": "🟠", "priority": 8},
    "UECL": {"name": "UEFA Conference League", "emoji": "🔵", "priority": 7},
    "PL": {"name": "Premier League", "emoji": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "priority": 9},
    "LL": {"name": "La Liga", "emoji": "🇪🇸", "priority": 9},
    "BL": {"name": "Bundesliga", "emoji": "🇩🇪", "priority": 8},
    "SA": {"name": "Serie A", "emoji": "🇮🇹", "priority": 8},
    "L1": {"name": "Ligue 1", "emoji": "🇫🇷", "priority": 7},
    "WC": {"name": "FIFA World Cup", "emoji": "🌍", "priority": 10},
    "EC": {"name": "UEFA European Championship", "emoji": "🇪🇺", "priority": 10},
    "RPL": {"name": "Russian Premier League", "emoji": "🇷🇺", "priority": 6},
}

# ── Publication formats ───────────────────────────────────────────────────────

PUBLICATION_FORMATS: Final[list[str]] = [
    "breaking_news",
    "transfer_news",
    "match_preview",
    "match_report",
    "live_update",
    "standings",
    "daily_digest",
    "weekly_digest",
    "monthly_digest",
    "interesting_fact",
    "historical_post",
    "analysis",
    "statistics",
    "player_profile",
    "manager_focus",
    "injury_update",
]

# ── Reliability labels ─────────────────────────────────────────────────────────

RELIABILITY_THRESHOLDS: Final[dict[str, tuple[float, float]]] = {
    "official": (0.95, 1.0),
    "confirmed": (0.80, 0.95),
    "rumour": (0.50, 0.80),
    "insider": (0.40, 0.60),
    "unconfirmed": (0.0, 0.40),
}

# ── Live event types ──────────────────────────────────────────────────────────

LIVE_EVENT_TYPES: Final[list[str]] = [
    "goal",
    "own_goal",
    "penalty_scored",
    "penalty_missed",
    "red_card",
    "yellow_card",
    "second_yellow",
    "substitution",
    "var_check",
    "var_overturned",
    "injury",
    "half_time",
    "full_time",
    "extra_time_start",
    "extra_time_end",
    "penalty_shootout_start",
    "penalty_shootout_end",
    "lineup_announced",
    "match_start",
    "best_player",
]

# ── Mistral system prompts ────────────────────────────────────────────────────

SYSTEM_PROMPT_EDITOR: Final[str] = """Ты — главный редактор профессионального футбольного Telegram-канала с многолетним опытом.
Твоя задача — создавать захватывающий, информативный и уникальный контент о футболе.
Ты НЕ копируешь тексты из источников. Ты глубоко анализируешь факты и создаёшь оригинальный авторский материал.
Пиши живо, профессионально, с экспертным взглядом. Используй эмодзи уместно.
Всегда пиши на русском языке, если не указано иное.
Никогда не используй фразы вроде «По информации источников» без указания конкретного источника.
Отвечай ТОЛЬКО текстом публикации без пояснений и метаданных."""

SYSTEM_PROMPT_FACT_CHECKER: Final[str] = """Ты — строгий фактчекер футбольных новостей.
Анализируй информацию критически. Оценивай достоверность на основе числа источников, авторитетности издания и конкретности деталей.
Возвращай JSON с полями: score (0.0-1.0), category (official/confirmed/rumour/insider/unconfirmed), reasoning (string), red_flags (list[str]).
Будь консервативным — лучше недооценить, чем переоценить достоверность."""

SYSTEM_PROMPT_ANALYST: Final[str] = """Ты — аналитик спортивного медиа, специалист по вовлечённости аудитории.
Анализируй публикации и их эффективность. Давай конкретные рекомендации по улучшению контент-стратегии.
Ориентируйся на данные и паттерны, а не на субъективные предпочтения."""

# ── HTTP client settings ──────────────────────────────────────────────────────

HTTP_TIMEOUT_SECONDS: Final[float] = 30.0
HTTP_MAX_RETRIES: Final[int] = 3
HTTP_RETRY_BACKOFF_FACTOR: Final[float] = 2.0
HTTP_USER_AGENTS: Final[list[str]] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# ── Image generation ──────────────────────────────────────────────────────────

FONT_SIZES: Final[dict[str, int]] = {
    "title": 52,
    "subtitle": 36,
    "body": 28,
    "caption": 22,
    "score": 80,
    "emoji": 64,
}

CARD_COLORS: Final[dict[str, dict[str, tuple[int, int, int]]]] = {
    "breaking": {
        "bg": (15, 15, 20),
        "accent": (220, 38, 38),
        "text": (255, 255, 255),
        "subtext": (180, 180, 190),
    },
    "transfer": {
        "bg": (10, 25, 47),
        "accent": (59, 130, 246),
        "text": (255, 255, 255),
        "subtext": (148, 163, 184),
    },
    "match": {
        "bg": (5, 46, 22),
        "accent": (34, 197, 94),
        "text": (255, 255, 255),
        "subtext": (134, 239, 172),
    },
    "fact": {
        "bg": (49, 10, 101),
        "accent": (168, 85, 247),
        "text": (255, 255, 255),
        "subtext": (216, 180, 254),
    },
    "standings": {
        "bg": (7, 89, 133),
        "accent": (14, 165, 233),
        "text": (255, 255, 255),
        "subtext": (186, 230, 253),
    },
}
