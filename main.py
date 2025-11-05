#!/usr/bin/env python
"""
AG2 Agent Network - CLI Entry Point
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional
import argparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agent_network import ParallelAgentNetwork, LLMConfig as AG2LLMConfig
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_config() -> Config:
    """Load configuration from environment."""
    return Config()


def create_llm_config(cfg: Config) -> AG2LLMConfig:
    """Create AG2 LLMConfig from Config object."""
    return AG2LLMConfig(
        model=cfg.llm.model,
        api_key=cfg.llm.api_key,
        api_base=cfg.llm.api_base,
        temperature=cfg.llm.temperature,
        timeout=cfg.llm.timeout,
    )


async def run_workflow(
    task: str,
    docs_path: str = "./docs",
    max_workers: int = 3,
    output_file: Optional[str] = None
) -> None:
    """Execute the agent network workflow."""
    try:
        config = load_config()
        llm_config = create_llm_config(config)

        logger.info(f"Initializing Agent Network")
        logger.info(f"  Provider: {config.llm.provider}")
        logger.info(f"  Model: {config.llm.model}")
        logger.info(f"  Workers: {max_workers}")

        network = ParallelAgentNetwork(
            llm_config=llm_config,
            max_workers=max_workers,
        )

        logger.info(f"Setting up teams...")
        network.setup_teams(task, docs_base_path=docs_path)

        logger.info(f"Executing {len(network.teams)} parallel teams...")
        results = await network.execute_parallel(task)

        logger.info(f"\nParallel Execution Complete:")
        for r in results:
            status = "✅" if r.success else "❌"
            print(f"  {status} {r.team_name}: {r.duration:.2f}s")

        logger.info(f"Starting refinement loop...")
        refinement = network.execute_refinement_loop(results)

        report = network.generate_report()
        report["refinement"] = refinement["refinement_output"]

        if output_file:
            with open(output_file, "w") as f:
                json.dump(report, f, indent=2)
            logger.info(f"Report saved to {output_file}")
        else:
            print(json.dumps(report, indent=2))

    except Exception as e:
        logger.error(f"Workflow failed: {str(e)}", exc_info=True)
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="AG2 Parallel Agent Network"
    )
    parser.add_argument(
        "task",
        help="Task description for agent network"
    )
    parser.add_argument(
        "--docs-path",
        default="./docs",
        help="Path to documentation for RAG"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Number of parallel workers"
    )
    parser.add_argument(
        "--output",
        help="Output file for report (JSON)"
    )
    parser.add_argument(
        "--config",
        help="Custom config file path"
    )

    args = parser.parse_args()

    asyncio.run(run_workflow(
        task=args.task,
        docs_path=args.docs_path,
        max_workers=args.workers,
        output_file=args.output,
    ))


if __name__ == "__main__":
    main()
