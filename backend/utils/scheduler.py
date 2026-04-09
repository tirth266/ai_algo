"""
Task Scheduler for Daily Trading Lifecycle
Handles automated scheduling of trading system tasks using APScheduler.
"""

import logging
import os
from datetime import datetime, time
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor

logger = logging.getLogger(__name__)


class TradingScheduler:
    """
    Scheduler for automated trading lifecycle tasks.

    Manages:
    - Pre-market tasks (login, WebSocket init, position loading)
    - Market open (start trading)
    - Market close (stop new trades)
    - Post-market (position squaring, reporting)
    - End of day (log saving, notifications)
    """

    def __init__(self):
        """Initialize the trading scheduler."""
        # Configure executors
        executors = {
            "default": ThreadPoolExecutor(20),
            "processpool": ProcessPoolExecutor(5),
        }

        # Job defaults
        job_defaults = {
            "coalesce": False,  # Don't combine missed executions
            "max_instances": 1,  # Only one instance of each job at a time
        }

        self.scheduler = BackgroundScheduler(
            executors=executors,
            job_defaults=job_defaults,
            timezone="Asia/Kolkata",  # IST timezone
        )

        self._is_running = False
        self._initialized = False

        logger.info("TradingScheduler initialized")

    def start(self):
        """Start the scheduler."""
        if self._is_running:
            logger.warning("Scheduler is already running")
            return

        try:
            self.scheduler.start()
            self._is_running = True
            logger.info("TradingScheduler started successfully")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise

    def shutdown(self, wait: bool = True):
        """Shutdown the scheduler."""
        if not self._is_running:
            logger.warning("Scheduler is not running")
            return

        try:
            self.scheduler.shutdown(wait=wait)
            self._is_running = False
            logger.info("TradingScheduler shutdown complete")
        except Exception as e:
            logger.error(f"Error during scheduler shutdown: {e}")

    def add_pre_market_job(self, func, job_id: str = "pre_market_tasks"):
        """
        Add pre-market job to run at 9:00 AM IST.

        Args:
            func: Function to execute (login, WebSocket init, load positions)
            job_id: Unique identifier for the job
        """
        try:
            trigger = CronTrigger(hour=9, minute=0, second=0, timezone="Asia/Kolkata")

            self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                name="Pre-market Tasks",
                replace_existing=True,
            )

            logger.info(f"Added pre-market job: {job_id}")
        except Exception as e:
            logger.error(f"Failed to add pre-market job: {e}")
            raise

    def add_market_open_job(self, func, job_id: str = "market_open"):
        """
        Add market open job to run at 9:15 AM IST.

        Args:
            func: Function to execute (start trading engine)
            job_id: Unique identifier for the job
        """
        try:
            trigger = CronTrigger(hour=9, minute=15, second=0, timezone="Asia/Kolkata")

            self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                name="Market Open - Start Trading",
                replace_existing=True,
            )

            logger.info(f"Added market open job: {job_id}")
        except Exception as e:
            logger.error(f"Failed to add market open job: {e}")
            raise

    def add_market_close_job(self, func, job_id: str = "market_close"):
        """
        Add market close job to run at 3:30 PM IST.

        Args:
            func: Function to execute (stop new trades)
            job_id: Unique identifier for the job
        """
        try:
            trigger = CronTrigger(hour=15, minute=30, second=0, timezone="Asia/Kolkata")

            self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                name="Market Close - Stop New Trades",
                replace_existing=True,
            )

            logger.info(f"Added market close job: {job_id}")
        except Exception as e:
            logger.error(f"Failed to add market close job: {e}")
            raise

    def add_post_market_job(self, func, job_id: str = "post_market_tasks"):
        """
        Add post-market job to run at 3:35 PM IST.

        Args:
            func: Function to execute (square off positions, generate report)
            job_id: Unique identifier for the job
        """
        try:
            trigger = CronTrigger(hour=15, minute=35, second=0, timezone="Asia/Kolkata")

            self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                name="Post-market Tasks",
                replace_existing=True,
            )

            logger.info(f"Added post-market job: {job_id}")
        except Exception as e:
            logger.error(f"Failed to add post-market job: {e}")
            raise

    def add_end_of_day_job(self, func, job_id: str = "end_of_day_tasks"):
        """
        Add end of day job to run at 4:00 PM IST.

        Args:
            func: Function to execute (save logs, send summary)
            job_id: Unique identifier for the job
        """
        try:
            trigger = CronTrigger(hour=16, minute=0, second=0, timezone="Asia/Kolkata")

            self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                name="End of Day Tasks",
                replace_existing=True,
            )

            logger.info(f"Added end of day job: {job_id}")
        except Exception as e:
            logger.error(f"Failed to add end of day job: {e}")
            raise

    def remove_job(self, job_id: str):
        """
        Remove a job by its ID.

        Args:
            job_id: ID of the job to remove
        """
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job: {job_id}")
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")

    def get_jobs(self):
        """
        Get list of all scheduled jobs.

        Returns:
            List of job dictionaries
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time,
                    "trigger": str(job.trigger),
                }
            )
        return jobs

    def is_running(self) -> bool:
        """
        Check if scheduler is running.

        Returns:
            True if scheduler is running, False otherwise
        """
        return self._is_running


# Global scheduler instance
_trading_scheduler: Optional[TradingScheduler] = None


def get_trading_scheduler() -> TradingScheduler:
    """
    Get or create the global trading scheduler instance.

    Returns:
        TradingScheduler instance
    """
    global _trading_scheduler

    if _trading_scheduler is None:
        _trading_scheduler = TradingScheduler()

    return _trading_scheduler


def initialize_scheduler():
    """Initialize and start the trading scheduler."""
    scheduler = get_trading_scheduler()
    if not scheduler.is_running():
        scheduler.start()
    return scheduler


def shutdown_scheduler():
    """Shutdown the trading scheduler."""
    scheduler = get_trading_scheduler()
    if scheduler.is_running():
        scheduler.shutdown()


if __name__ == "__main__":
    # Example usage and testing
    import time

    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Define example task functions
    def pre_market_tasks():
        logger.info("Executing pre-market tasks: Login, WebSocket init, Load positions")
        # In real implementation:
        # 1. Login to broker using auth_manager
        # 2. Initialize WebSocket connection
        # 3. Load positions from broker/database

    def market_open_start():
        logger.info("Executing market open task: Start trading engine")
        # In real implementation:
        # Start the trading engine/system

    def market_close_stop():
        logger.info("Executing market close task: Stop new trades")
        # In real implementation:
        # Signal trading engine to stop opening new trades

    def post_market_tasks():
        logger.info(
            "Executing post-market tasks: Square off positions, Generate report"
        )
        # In real implementation:
        # 1. Square off any intraday positions
        # 2. Generate daily performance report

    def end_of_day_tasks():
        logger.info("Executing end of day tasks: Save logs, Send summary")
        # In real implementation:
        # 1. Save logs to persistent storage
        # 2. Send summary via Telegram/email

    # Initialize scheduler
    scheduler = initialize_scheduler()

    # Add jobs
    scheduler.add_pre_market_job(pre_market_tasks)
    scheduler.add_market_open_job(market_open_start)
    scheduler.add_market_close_job(market_close_stop)
    scheduler.add_post_market_job(post_market_tasks)
    scheduler.add_end_of_day_job(end_of_day_tasks)

    # Display scheduled jobs
    logger.info("Scheduled jobs:")
    for job in scheduler.get_jobs():
        logger.info(
            f"  - {job['name']} (ID: {job['id']}) - Next run: {job['next_run_time']}"
        )

    try:
        # Keep the scheduler running
        logger.info("Scheduler running. Press Ctrl+C to exit.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down scheduler...")
        shutdown_scheduler()
        logger.info("Scheduler shutdown complete.")
