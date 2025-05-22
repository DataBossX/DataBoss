"""
System Monitor for DataBoss
Monitors system health and performance
"""

import os
import sys
import json
import time
import logging
import psutil
import platform
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("databoss.system_monitor")
logging.basicConfig(level=logging.INFO)

class SystemMonitor:
    def __init__(self, log_dir: str = "logs", check_interval: int = 300):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.check_interval = check_interval
        self.running = False
        
    def start(self):
        """Start system monitoring"""
        self.running = True
        logger.info("System Monitor started")
        
        while self.running:
            self.check_system_health()
            time.sleep(self.check_interval)
            
    def stop(self):
        """Stop system monitoring"""
        self.running = False
        logger.info("System Monitor stopped")
        
    def check_system_health(self):
        """Check system health and log results"""
        try:
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "cpu": {
                    "percent": psutil.cpu_percent(interval=1),
                    "count": psutil.cpu_count(),
                    "load_avg": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
                },
                "memory": {
                    "total": psutil.virtual_memory().total,
                    "available": psutil.virtual_memory().available,
                    "percent": psutil.virtual_memory().percent
                },
                "disk": {
                    "total": psutil.disk_usage('/').total,
                    "free": psutil.disk_usage('/').free,
                    "percent": psutil.disk_usage('/').percent
                },
                "network": {
                    "connections": len(psutil.net_connections())
                },
                "processes": {
                    "total": len(psutil.pids()),
                    "databoss_processes": self._count_databoss_processes()
                },
                "system": {
                    "platform": platform.system(),
                    "release": platform.release(),
                    "python_version": platform.python_version()
                }
            }
            
            warnings = []
            if metrics["cpu"]["percent"] > 80:
                warnings.append("High CPU usage")
                
            if metrics["memory"]["percent"] > 80:
                warnings.append("High memory usage")
                
            if metrics["disk"]["percent"] > 80:
                warnings.append("Low disk space")
                
            metrics["warnings"] = warnings
            metrics["status"] = "warning" if warnings else "healthy"
            
            self._log_metrics(metrics)
            
            if warnings:
                self._handle_warnings(metrics, warnings)
                
            logger.info(f"System health check completed: {metrics['status']}")
            
        except Exception as e:
            logger.error(f"System health check failed: {str(e)}", exc_info=True)
            
    def _count_databoss_processes(self) -> int:
        """Count DataBoss-related processes"""
        count = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and any(x for x in cmdline if 'databoss' in str(x).lower() or 'streamlit' in str(x).lower()):
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return count
        
    def _log_metrics(self, metrics: Dict[str, Any]):
        """Log system metrics to file"""
        try:
            log_file = self.log_dir / f"system_health_{datetime.now().strftime('%Y%m%d')}.json"
            
            existing_data = []
            if log_file.exists():
                with open(log_file, "r") as f:
                    existing_data = json.load(f)
                    
            existing_data.append(metrics)
            
            with open(log_file, "w") as f:
                json.dump(existing_data, f, indent=2)
                
        except Exception as e: 
            logger.error(f"Failed to log metrics: {str(e)}")
            
    def _handle_warnings(self, metrics: Dict[str, Any], warnings: List[str]):
        """Handle system warnings"""
        warning_log = {
            "timestamp": datetime.now().isoformat(),
            "warnings": warnings,
            "metrics": metrics
        }
        
        warning_file = self.log_dir / "system_warnings.json"
        
        try:
            if "High CPU usage" in warnings:
                logger.warning("High CPU usage detected")
                
            if "High memory usage" in warnings:
                logger.warning("High memory usage detected")
                
            if "Low disk space" in warnings:
                self._cleanup_old_logs()
                logger.warning("Low disk space detected, cleaned up old logs")
                
            with open(warning_file, "w") as f:
                json.dump(warning_log, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to handle warnings: {str(e)}")
            
    def _cleanup_old_logs(self):
        """Clean up old log files to free disk space"""
        try:
            current_time = time.time()
            for log_file in self.log_dir.glob("*.json"):
                file_age = current_time - log_file.stat().st_mtime
                if file_age > 7 * 24 * 60 * 60:  # 7 days in seconds
                    log_file.unlink()
                    logger.info(f"Deleted old log file: {log_file}")
        except Exception as e:
            logger.error(f"Failed to clean up logs: {str(e)}")
