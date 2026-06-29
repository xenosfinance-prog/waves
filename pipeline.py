from typing import Optional
from collectors.rss_collector import RSSCollector
from analyzers.deduplicator import Deduplicator
from analyzers.classifier import Classifier
from analyzers.market_analyzer import MarketAnalyzer
from analyzers.gemini_writer import GeminiWriter
from writers.html_writer import HTMLWriter
from writers.github_publisher import GitHubPublisher
from config.settings import RSS_FEEDS, OUTPUT_PATH
from utils.logger import get_logger

log = get_logger(__name__)


class MarketIntelligencePipeline:
    def __init__(self, output_path: str = OUTPUT_PATH, publish: bool = True):
        self.output_path    = output_path
        self.publish        = publish
        self.collector      = RSSCollector(RSS_FEEDS)
        self.deduplicator   = Deduplicator()
        self.classifier     = Classifier()
        self.analyzer       = MarketAnalyzer()
        self.gemini_writer  = GeminiWriter()
        self.html_writer    = HTMLWriter()
        self.github         = GitHubPublisher()

    def run(self) -> Optional[str]:
        log.info("=" * 60)
        log.info("XenosFinance Market Intelligence Pipeline — START")
        log.info("=" * 60)

        # Step 1: Collect RSS
        articles = self.collector.collect()
        if not articles:
            log.error("No articles collected — aborting.")
            return None
        log.info(f"Step 1 ✓ Collected {len(articles)} articles")

        # Step 2: Deduplicate
        articles = self.deduplicator.deduplicate(articles)
        log.info(f"Step 2 ✓ Deduplicated → {len(articles)} articles")

        # Step 3: Classify + score
        articles = self.classifier.classify(articles)
        log.info(f"Step 3 ✓ Classified")

        # Step 4: Market analysis
        market_data = self.analyzer.analyze(articles)
        log.info(f"Step 4 ✓ Market analysis: {market_data['overall_label']}")

        # Step 5: Gemini AI brief
        log.info("Step 5   Generating AI brief with Gemini...")
        ai_brief = self.gemini_writer.generate(articles, market_data)
        if ai_brief:
            log.info(f"Step 5 ✓ AI brief: {len(ai_brief)} chars")
        else:
            log.warning("Step 5 ⚠ AI brief empty — using fallback")
            ai_brief = self.gemini_writer._fallback_brief(market_data)

        # Step 6: Write HTML
        output = self.html_writer.write(
            articles, market_data, ai_brief, self.output_path
        )
        log.info(f"Step 6 ✓ HTML written → {output}")

        # Step 7: Publish to GitHub → Cloudflare Pages
        if self.publish:
            log.info("Step 7   Publishing to GitHub...")
            ok = self.github.publish(output)
            if ok:
                log.info("Step 7 ✓ Published → xenosfinance.com/market-brief")
            else:
                log.warning("Step 7 ⚠ GitHub publish failed — HTML saved locally only")

        log.info("=" * 60)
        log.info("Pipeline complete ✓")
        log.info("=" * 60)
        return output
