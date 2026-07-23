"""GitHub Actions Runner — the main entry point for every scheduled workflow run.

Each run:
1. Initialises all services
2. Runs the pipeline for the configured RUN_MODE
3. Publishes to Telegram
4. Saves state to SQLite (committed to repo via git)
5. Logs metrics and exits cleanly

RUN_MODE is passed as an environment variable from the GitHub Actions workflow.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from typing import Any

from football_bot.config.settings import get_settings
from football_bot.core.models.publication import Publication, PublicationStatus
from football_bot.parsers.html_parser import HTMLParser
from football_bot.parsers.rss_parser import RSSParser
from football_bot.parsers.transfer_parser import TransferParser
from football_bot.repositories.match_repository import MatchRepository
from football_bot.repositories.news_repository import NewsRepository
from football_bot.repositories.publication_repository import PublicationRepository
from football_bot.services.ai_editor import AIEditor
from football_bot.services.analytics_engine import AnalyticsEngine
from football_bot.services.duplicate_detector import DuplicateDetector
from football_bot.services.fact_checker import FactChecker
from football_bot.services.facts_generator import FactsGenerator
from football_bot.services.history_generator import HistoryGenerator
from football_bot.services.image_generator import ImageGenerator
from football_bot.services.image_search import ImageSearchService
from football_bot.services.live_center import LiveCenter
from football_bot.services.match_center import MatchCenter
from football_bot.services.mistral_service import MistralService
from football_bot.services.news_aggregator import NewsAggregator
from football_bot.services.self_learning import SelfLearningModule
from football_bot.services.standings_generator import StandingsGenerator
from football_bot.storage.database import get_database_manager
from football_bot.telegram.publisher import TelegramPublisher
from football_bot.utils.health import HealthChecker
from football_bot.utils.logger import configure_logging, get_logger
from football_bot.utils.metrics import MetricsCollector

logger = get_logger(__name__)


class Container:
    """Dependency injection container — wires all services together."""

    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.db_manager = get_database_manager(settings.database_path)
        self.metrics = MetricsCollector()
        self.health_checker = HealthChecker()

        session_factory = None  # Set after DB init

        self.mistral = MistralService(session_factory=None)
        self.html_parser = HTMLParser()
        self.rss_parser = RSSParser()
        self.transfer_parser = TransferParser()

        self.news_repo: NewsRepository | None = None
        self.match_repo: MatchRepository | None = None
        self.pub_repo: PublicationRepository | None = None

        self.news_aggregator: NewsAggregator | None = None
        self.duplicate_detector: DuplicateDetector | None = None
        self.fact_checker: FactChecker | None = None
        self.ai_editor: AIEditor | None = None
        self.image_search = ImageSearchService()  # <-- НОВОЕ
        self.image_generator = ImageGenerator(self.image_search)  # <-- ПЕРЕДАЁМ
        self.publisher = TelegramPublisher()
        self.match_center: MatchCenter | None = None
        self.live_center: LiveCenter | None = None
        self.standings_generator: StandingsGenerator | None = None
        self.history_generator: HistoryGenerator | None = None
        self.facts_generator: FactsGenerator | None = None
        self.analytics_engine: AnalyticsEngine | None = None
        self.self_learning: SelfLearningModule | None = None

    async def initialise(self) -> None:
        await self.db_manager.initialise()
        session_factory = self.db_manager.get_session_factory()

        self.mistral = MistralService(session_factory=session_factory)

        self.news_repo = NewsRepository(session_factory)
        self.match_repo = MatchRepository(session_factory)
        self.pub_repo = PublicationRepository(session_factory)

        self.news_aggregator = NewsAggregator(self.news_repo, self.rss_parser, self.transfer_parser)
        self.duplicate_detector = DuplicateDetector(self.news_repo, self.settings.deduplication_threshold)
        self.fact_checker = FactChecker(self.mistral, self.news_repo)
        self.ai_editor = AIEditor(self.mistral)
        self.match_center = MatchCenter(self.match_repo)
        self.live_center = LiveCenter(self.match_repo, self.mistral)
        self.standings_generator = StandingsGenerator(self.html_parser, self.mistral)
        self.history_generator = HistoryGenerator(self.mistral)
        self.facts_generator = FactsGenerator(self.mistral)
        self.analytics_engine = AnalyticsEngine(self.pub_repo, self.mistral, session_factory)
        self.self_learning = SelfLearningModule(self.analytics_engine, session_factory)

        self.health_checker.register("telegram", self.publisher.health_check)
        self.health_checker.register("mistral", self.mistral.health_check)

        logger.info("container_initialised")

    async def shutdown(self) -> None:
        await self.mistral.close()
        await self.publisher.close()
        await self.html_parser.close()
        await self.rss_parser.close()
        await self.transfer_parser.close()
        if self.match_center:
            await self.match_center.close()
        await self.image_search.close()  # <-- НОВОЕ
        await self.db_manager.close()
        logger.info("container_shutdown")


# ── Pipeline implementations (без изменений) ───────────────────────────────────

async def pipeline_news(c: Container) -> list[Publication]:
    """Collect → deduplicate → fact-check → write → image → queue."""
    logger.info("pipeline_news_started")
    c.metrics.set_run_mode("news")

    new_items = await c.news_aggregator.run()
    c.metrics.increment("news_fetched", len(new_items))

    unique_items = await c.duplicate_detector.run_batch(new_items)
    c.metrics.increment("news_unique", len(unique_items))

    checked_items = await c.fact_checker.check_batch(unique_items)
    publishable = [
        item for item in checked_items
        if item.reliability_score >= c.settings.min_reliability_score
        and not item.is_duplicate
    ]
    c.metrics.increment("news_publishable", len(publishable))

    publications: list[Publication] = []
    max_pubs = c.settings.max_publications_per_run

    for item in publishable[:max_pubs]:
        if item.category.value == "transfer":
            pub = await c.ai_editor.write_transfer_news(item)
        else:
            pub = await c.ai_editor.write_breaking_news(item)

        # Генерация изображения (теперь асинхронно)
        image_path = await c.image_generator.generate_for_publication(pub, source_item=item)
        if image_path:
            pub.image_path = image_path

        await c.pub_repo.save(pub)
        await c.news_repo.mark_published(item.item_id)
        publications.append(pub)

    logger.info("pipeline_news_complete", generated=len(publications))
    return publications


async def pipeline_live(c: Container) -> list[Publication]:
    """Poll live matches and publish event updates."""
    logger.info("pipeline_live_started")
    c.metrics.set_run_mode("live")

    live_matches = await c.match_repo.get_live()
    c.metrics.gauge("live_matches", len(live_matches))

    today_matches = await c.match_center.fetch_today_matches()
    all_live = [m for m in today_matches if m.is_live]

    publications: list[Publication] = []
    for match in all_live:
        event_pubs = await c.live_center.process_new_events(match)
        for pub in event_pubs:
            await c.pub_repo.save(pub)
        publications.extend(event_pubs)

    logger.info("pipeline_live_complete", events_published=len(publications))
    return publications


async def pipeline_digest_daily(c: Container) -> list[Publication]:
    logger.info("pipeline_digest_daily_started")
    c.metrics.set_run_mode("digest_daily")

    items = await c.news_repo.get_recent(hours=24, limit=20)
    matches = await c.match_repo.get_recent_finished(hours=24)

    pub = await c.ai_editor.write_daily_digest(items, matches)
    # Генерация изображения для дайджеста (опционально)
    image_path = await c.image_generator.generate_for_publication(pub)
    if image_path:
        pub.image_path = image_path
    await c.pub_repo.save(pub)
    return [pub]


async def pipeline_digest_weekly(c: Container) -> list[Publication]:
    logger.info("pipeline_digest_weekly_started")
    c.metrics.set_run_mode("digest_weekly")

    items = await c.news_repo.get_recent(hours=168, limit=50)
    matches = await c.match_repo.get_recent_finished(hours=168)

    pub = await c.ai_editor.write_weekly_digest(items, matches)
    image_path = await c.image_generator.generate_for_publication(pub)
    if image_path:
        pub.image_path = image_path
    await c.pub_repo.save(pub)
    return [pub]


async def pipeline_digest_monthly(c: Container) -> list[Publication]:
    logger.info("pipeline_digest_monthly_started")
    c.metrics.set_run_mode("digest_monthly")

    items = await c.news_repo.get_recent(hours=720, limit=100)
    matches = await c.match_repo.get_recent_finished(hours=720)

    pub = await c.ai_editor.write_monthly_digest(items, matches)
    image_path = await c.image_generator.generate_for_publication(pub)
    if image_path:
        pub.image_path = image_path
    await c.pub_repo.save(pub)
    return [pub]


async def pipeline_facts(c: Container) -> list[Publication]:
    logger.info("pipeline_facts_started")
    c.metrics.set_run_mode("facts")

    from datetime import datetime as dt
    day_of_month = dt.utcnow().day
    if day_of_month % 3 == 0:
        pub = await c.history_generator.generate_on_this_day()
    else:
        pub = await c.facts_generator.generate_interesting_fact()

    image_path = await c.image_generator.generate_for_publication(pub)
    if image_path:
        pub.image_path = image_path

    await c.pub_repo.save(pub)
    return [pub]


async def pipeline_standings(c: Container) -> list[Publication]:
    logger.info("pipeline_standings_started")
    c.metrics.set_run_mode("standings")

    from football_bot.config.constants import LEAGUES
    strategy = await c.self_learning.get_current_strategy()
    preferred_leagues = strategy.get("preferred_leagues", ["UCL", "PL", "LL"])

    publications: list[Publication] = []
    for league_code in preferred_leagues[:3]:
        pub = await c.standings_generator.generate_standings_post(league_code)
        if pub:
            league = LEAGUES.get(league_code, {})
            top_rows: list[tuple] = []
            table = await c.standings_generator.fetch_standings(league_code)
            if table:
                top_rows = [(s.position, s.team_name, s.points) for s in table.top(8)]
            image_path = c.image_generator.generate_standings_card(
                league.get("name", league_code), top_rows
            )
            if image_path:
                pub.image_path = image_path
            await c.pub_repo.save(pub)
            publications.append(pub)

    return publications


async def pipeline_analytics(c: Container) -> list[Publication]:
    logger.info("pipeline_analytics_started")
    c.metrics.set_run_mode("analytics")

    if c.settings.enable_self_learning:
        state = await c.self_learning.run_learning_cycle()
        logger.info("self_learning_state_updated", iteration=state.get("iteration"))

    report = await c.analytics_engine.compute_analytics_report(c.settings.analytics_window_days)
    recommendations = await c.analytics_engine.generate_strategy_recommendations(report)
    logger.info("analytics_recommendations", text=recommendations[:200])
    return []


_PIPELINES = {
    "news": pipeline_news,
    "live": pipeline_live,
    "digest_daily": pipeline_digest_daily,
    "digest_weekly": pipeline_digest_weekly,
    "digest_monthly": pipeline_digest_monthly,
    "facts": pipeline_facts,
    "standings": pipeline_standings,
    "analytics": pipeline_analytics,
}


async def run() -> None:
    """Main async entry point for GitHub Actions."""
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)

    logger.info(
        "run_started",
        mode=settings.run_mode,
        timestamp=datetime.utcnow().isoformat(),
    )

    container = Container()
    try:
        await container.initialise()

        health_results = await container.health_checker.run_all()
        critical_ok = container.health_checker.critical_healthy(health_results, ["telegram", "mistral"])
        if not critical_ok:
            logger.error("critical_health_check_failed")
            sys.exit(1)

        pipeline_fn = _PIPELINES.get(settings.run_mode)
        if not pipeline_fn:
            logger.error("unknown_run_mode", mode=settings.run_mode)
            sys.exit(1)

        publications = await pipeline_fn(container)
        container.metrics.increment("publications_generated", len(publications))

        ready_pubs = [p for p in publications if p.status == PublicationStatus.READY]
        message_ids = await container.publisher.publish_batch(ready_pubs)
        container.metrics.increment("publications_sent", len([m for m in message_ids if m]))

        for pub, msg_id in zip(ready_pubs, message_ids):
            if msg_id:
                await container.pub_repo.update_message_id(pub.pub_id, msg_id)
                await container.analytics_engine.record_publication_event(pub)
            else:
                await container.pub_repo.update_status(pub.pub_id, PublicationStatus.FAILED)

        await container.metrics.persist()
        container.metrics.log_summary()

        logger.info(
            "run_complete",
            mode=settings.run_mode,
            publications_sent=len([m for m in message_ids if m]),
        )

    except Exception as exc:
        logger.error("run_fatal_error", error=str(exc), exc_info=True)
        sys.exit(1)
    finally:
        await container.shutdown()
