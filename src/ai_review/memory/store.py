"""
ReviewMemory - Manages review memory file with warnings, suppression, decay, and reminders.
"""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path


@dataclass
class WarningRecord:
    """
    Records a warning that has appeared during code review.
    """
    rule_id: str
    first_seen: str          # ISO timestamp
    count: int               # How many times this warning appeared
    remind_count: int        # How many times reminded to developer
    remind_state: str        # "full" | "short" | "minimal" | "suppressed" | "manual_suppress"
    last_message: str        # Last warning message shown

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'WarningRecord':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class SuppressRecord:
    """
    Records a warning that has been suppressed.
    """
    rule_id: str
    reason: str
    suppressed_at: str       # ISO timestamp
    suppressed_by: str       # "manual"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'SuppressRecord':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class FileMemory:
    """
    Memory state for a specific file.
    """
    pending_warnings: List[WarningRecord]
    suppressed: List[SuppressRecord]
    risk_score: int          # 0-10
    last_reviewed: str       # ISO timestamp

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "pending_warnings": [w.to_dict() for w in self.pending_warnings],
            "suppressed": [s.to_dict() for s in self.suppressed],
            "risk_score": self.risk_score,
            "last_reviewed": self.last_reviewed
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'FileMemory':
        """Create from dictionary."""
        return cls(
            pending_warnings=[WarningRecord.from_dict(w) for w in data.get("pending_warnings", [])],
            suppressed=[SuppressRecord.from_dict(s) for s in data.get("suppressed", [])],
            risk_score=data.get("risk_score", 0),
            last_reviewed=data.get("last_reviewed", datetime.now().isoformat())
        )


class ReviewMemory:
    """
    Manages the review memory file (.ai-review/memory.json) with persistence,
    warning decay, suppression, and reminder strategies.
    """

    def __init__(self, memory_path: str = ".ai-review/memory.json"):
        """
        Initialize the memory system.

        Args:
            memory_path: Path to the memory JSON file
        """
        self.path = memory_path
        self.data = self._load()

    def record_warnings(self, file_path: str, warnings: List[dict]) -> None:
        """
        Record async review warnings for a file. Increment count if same rule already exists.

        Args:
            file_path: Path to the file being reviewed
            warnings: List of warning dictionaries containing rule_id, message, etc.
        """
        if not warnings:
            return

        # Initialize file memory if not exists
        if file_path not in self.data.get("files", {}):
            if "files" not in self.data:
                self.data["files"] = {}
            self.data["files"][file_path] = {
                "pending_warnings": [],
                "suppressed": [],
                "risk_score": 0,
                "last_reviewed": datetime.now().isoformat()
            }

        file_memory = FileMemory.from_dict(self.data["files"][file_path])

        # Record each warning
        for warning in warnings:
            rule_id = warning.get("rule_id", "unknown")
            message = warning.get("message", "")

            # Find existing warning
            existing_warning = None
            for warn in file_memory.pending_warnings:
                if warn.rule_id == rule_id:
                    existing_warning = warn
                    break

            if existing_warning:
                # Update existing warning
                existing_warning.count += 1
                existing_warning.last_message = message
                existing_warning.remind_state = "full"  # Reset to full on new occurrence
            else:
                # Create new warning
                new_warning = WarningRecord(
                    rule_id=rule_id,
                    first_seen=datetime.now().isoformat(),
                    count=1,
                    remind_count=0,
                    remind_state="full",
                    last_message=message
                )
                file_memory.pending_warnings.append(new_warning)

        # Calculate risk score directly on local object
        total_score = 0
        for warning in file_memory.pending_warnings:
            total_score += min(warning.count, 5) * 2
        file_memory.risk_score = min(total_score, 10)

        # Update last reviewed time
        file_memory.last_reviewed = datetime.now().isoformat()

        # Save back to data
        self.data["files"][file_path] = file_memory.to_dict()
        self._save()

    def get_file_memory(self, file_path: str) -> Optional[FileMemory]:
        """
        Get memory state for a specific file.

        Args:
            file_path: Path to the file

        Returns:
            FileMemory object or None if no memory exists
        """
        if file_path not in self.data.get("files", {}):
            return None

        return FileMemory.from_dict(self.data["files"][file_path])

    def get_risk_files(self, threshold: int = 5) -> List[str]:
        """
        Return files with risk_score >= threshold.

        Args:
            threshold: Minimum risk score to include

        Returns:
            List of file paths with high risk scores
        """
        high_risk_files = []

        for file_path, file_data in self.data.get("files", {}).items():
            if file_data.get("risk_score", 0) >= threshold:
                high_risk_files.append(file_path)

        return sorted(high_risk_files)

    def get_reminder_level(self, file_path: str) -> Optional[str]:
        """
        Determine reminder level for a file's pending warnings.
        Returns "full", "short", "minimal", or None (suppressed).
        Based on remind_count: 0=full, 1=short, 2=minimal, 3+=suppressed

        Args:
            file_path: Path to the file

        Returns:
            Reminder level string or None if suppressed
        """
        file_memory = self.get_file_memory(file_path)
        if not file_memory or not file_memory.pending_warnings:
            return None

        # Check if any warning is suppressed
        for warning in file_memory.pending_warnings:
            if warning.remind_state == "suppressed" or warning.remind_state == "manual_suppress":
                return None

        # Determine reminder level based on minimum remind_count
        min_remind_count = min(w.remind_count for w in file_memory.pending_warnings)

        if min_remind_count >= 3:
            return "suppressed"
        elif min_remind_count >= 2:
            return "minimal"
        elif min_remind_count >= 1:
            return "short"
        else:
            return "full"

    def increment_remind_count(self, file_path: str) -> None:
        """
        Called after showing a reminder in pre-commit output.
        Increments remind_count for all pending warnings.

        Args:
            file_path: Path to the file
        """
        file_memory = self.get_file_memory(file_path)
        if not file_memory:
            return

        for warning in file_memory.pending_warnings:
            if warning.remind_state not in ["suppressed", "manual_suppress"]:
                warning.remind_count += 1

                # Update remind_state based on new count
                if warning.remind_count >= 3:
                    warning.remind_state = "suppressed"
                elif warning.remind_count >= 2:
                    warning.remind_state = "minimal"
                elif warning.remind_count >= 1:
                    warning.remind_state = "short"

        # Save back
        self.data["files"][file_path] = file_memory.to_dict()
        self._save()

    def format_reminder(self, file_path: str, level: str) -> str:
        """
        Format the reminder text based on level (full/short/minimal).

        Args:
            file_path: Path to the file
            level: Reminder level ("full", "short", "minimal")

        Returns:
            Formatted reminder string
        """
        file_memory = self.get_file_memory(file_path)
        if not file_memory:
            return ""

        pending_warnings = [w for w in file_memory.pending_warnings
                          if w.remind_state not in ["suppressed", "manual_suppress"]]

        if not pending_warnings:
            return ""

        # Format based on level
        if level == "full":
            header = f"⚠️  Persistent issues in {file_path}:"
            details = "\n".join(f"  • {w.last_message} ({w.count} occurrences)" for w in pending_warnings)
            risk_info = f"\n  Risk score: {file_memory.risk_score}/10"
            return f"{header}\n{details}{risk_info}"

        elif level == "short":
            return f"⚠️  {len(pending_warnings)} persistent issues in {file_path} (risk: {file_memory.risk_score}/10)"

        elif level == "minimal":
            return f"⚠️  {len(pending_warnings)} issues in {file_path}"

        return ""

    def suppress_rule(self, file_path: str, rule_id: str, reason: str) -> None:
        """
        Suppress a specific rule for a file.

        Args:
            file_path: Path to the file
            rule_id: ID of the rule to suppress
            reason: Reason for suppression
        """
        file_memory = self.get_file_memory(file_path)
        if not file_memory:
            return

        # Create suppress record
        suppress_record = SuppressRecord(
            rule_id=rule_id,
            reason=reason,
            suppressed_at=datetime.now().isoformat(),
            suppressed_by="manual"
        )

        file_memory.suppressed.append(suppress_record)

        # Remove from pending warnings if it exists
        file_memory.pending_warnings = [
            w for w in file_memory.pending_warnings
            if not (w.rule_id == rule_id and w.remind_state != "manual_suppress")
        ]

        # Save back
        self.data["files"][file_path] = file_memory.to_dict()
        self._save()

    def cancel_suppress(self, file_path: str, rule_id: str) -> None:
        """
        Cancel suppression of a specific rule.

        Args:
            file_path: Path to the file
            rule_id: ID of the rule to unsuppress
        """
        file_memory = self.get_file_memory(file_path)
        if not file_memory:
            return

        # Remove suppression record
        file_memory.suppressed = [
            s for s in file_memory.suppressed
            if s.rule_id != rule_id
        ]

        # Save back
        self.data["files"][file_path] = file_memory.to_dict()
        self._save()

    def list_suppressed(self) -> List[Tuple[str, SuppressRecord]]:
        """
        Return all suppressed warnings across all files.

        Returns:
            List of tuples (file_path, SuppressRecord)
        """
        suppressed_list = []

        for file_path, file_data in self.data.get("files", {}).items():
            for suppressed in file_data.get("suppressed", []):
                suppressed_list.append((file_path, suppressed))

        return suppressed_list

    def check_fixed_warnings(self, file_path: str, diff: str) -> None:
        """
        Check if any pending warning's code was fixed in the diff. Remove if so.
        Simple heuristic: if the line mentioned in last_message is no longer in the diff.

        Args:
            file_path: Path to the file
            diff: The diff content of the file
        """
        file_memory = self.get_file_memory(file_path)
        if not file_memory or not file_memory.pending_warnings:
            return

        # Check each warning against the diff
        remaining_warnings = []
        for warning in file_memory.pending_warnings:
            # Simple heuristic: if warning mentions a line number that's no longer in the file
            if not self._is_warning_fixed(warning, diff):
                remaining_warnings.append(warning)

        if len(remaining_warnings) != len(file_memory.pending_warnings):
            file_memory.pending_warnings = remaining_warnings
            self.recalc_risk_score(file_path)
            self.data["files"][file_path] = file_memory.to_dict()
            self._save()

    def _is_warning_fixed(self, warning: WarningRecord, diff: str) -> bool:
        """
        Check if a warning appears to be fixed based on the diff.

        Args:
            warning: Warning record to check
            diff: The diff content

        Returns:
            True if the warning appears to be fixed
        """
        # Simple heuristic: if warning contains line numbers and the diff removes those lines
        import re

        # Extract line numbers from warning message
        line_numbers = re.findall(r'line (\d+)', warning.last_message, re.IGNORECASE)

        if not line_numbers:
            return False  # Can't determine if fixed without line info

        # Check if any mentioned lines are deleted in the diff
        for line_num in line_numbers:
            # Look for deletions at or around this line
            pattern = rf'^[-].*{line_num}.*$'
            if re.search(pattern, diff, re.MULTILINE):
                return True

        return False

    def decay(self, decay_days: int = 30) -> None:
        """
        Remove warnings older than decay_days that haven't been re-triggered.

        Args:
            decay_days: Maximum age of warnings in days
        """
        cutoff_date = datetime.now() - timedelta(days=decay_days)

        for file_path, file_data in self.data.get("files", {}).items():
            file_memory = FileMemory.from_dict(file_data)

            # Remove old warnings
            remaining_warnings = []
            for warning in file_memory.pending_warnings:
                warning_date = datetime.fromisoformat(warning.first_seen)
                if warning_date > cutoff_date:
                    remaining_warnings.append(warning)

            if len(remaining_warnings) != len(file_memory.pending_warnings):
                file_memory.pending_warnings = remaining_warnings
                self.recalc_risk_score(file_path)
                self.data["files"][file_path] = file_memory.to_dict()

        # Save and update timestamp
        self.data["updated_at"] = datetime.now().isoformat()
        self._save()

    def recalc_risk_score(self, file_path: str) -> None:
        """
        Recalculate risk score: sum of min(count, 5) * 2 for each warning, capped at 10.

        Args:
            file_path: Path to the file
        """
        file_memory = self.get_file_memory(file_path)
        if not file_memory:
            return

        total_score = 0
        for warning in file_memory.pending_warnings:
            # Each warning contributes min(count, 5) * 2 points
            warning_score = min(warning.count, 5) * 2
            total_score += warning_score

        # Cap at 10
        file_memory.risk_score = min(total_score, 10)

    def _load(self) -> dict:
        """
        Load memory data from file.

        Returns:
            Dictionary containing memory data
        """
        try:
            if os.path.exists(self.path):
                with open(self.path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Ensure required fields exist
                if "version" not in data:
                    data["version"] = 1
                if "updated_at" not in data:
                    data["updated_at"] = datetime.now().isoformat()
                if "files" not in data:
                    data["files"] = {}
                if "inbox" not in data:
                    data["inbox"] = {"reports": {}}

                return data
            else:
                # Initialize with default structure
                return {
                    "version": 1,
                    "updated_at": datetime.now().isoformat(),
                    "files": {},
                    "inbox": {"reports": {}}
                }
        except Exception as e:
            print(f"Error loading memory file: {e}")
            return {
                "version": 1,
                "updated_at": datetime.now().isoformat(),
                "files": {},
                "inbox": {"reports": {}}
            }

    def _save(self) -> None:
        """
        Save memory data to file.
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.path), exist_ok=True)

            # Update timestamp
            self.data["updated_at"] = datetime.now().isoformat()

            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"Error saving memory file: {e}")

    def _estimate_tokens(self, text: str) -> int:
        """
        Rough estimate: 1 token per 4 characters.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        return len(text) // 4