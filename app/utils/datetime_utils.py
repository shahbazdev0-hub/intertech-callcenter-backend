# backend/app/utils/datetime_utils.py
from datetime import datetime, timezone
from typing import Optional, Union
from fastapi import HTTPException, status


def parse_iso_datetime(date_string: str) -> datetime:
    """
    Parse ISO datetime string, handling various formats including Z suffix
    
    Args:
        date_string: ISO datetime string (e.g., "2025-09-25T16:10:04.058Z" or "2025-09-25T16:10:04+00:00")
    
    Returns:
        datetime object
        
    Raises:
        HTTPException: If the date format is invalid
    """
    if not date_string:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date string cannot be empty"
        )
    
    try:
        # Handle Z suffix (UTC timezone)
        if date_string.endswith('Z'):
            date_string = date_string[:-1] + '+00:00'
        
        # Parse the datetime
        parsed_date = datetime.fromisoformat(date_string)
        
        # Ensure timezone awareness (convert to UTC if naive)
        if parsed_date.tzinfo is None:
            parsed_date = parsed_date.replace(tzinfo=timezone.utc)
        
        return parsed_date
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format: '{date_string}'. Expected ISO format (e.g., '2025-09-25T16:10:04Z' or '2025-09-25T16:10:04+00:00'). Error: {str(e)}"
        )


def parse_optional_datetime(date_string: Optional[str]) -> Optional[datetime]:
    """
    Parse optional ISO datetime string
    
    Args:
        date_string: Optional ISO datetime string
    
    Returns:
        datetime object or None if date_string is None/empty
    """
    if not date_string or date_string.strip() == "":
        return None
    
    return parse_iso_datetime(date_string.strip())


def datetime_to_iso_string(dt: datetime) -> str:
    """
    Convert datetime to ISO string format
    
    Args:
        dt: datetime object
    
    Returns:
        ISO formatted datetime string
    """
    if dt is None:
        return None
    
    # Ensure timezone awareness
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    return dt.isoformat()


def format_datetime_response(dt: Union[datetime, str, None]) -> Optional[str]:
    """
    Format datetime for API response
    
    Args:
        dt: datetime object, ISO string, or None
    
    Returns:
        ISO formatted datetime string or None
    """
    if dt is None:
        return None
    
    if isinstance(dt, str):
        try:
            dt = parse_iso_datetime(dt)
        except HTTPException:
            return None
    
    return datetime_to_iso_string(dt)


def get_current_utc_datetime() -> datetime:
    """Get current UTC datetime with timezone info"""
    return datetime.now(timezone.utc)


def validate_date_range(from_date: Optional[str], to_date: Optional[str]) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Validate and parse date range parameters
    
    Args:
        from_date: Optional start date string
        to_date: Optional end date string
    
    Returns:
        Tuple of (parsed_from_date, parsed_to_date)
        
    Raises:
        HTTPException: If dates are invalid or range is invalid
    """
    parsed_from_date = parse_optional_datetime(from_date)
    parsed_to_date = parse_optional_datetime(to_date)
    
    # Validate date range
    if parsed_from_date and parsed_to_date:
        if parsed_from_date >= parsed_to_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'from_date' must be earlier than 'to_date'"
            )
    
    return parsed_from_date, parsed_to_date


def format_duration(seconds: Optional[int]) -> str:
    """
    Format duration in seconds to human readable format
    
    Args:
        seconds: Duration in seconds
    
    Returns:
        Formatted duration string (e.g., "2m 30s", "1h 15m")
    """
    if not seconds or seconds <= 0:
        return "0s"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining_seconds = seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if remaining_seconds > 0 or not parts:
        parts.append(f"{remaining_seconds}s")
    
    return " ".join(parts)