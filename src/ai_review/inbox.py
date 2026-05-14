"""Inbox manager - tracks review reports with read/unread state."""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from glob import glob
from typing import Dict, List, Optional


@dataclass
class InboxReport:
    report_id: str       # filename stem, e.g. "review_abc12345_1747286400"
    tag: str
    status: str          # PASS / WARNING / BLOCKING
    timestamp: int
    time_str: str
    issue_count: int
    file_count: int
    read: bool
    archived: bool


class InboxManager:
    """Manages report inbox state, persisted in memory.json alongside ReviewMemory."""

    def __init__(self, memory_path: str = ".ai-review/memory.json"):
        self.memory_path = memory_path
        self.reports_dir = os.path.join(os.path.dirname(memory_path), "reports")

    def _load_inbox(self) -> dict:
        try:
            if os.path.exists(self.memory_path):
                with open(self.memory_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return data.get("inbox", {}).get("reports", {})
        except Exception:
            pass
        return {}

    def _save_inbox(self, inbox_reports: dict) -> None:
        data = {}
        try:
            if os.path.exists(self.memory_path):
                with open(self.memory_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
        except Exception:
            data = {"version": 1, "files": {}, "inbox": {"reports": {}}}

        if "inbox" not in data:
            data["inbox"] = {"reports": {}}
        data["inbox"]["reports"] = inbox_reports
        data["updated_at"] = datetime.now().isoformat()

        os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
        with open(self.memory_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _scan_report_files(self) -> List[str]:
        if not os.path.isdir(self.reports_dir):
            return []
        pattern = os.path.join(self.reports_dir, "review_*.json")
        files = glob(pattern)
        # Extract stem (without .json)
        return [os.path.splitext(os.path.basename(f))[0] for f in sorted(files, reverse=True)]

    def _read_report_meta(self, report_id: str) -> Optional[dict]:
        json_path = os.path.join(self.reports_dir, f"{report_id}.json")
        if not os.path.exists(json_path):
            return None
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return {
                "tag": data.get("tag", ""),
                "status": data.get("status", "PASS"),
                "timestamp": data.get("timestamp", 0),
                "issue_count": sum(data.get("severity_counts", {}).values()),
                "file_count": len(data.get("files", [])),
            }
        except Exception:
            return None

    def list_reports(
        self,
        status: Optional[str] = None,
        unread_only: bool = False,
        limit: int = 20,
        include_archived: bool = False,
    ) -> List[InboxReport]:
        inbox_state = self._load_inbox()
        report_ids = self._scan_report_files()
        results = []

        for rid in report_ids:
            entry = inbox_state.get(rid, {})
            read = entry.get("read", False)
            archived = entry.get("archived", False)

            if not include_archived and archived:
                continue

            meta = self._read_report_meta(rid)
            if not meta:
                continue

            if status and meta["status"] != status.upper():
                continue

            if unread_only and read:
                continue

            ts = meta["timestamp"]
            time_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else ""

            results.append(InboxReport(
                report_id=rid,
                tag=meta["tag"],
                status=meta["status"],
                timestamp=ts,
                time_str=time_str,
                issue_count=meta["issue_count"],
                file_count=meta["file_count"],
                read=read,
                archived=archived,
            ))

            if len(results) >= limit:
                break

        return results

    def get_report(self, report_id: str) -> Optional[dict]:
        json_path = os.path.join(self.reports_dir, f"{report_id}.json")
        if not os.path.exists(json_path):
            return None
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    def get_report_path(self, report_id: str, ext: str = "md") -> Optional[str]:
        path = os.path.join(self.reports_dir, f"{report_id}.{ext}")
        return path if os.path.exists(path) else None

    def mark_read(self, report_id: str) -> None:
        inbox = self._load_inbox()
        if report_id not in inbox:
            inbox[report_id] = {}
        inbox[report_id]["read"] = True
        self._save_inbox(inbox)

    def mark_unread(self, report_id: str) -> None:
        inbox = self._load_inbox()
        if report_id not in inbox:
            inbox[report_id] = {}
        inbox[report_id]["read"] = False
        self._save_inbox(inbox)

    def mark_all_read(self) -> int:
        inbox = self._load_inbox()
        report_ids = self._scan_report_files()
        count = 0
        for rid in report_ids:
            if not inbox.get(rid, {}).get("read", False):
                if rid not in inbox:
                    inbox[rid] = {}
                inbox[rid]["read"] = True
                count += 1
        self._save_inbox(inbox)
        return count

    def archive(self, report_id: str) -> None:
        inbox = self._load_inbox()
        if report_id not in inbox:
            inbox[report_id] = {}
        inbox[report_id]["archived"] = True
        self._save_inbox(inbox)

    def get_unread_count(self) -> int:
        inbox = self._load_inbox()
        report_ids = self._scan_report_files()
        count = 0
        for rid in report_ids:
            entry = inbox.get(rid, {})
            if not entry.get("read", False) and not entry.get("archived", False):
                count += 1
        return count

    def register_report(self, report_id: str) -> None:
        inbox = self._load_inbox()
        if report_id not in inbox:
            inbox[report_id] = {
                "read": False,
                "archived": False,
                "notified": False,
                "registered_at": datetime.now().isoformat(),
            }
        self._save_inbox(inbox)

    def get_all_reports_data(self, limit: int = 50) -> List[dict]:
        """Get full report data for dashboard generation."""
        reports = self.list_reports(limit=limit, include_archived=False)
        results = []
        for r in reports:
            data = self.get_report(r.report_id)
            if data:
                data["_inbox"] = {
                    "read": r.read,
                    "report_id": r.report_id,
                }
                results.append(data)
        return results
