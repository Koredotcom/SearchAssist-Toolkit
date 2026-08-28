# Cleanup Scheduler for Session Management
# This module provides automated cleanup of old session files

import asyncio
import schedule
import time
import threading
import logging
from datetime import datetime
from utils.sessionManager import get_session_manager

logger = logging.getLogger(__name__)

class CleanupScheduler:
    def __init__(self, cleanup_interval_hours: int = 24, max_session_age_hours: int = 24):
        self.cleanup_interval_hours = cleanup_interval_hours
        self.max_session_age_hours = max_session_age_hours
        self.running = False
        self.scheduler_thread = None
        
    def cleanup_old_sessions(self):
        """Perform cleanup of old sessions"""
        try:
            session_manager = get_session_manager()
            cleaned_count = session_manager.cleanup_old_sessions(self.max_session_age_hours)
            
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[{current_time}] Cleanup completed: removed {cleaned_count} old sessions")
            
            return cleaned_count
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return 0
    
    def start_scheduler(self):
        """Start the cleanup scheduler in a separate thread"""
        if self.running:
            logger.warning("Cleanup scheduler is already running")
            return
        
        self.running = True
        
        # Schedule cleanup every N hours
        schedule.every(self.cleanup_interval_hours).hours.do(self.cleanup_old_sessions)
        
        # Run an initial cleanup
        initial_cleaned = self.cleanup_old_sessions()
        logger.info(f"Initial cleanup completed: {initial_cleaned} sessions removed")
        
        def run_scheduler():
            logger.info(f"Starting cleanup scheduler: every {self.cleanup_interval_hours} hours, max age {self.max_session_age_hours} hours")
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            logger.info("Cleanup scheduler stopped")
        
        self.scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("Cleanup scheduler started successfully")
    
    def stop_scheduler(self):
        """Stop the cleanup scheduler"""
        if not self.running:
            logger.warning("Cleanup scheduler is not running")
            return
        
        self.running = False
        schedule.clear()
        
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        
        logger.info("Cleanup scheduler stopped")
    
    def get_status(self) -> dict:
        """Get the current status of the scheduler"""
        return {
            "running": self.running,
            "cleanup_interval_hours": self.cleanup_interval_hours,
            "max_session_age_hours": self.max_session_age_hours,
            "scheduled_jobs": len(schedule.jobs),
            "next_run": str(schedule.next_run()) if schedule.jobs else "No jobs scheduled"
        }

# Global scheduler instance
_cleanup_scheduler = None

def get_cleanup_scheduler() -> CleanupScheduler:
    """Get the global cleanup scheduler instance"""
    global _cleanup_scheduler
    if _cleanup_scheduler is None:
        _cleanup_scheduler = CleanupScheduler()
    return _cleanup_scheduler

def start_cleanup_scheduler(cleanup_interval_hours: int = 24, max_session_age_hours: int = 24):
    """Start the global cleanup scheduler"""
    scheduler = get_cleanup_scheduler()
    scheduler.cleanup_interval_hours = cleanup_interval_hours
    scheduler.max_session_age_hours = max_session_age_hours
    scheduler.start_scheduler()

def stop_cleanup_scheduler():
    """Stop the global cleanup scheduler"""
    scheduler = get_cleanup_scheduler()
    scheduler.stop_scheduler()

def manual_cleanup() -> int:
    """Manually trigger a cleanup and return the number of sessions cleaned"""
    scheduler = get_cleanup_scheduler()
    return scheduler.cleanup_old_sessions() 