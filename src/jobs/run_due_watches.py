"""Entry point for Azure Container Apps Job.

Finds active due watches and creates placeholder WatchRuns.

Usage:
    python -m src.jobs.run_due_watches

Environment variables:
    DATABASE_URL    PostgreSQL connection string (required)
    WATCH_CADENCE   Optional cadence filter (morning|afternoon|daily|twice_daily|weekly|monthly)
"""
import asyncio
import logging
import os

from src.db.models.watch import WatchCadence
from src.db.session import AsyncSessionLocal
from src.services.watch_service import WatchService

logger = logging.getLogger(__name__)


async def run() -> None:
    cadence_str = os.environ.get("WATCH_CADENCE")
    cadence: WatchCadence | None = None
    if cadence_str:
        try:
            cadence = WatchCadence(cadence_str)
            logger.info(f"Filtering to cadence: {cadence.value}")
        except ValueError:
            logger.warning(
                f"Invalid WATCH_CADENCE value '{cadence_str}', processing all due watches"
            )

    async with AsyncSessionLocal() as session:
        service = WatchService(db=session)

        due_result = await service.list_due_watches(cadence=cadence)
        if not due_result.success:
            logger.error(f"Failed to list due watches: {due_result.message}")
            return

        watches = due_result.watches
        logger.info(f"Found {len(watches)} due watches to process")

        processed = 0
        failed = 0

        for watch in watches:
            try:
                start_result = await service.start_watch_run(watch_id=watch.id)
                if not start_result.success:
                    logger.error(
                        f"Failed to start run for watch {watch.id}: {start_result.message}"
                    )
                    failed += 1
                    continue

                run_id = start_result.watch_run.id
                complete_result = await service.complete_watch_run(
                    run_id=run_id,
                    summary=(
                        "Scheduled watch evaluation placeholder — "
                        "AI evaluation not yet implemented"
                    ),
                )
                if not complete_result.success:
                    logger.error(f"Failed to complete run {run_id}: {complete_result.message}")
                    failed += 1
                    continue

                logger.info(
                    f"Completed placeholder run {run_id} for watch {watch.id} ({watch.name})"
                )
                processed += 1

            except Exception as e:
                logger.error(
                    f"Unexpected error processing watch {watch.id}: {e}", exc_info=True
                )
                failed += 1

        logger.info(
            f"Job complete: {processed} processed, {failed} failed "
            f"out of {len(watches)} due watches"
        )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(run())
