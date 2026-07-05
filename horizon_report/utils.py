"""Utility functions for the Horizon report system."""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


def setup_logging(log_path: Optional[Path] = None, console_level: int = logging.INFO) -> logging.Logger:
    """Set up logging configuration.
    
    Args:
        log_path: Optional path to log file
        console_level: Logging level for console output
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("horizon_report")
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler if path provided
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    
    return logger


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def normalize_column_name(name: str) -> str:
    """Normalize column names for consistent parsing.
    
    Args:
        name: Raw column name
        
    Returns:
        Normalized column name
    """
    if not isinstance(name, str):
        return ""
    
    # Convert to lowercase and strip
    normalized = name.lower().strip()
    
    # Remove special characters
    normalized = ''.join(c if c.isalnum() or c == '_' else '_' for c in normalized)
    
    # Remove consecutive underscores
    while '__' in normalized:
        normalized = normalized.replace('__', '_')
    
    return normalized.strip('_')


def detect_file_relevance(file_path: Path) -> str:
    """Detect why a file might be relevant.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Relevance description
    """
    name_lower = file_path.name.lower()
    stem_lower = file_path.stem.lower()
    
    # Check for common patterns
    if 'runsheet' in name_lower or 'run_sheet' in name_lower or 'run sheet' in name_lower:
        return "Likely runsheet"
    
    if 'ownership' in name_lower or 'owner' in name_lower:
        return "Likely ownership document"
    
    if 'template' in name_lower:
        return "Likely template"
    
    if 'deed' in name_lower:
        return "Likely deed document"
    
    if 'lease' in name_lower:
        return "Likely lease document"
    
    if 'title' in name_lower:
        return "Likely title report"
    
    if 'chain' in name_lower:
        return "Likely chain of title"
    
    if 'report' in name_lower:
        return "Prior report"
    
    if any(ext in name_lower for ext in ['ogl', 'mineral', 'interest']):
        return "Likely mineral interest data"
    
    return "Source document"


def is_likely_runsheet(file_path: Path) -> bool:
    """Check if file is likely a runsheet.
    
    Args:
        file_path: Path to check
        
    Returns:
        True if likely a runsheet
    """
    name_lower = file_path.name.lower()
    return any(term in name_lower for term in ['runsheet', 'run_sheet', 'run sheet', 'ogl'])


def is_likely_template(file_path: Path) -> bool:
    """Check if file is likely a template.
    
    Args:
        file_path: Path to check
        
    Returns:
        True if likely a template
    """
    name_lower = file_path.name.lower()
    return 'template' in name_lower or 'blank' in name_lower


def get_timestamp() -> str:
    """Get current timestamp string for filenames.
    
    Returns:
        Timestamp string in format YYYY-MM-DD_HH-MM-SS
    """
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def safe_filename(filename: str) -> str:
    """Make a filename safe by removing invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Safe filename
    """
    # Remove or replace invalid characters
    invalid_chars = '<>:"|?*\\'
    safe = filename
    for char in invalid_chars:
        safe = safe.replace(char, '_')
    
    # Remove leading/trailing dots and spaces
    safe = safe.strip('. ')
    
    # Limit length
    if len(safe) > 200:
        name, ext = safe.rsplit('.', 1) if '.' in safe else (safe, '')
        safe = name[:190] + ('.' + ext if ext else '')
    
    return safe or "unnamed"


def print_table(headers: list, rows: list, title: Optional[str] = None) -> None:
    """Print a formatted table to console.
    
    Args:
        headers: List of column headers
        rows: List of row data (each row is a list matching headers)
        title: Optional table title
    """
    if not headers or not rows:
        return
    
    # Calculate column widths
    col_widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))
    
    # Create format string
    row_format = " | ".join(f"{{:<{w}}}" for w in col_widths)
    separator = "-+-".join("-" * w for w in col_widths)
    
    # Print table
    if title:
        print(f"\n{title}")
        print("=" * len(title))
    
    print(row_format.format(*headers))
    print(separator)
    
    for row in rows:
        # Pad row if needed
        padded_row = list(row) + [''] * (len(headers) - len(row))
        print(row_format.format(*padded_row))
    
    print()


def parse_section_string(section_str: str) -> dict:
    """Parse section string like '31-12N-24W' into components.
    
    Args:
        section_str: Section string
        
    Returns:
        Dictionary with section, township, range
    """
    result = {"section": "", "township": "", "range": ""}
    
    if not section_str:
        return result
    
    parts = section_str.strip().split('-')
    if len(parts) >= 1:
        result["section"] = parts[0].strip()
    if len(parts) >= 2:
        result["township"] = parts[1].strip()
    if len(parts) >= 3:
        result["range"] = parts[2].strip()
    
    return result
