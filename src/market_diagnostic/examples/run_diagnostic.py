#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Market Diagnostic System - Example Usage Script
================================================

Demonstrates how to use the MarketDiagnosticEngine directly and via
MarketAnalyzer with enable_diagnostic=True.

Usage
-----
Run with defaults (today's date, print Markdown to stdout):

    python run_diagnostic.py

Specify a date and save outputs:

    python run_diagnostic.py --date 2024-01-15 --output-json report.json --output-md report.md

Disable LLM narrative and enable verbose logging:

    python run_diagnostic.py --no-llm --verbose

Requirements: 21.8
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def _setup_logging(verbose: bool = False) -> None:
    """Configure root logger based on verbosity flag."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ---------------------------------------------------------------------------
# Example 1: Use MarketDiagnosticEngine directly
# ---------------------------------------------------------------------------

def example_direct_engine(
    date: Optional[str] = None,
    enable_llm: bool = True,
) -> tuple:
    """
    Demonstrate direct usage of MarketDiagnosticEngine.

    This is the lower-level approach that gives full control over the
    engine configuration.

    Parameters
    ----------
    date : str, optional
        Target date in 'YYYY-MM-DD' format. Defaults to today.
    enable_llm : bool
        Whether to enable LLM narrative generation.

    Returns
    -------
    tuple[DiagnosticReport, str]
        (structured_report, markdown_string)
    """
    logger = logging.getLogger(__name__)
    logger.info("=== Example 1: Direct MarketDiagnosticEngine usage ===")

    # Import the engine and its dependencies
    import sys
    from pathlib import Path
    
    # Add project root to path if needed
    project_root = Path(__file__).resolve().parents[3]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    from data_provider.base import DataFetcherManager
    from src.market_diagnostic.engine import MarketDiagnosticEngine

    # Initialize the data manager (reuses existing infrastructure)
    data_manager = DataFetcherManager()

    # Create the engine — pass analyzer=None to skip LLM narrative
    # or pass a GeminiAnalyzer instance to enable it
    engine = MarketDiagnosticEngine(
        data_manager=data_manager,
        analyzer=None,  # Replace with GeminiAnalyzer() to enable LLM narrative
        enable_llm_narrative=enable_llm,
    )

    # Run the diagnostic workflow
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    logger.info(f"Running diagnostic for date: {target_date}")

    report, markdown = engine.run(date=target_date)

    logger.info(
        f"Diagnostic complete — regime={report.composite_regime}, "
        f"confidence={report.confidence:.0%}, "
        f"missing_data={len(report.missing_data)} items"
    )

    return report, markdown


# ---------------------------------------------------------------------------
# Example 2: Use MarketAnalyzer with enable_diagnostic=True
# ---------------------------------------------------------------------------

def example_market_analyzer(
    date: Optional[str] = None,
    enable_llm: bool = True,
) -> tuple:
    """
    Demonstrate using MarketAnalyzer with enable_diagnostic=True.

    This is the higher-level approach that integrates with the existing
    MarketAnalyzer workflow.

    Parameters
    ----------
    date : str, optional
        Target date in 'YYYY-MM-DD' format. Defaults to today.
    enable_llm : bool
        Whether to enable LLM narrative generation.

    Returns
    -------
    tuple[Optional[DiagnosticReport], str]
        (structured_report_or_None, markdown_string)
    """
    logger = logging.getLogger(__name__)
    logger.info("=== Example 2: MarketAnalyzer with enable_diagnostic=True ===")

    import sys
    from pathlib import Path
    
    # Add project root to path if needed
    project_root = Path(__file__).resolve().parents[3]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from src.market_analyzer import MarketAnalyzer

    # Initialize MarketAnalyzer with diagnostic mode enabled
    # Pass analyzer=None to skip LLM; replace with GeminiAnalyzer() to enable
    analyzer = MarketAnalyzer(
        search_service=None,   # No news search in this example
        analyzer=None,         # Replace with GeminiAnalyzer() to enable LLM
        region="cn",
        enable_diagnostic=True,
    )

    # Disable LLM narrative if requested
    if not enable_llm and analyzer.diagnostic_engine is not None:
        analyzer.diagnostic_engine.enable_llm_narrative = False

    # run_full_analysis() returns (DiagnosticReport, markdown_str) in diagnostic mode
    report, markdown = analyzer.run_full_analysis()

    if report is not None:
        logger.info(
            f"MarketAnalyzer diagnostic complete — regime={report.composite_regime}, "
            f"confidence={report.confidence:.0%}"
        )
    else:
        logger.info("MarketAnalyzer returned non-diagnostic report (fallback mode)")

    return report, markdown


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _save_json(report, output_path: str) -> None:
    """Serialize DiagnosticReport to JSON and write to file."""
    logger = logging.getLogger(__name__)
    try:
        json_data = report.to_json()
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json_data, encoding="utf-8")
        logger.info(f"JSON report saved to: {path.resolve()}")
    except Exception as exc:
        logger.error(f"Failed to save JSON report: {exc}")


def _save_markdown(markdown: str, output_path: str) -> None:
    """Write Markdown report to file."""
    logger = logging.getLogger(__name__)
    try:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
        logger.info(f"Markdown report saved to: {path.resolve()}")
    except Exception as exc:
        logger.error(f"Failed to save Markdown report: {exc}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="run_diagnostic",
        description=(
            "Run the Market Diagnostic System for A-share market analysis.\n\n"
            "By default the Markdown report is printed to stdout. Use --output-json\n"
            "and --output-md to save reports to files."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run for today, print Markdown to stdout
  python run_diagnostic.py

  # Run for a specific date
  python run_diagnostic.py --date 2024-01-15

  # Save both JSON and Markdown reports
  python run_diagnostic.py --output-json report.json --output-md report.md

  # Disable LLM narrative and enable verbose logging
  python run_diagnostic.py --no-llm --verbose
""",
    )

    parser.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        default=None,
        help="Target trading date (default: today)",
    )
    parser.add_argument(
        "--output-json",
        metavar="PATH",
        default=None,
        help="Save JSON report to this file path",
    )
    parser.add_argument(
        "--output-md",
        metavar="PATH",
        default=None,
        help="Save Markdown report to this file path",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        default=False,
        help="Disable LLM narrative generation",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose (DEBUG) logging",
    )
    parser.add_argument(
        "--mode",
        choices=["engine", "analyzer"],
        default="engine",
        help=(
            "Which API to use: 'engine' for MarketDiagnosticEngine directly, "
            "'analyzer' for MarketAnalyzer with enable_diagnostic=True "
            "(default: engine)"
        ),
    )

    return parser


def main(argv: Optional[list] = None) -> int:
    """
    Main entry point for the CLI.

    Parameters
    ----------
    argv : list, optional
        Command-line arguments (defaults to sys.argv[1:]).

    Returns
    -------
    int
        Exit code (0 = success, 1 = error).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    _setup_logging(verbose=args.verbose)
    logger = logging.getLogger(__name__)

    # Validate date format if provided
    if args.date is not None:
        try:
            datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            logger.error(f"Invalid date format: '{args.date}'. Expected YYYY-MM-DD.")
            return 1

    enable_llm = not args.no_llm

    try:
        # Run the selected example
        if args.mode == "analyzer":
            report, markdown = example_market_analyzer(
                date=args.date,
                enable_llm=enable_llm,
            )
        else:
            report, markdown = example_direct_engine(
                date=args.date,
                enable_llm=enable_llm,
            )

        # Save JSON report if requested
        if args.output_json and report is not None:
            _save_json(report, args.output_json)

        # Save Markdown report if requested
        if args.output_md:
            _save_markdown(markdown, args.output_md)

        # Always print Markdown to stdout
        print(markdown)

        return 0

    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        return 130
    except Exception as exc:
        logger.error(f"Diagnostic run failed: {exc}", exc_info=args.verbose)
        return 1


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())
