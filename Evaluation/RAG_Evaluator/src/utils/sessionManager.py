# Session Manager for User-level File Separation
# This module handles unique session IDs and file mapping for multi-user support

import uuid
import time
import json
import os
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, base_output_dir: str = "outputs"):
        self.base_output_dir = base_output_dir
        self.sessions_file = os.path.join(base_output_dir, "sessions.json")
        self.sessions: Dict[str, dict] = {}
        self.lock = threading.RLock()
        self.load_sessions()
        
        # Create base output directory if it doesn't exist
        os.makedirs(base_output_dir, exist_ok=True)
    
    def create_session(self) -> str:
        """Create a new user session and return session ID"""
        with self.lock:
            session_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            
            session_data = {
                "session_id": session_id,
                "created_at": timestamp,
                "last_accessed": timestamp,
                "output_files": [],
                "status": "active",
                "user_ip": None,  # Can be set later
                "user_agent": None  # Can be set later
            }
            
            self.sessions[session_id] = session_data
            
            # Create user-specific directory
            session_dir = self.get_session_directory(session_id)
            os.makedirs(session_dir, exist_ok=True)
            
            self.save_sessions()
            logger.info(f"Created new session: {session_id}")
            return session_id
    
    def get_session_directory(self, session_id: str) -> str:
        """Get the directory path for a specific session"""
        return os.path.join(self.base_output_dir, f"session_{session_id}")
    
    def add_output_file(self, session_id: str, file_path: str) -> bool:
        """Add an output file to a session"""
        with self.lock:
            if session_id not in self.sessions:
                logger.error(f"Session not found: {session_id}")
                return False
            
            # Update last accessed time
            self.sessions[session_id]["last_accessed"] = datetime.now().isoformat()
            
            # Add file to session
            if file_path not in self.sessions[session_id]["output_files"]:
                self.sessions[session_id]["output_files"].append({
                    "file_path": file_path,
                    "created_at": datetime.now().isoformat(),
                    "file_size": os.path.getsize(file_path) if os.path.exists(file_path) else 0
                })
                
                self.save_sessions()
                logger.info(f"Added output file to session {session_id}: {file_path}")
                return True
            
            return False
    
    def get_session_files(self, session_id: str) -> List[dict]:
        """Get all output files for a session"""
        with self.lock:
            if session_id not in self.sessions:
                return []
            
            # Update last accessed time
            self.sessions[session_id]["last_accessed"] = datetime.now().isoformat()
            self.save_sessions()
            
            return self.sessions[session_id]["output_files"]
    
    def get_latest_file(self, session_id: str) -> Optional[str]:
        """Get the most recent output file for a session"""
        files = self.get_session_files(session_id)
        if not files:
            return None
        
        # Sort by creation time and return the latest
        latest_file = max(files, key=lambda f: f["created_at"])
        file_path = latest_file["file_path"]
        
        # Verify file still exists
        if os.path.exists(file_path):
            return file_path
        else:
            logger.warning(f"File not found: {file_path}")
            return None
    
    def is_valid_session(self, session_id: str) -> bool:
        """Check if a session ID is valid and active"""
        with self.lock:
            return session_id in self.sessions and self.sessions[session_id]["status"] == "active"
    
    def update_session_metadata(self, session_id: str, user_ip: str = None, user_agent: str = None):
        """Update session metadata with user information"""
        with self.lock:
            if session_id in self.sessions:
                if user_ip:
                    self.sessions[session_id]["user_ip"] = user_ip
                if user_agent:
                    self.sessions[session_id]["user_agent"] = user_agent
                
                self.sessions[session_id]["last_accessed"] = datetime.now().isoformat()
                self.save_sessions()
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Clean up old sessions and their files"""
        with self.lock:
            current_time = datetime.now()
            sessions_to_remove = []
            
            for session_id, session_data in self.sessions.items():
                last_accessed = datetime.fromisoformat(session_data["last_accessed"])
                age_hours = (current_time - last_accessed).total_seconds() / 3600
                
                if age_hours > max_age_hours:
                    sessions_to_remove.append(session_id)
            
            for session_id in sessions_to_remove:
                self.remove_session(session_id)
            
            logger.info(f"Cleaned up {len(sessions_to_remove)} old sessions")
            return len(sessions_to_remove)
    
    def remove_session(self, session_id: str):
        """Remove a session and clean up its files"""
        with self.lock:
            if session_id not in self.sessions:
                return
            
            session_data = self.sessions[session_id]
            
            # Remove output files
            for file_info in session_data["output_files"]:
                file_path = file_info["file_path"]
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"Removed file: {file_path}")
                except Exception as e:
                    logger.error(f"Error removing file {file_path}: {e}")
            
            # Remove session directory
            session_dir = self.get_session_directory(session_id)
            try:
                if os.path.exists(session_dir):
                    import shutil
                    shutil.rmtree(session_dir)
                    logger.info(f"Removed session directory: {session_dir}")
            except Exception as e:
                logger.error(f"Error removing session directory {session_dir}: {e}")
            
            # Remove from sessions
            del self.sessions[session_id]
            self.save_sessions()
            logger.info(f"Removed session: {session_id}")
    
    def get_session_stats(self) -> dict:
        """Get statistics about all sessions"""
        with self.lock:
            total_sessions = len(self.sessions)
            active_sessions = sum(1 for s in self.sessions.values() if s["status"] == "active")
            total_files = sum(len(s["output_files"]) for s in self.sessions.values())
            
            return {
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "total_files": total_files,
                "base_output_dir": self.base_output_dir
            }
    
    def save_sessions(self):
        """Save sessions to disk"""
        try:
            with open(self.sessions_file, 'w') as f:
                json.dump(self.sessions, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving sessions: {e}")
    
    def load_sessions(self):
        """Load sessions from disk"""
        try:
            if os.path.exists(self.sessions_file):
                with open(self.sessions_file, 'r') as f:
                    self.sessions = json.load(f)
                logger.info(f"Loaded {len(self.sessions)} sessions from disk")
            else:
                self.sessions = {}
                logger.info("No existing sessions file found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
            self.sessions = {}

# Global session manager instance
_session_manager = None

def get_session_manager() -> SessionManager:
    """Get the global session manager instance"""
    global _session_manager
    if _session_manager is None:
        # Use the outputs directory from the app structure
        output_dir = os.path.join(os.path.dirname(__file__), "../outputs")
        _session_manager = SessionManager(output_dir)
    return _session_manager

def create_user_session() -> str:
    """Convenience function to create a new user session"""
    return get_session_manager().create_session()

def get_user_session_directory(session_id: str) -> str:
    """Convenience function to get session directory"""
    return get_session_manager().get_session_directory(session_id)

def add_session_file(session_id: str, file_path: str) -> bool:
    """Convenience function to add file to session"""
    return get_session_manager().add_output_file(session_id, file_path)

def get_session_latest_file(session_id: str) -> Optional[str]:
    """Convenience function to get latest file for session"""
    return get_session_manager().get_latest_file(session_id)

def validate_session(session_id: str) -> bool:
    """Convenience function to validate session"""
    return get_session_manager().is_valid_session(session_id) 