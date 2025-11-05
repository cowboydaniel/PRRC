"""
Shared schemas and data structures for PRRC OS Suite.

This module provides standardized enums and conversion functions for data
exchanged between HQ Command and FieldOps components.
"""

from enum import Enum
from typing import Union


class Priority(str, Enum):
    """
    Standard priority levels for tasks and operations.

    This enum provides a consistent priority representation across both
    HQ Command (which uses integers 1-5) and FieldOps (which uses strings).
    """
    ROUTINE = "Routine"
    HIGH = "High"
    CRITICAL = "Critical"


class TaskPriority:
    """
    Standardized priority mapping between HQ Command (int) and FieldOps (string).

    HQ Command uses integer priorities 1-5:
    - 1-2: Routine
    - 3-4: High
    - 5: Critical

    FieldOps uses string priorities:
    - "Routine": Low priority tasks
    - "High": Urgent tasks requiring attention
    - "Critical": Emergency tasks requiring immediate action
    """

    # Integer to Priority enum mapping (HQ Command -> Standard)
    INT_TO_PRIORITY = {
        1: Priority.ROUTINE,
        2: Priority.ROUTINE,
        3: Priority.HIGH,
        4: Priority.HIGH,
        5: Priority.CRITICAL,
    }

    # Priority enum to string mapping (Standard -> FieldOps)
    PRIORITY_TO_STRING = {
        Priority.ROUTINE: "Routine",
        Priority.HIGH: "High",
        Priority.CRITICAL: "Critical",
    }

    # String to Priority enum mapping (FieldOps -> Standard)
    STRING_TO_PRIORITY = {
        "Routine": Priority.ROUTINE,
        "routine": Priority.ROUTINE,
        "High": Priority.HIGH,
        "high": Priority.HIGH,
        "Critical": Priority.CRITICAL,
        "critical": Priority.CRITICAL,
    }

    # Priority enum to integer mapping (Standard -> HQ Command)
    # Maps to the highest value for each priority level
    PRIORITY_TO_INT = {
        Priority.ROUTINE: 2,
        Priority.HIGH: 4,
        Priority.CRITICAL: 5,
    }


def priority_to_int(priority: Union[str, Priority, int]) -> int:
    """
    Convert any priority representation to HQ Command integer format.

    Args:
        priority: Priority as string, Priority enum, or int

    Returns:
        Integer priority (1-5), defaults to 3 (High) if invalid

    Examples:
        >>> priority_to_int("Routine")
        2
        >>> priority_to_int(Priority.HIGH)
        4
        >>> priority_to_int(5)
        5
    """
    # Already an int
    if isinstance(priority, int):
        if 1 <= priority <= 5:
            return priority
        return 3  # Default to High

    # Priority enum
    if isinstance(priority, Priority):
        return TaskPriority.PRIORITY_TO_INT[priority]

    # String
    if isinstance(priority, str):
        priority_enum = TaskPriority.STRING_TO_PRIORITY.get(priority)
        if priority_enum:
            return TaskPriority.PRIORITY_TO_INT[priority_enum]

    # Default to High priority
    return 3


def priority_to_string(priority: Union[str, Priority, int]) -> str:
    """
    Convert any priority representation to FieldOps string format.

    Args:
        priority: Priority as string, Priority enum, or int

    Returns:
        String priority ("Routine", "High", "Critical"), defaults to "High" if invalid

    Examples:
        >>> priority_to_string(1)
        'Routine'
        >>> priority_to_string(Priority.CRITICAL)
        'Critical'
        >>> priority_to_string("high")
        'High'
    """
    # Already a string in the correct format
    if isinstance(priority, str):
        priority_enum = TaskPriority.STRING_TO_PRIORITY.get(priority)
        if priority_enum:
            return TaskPriority.PRIORITY_TO_STRING[priority_enum]
        return "High"  # Default

    # Priority enum
    if isinstance(priority, Priority):
        return TaskPriority.PRIORITY_TO_STRING[priority]

    # Integer
    if isinstance(priority, int):
        priority_enum = TaskPriority.INT_TO_PRIORITY.get(priority)
        if priority_enum:
            return TaskPriority.PRIORITY_TO_STRING[priority_enum]

    # Default to High priority
    return "High"


def validate_priority(priority: Union[str, Priority, int]) -> bool:
    """
    Validate if a priority value is valid.

    Args:
        priority: Priority to validate

    Returns:
        True if valid, False otherwise

    Examples:
        >>> validate_priority(3)
        True
        >>> validate_priority("Routine")
        True
        >>> validate_priority("invalid")
        False
        >>> validate_priority(10)
        False
    """
    if isinstance(priority, Priority):
        return True

    if isinstance(priority, int):
        return 1 <= priority <= 5

    if isinstance(priority, str):
        return priority in TaskPriority.STRING_TO_PRIORITY

    return False
