#!/usr/bin/env python3
"""
XenosFinance Market Intelligence Agent
Run: PYTHONPATH=. python -B app/main.py
"""
import sys
import argparse
from app.pipeline import MarketIntelligencePipeline


def main():
    parser = argparse.ArgumentParser(description="XenosFinance Market Intelligence Agent")
    parser.add_argument("--output", "-o", default="site/market-brief.html",
                        help="Output HTML file (default: site/market-brief.html)")
    parser.add_argument("--no-publish", action="store_true",
                        help="Skip GitHub publish (local test only)")
    parser.add_argument("--serve", "-s", action="store_true",
                        help="Start HTTP server after generating (port 8000)")
    args = parser.parse_args()

    publish = not args.no_publish
    pipeline = MarketIntelligencePipeline(output_path=args.output, publish=publish)
    result   = pipeline.run()

    if not result:
        print("Pipeline failed.", file=sys.stderr)
        sys.exit(1)

    print(f"\n✓ Done: {result}")
    if not publish:
        print("  (GitHub publish skipped — local mode)")

    if args.serve:
        import http.server, socketserver, webbrowser
        PORT = 8000
        print(f"\n  Serving at http://localhost:{PORT}")
        webbrowser.open(f"http://localhost:{PORT}/{result}")
        with socketserver.TCPServer(("", PORT), http.server.SimpleHTTPRequestHandler) as httpd:
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nServer stopped.")


if __name__ == "__main__":
    main()
