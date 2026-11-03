import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger("CodeStorage")

HISTORY_FILE = "codes_history.json"

class CodeManager:
    def __init__(self, filepath: str = HISTORY_FILE):
        self.filepath = filepath
        self.data: Dict[str, Dict[str, Any]] = self._load()

    def _load(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading {self.filepath}: {e}")
        return {}

    def save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving {self.filepath}: {e}")

    def is_known(self, code: str) -> bool:
        """Returns True if the code has already been seen/marked."""
        return code.upper() in self.data

    def get_status(self, code: str) -> str:
        entry = self.data.get(code.upper())
        return entry.get("status", "NEW") if entry else "NEW"

    def add_code(self, code: str, source: str = "Telegram"):
        code = code.upper()
        if code not in self.data:
            self.data[code] = {
                "code": code,
                "status": "PENDING",  # PENDING, CLAIMED, INVALID
                "source": source,
                "timestamp": self._get_now()
            }
            self.save()

    def mark_status(self, code: str, status: str):
        """Mark code as CLAIMED or INVALID so it's never re-scanned/re-processed."""
        code = code.upper()
        if code in self.data:
            self.data[code]["status"] = status
            self.data[code]["updated_at"] = self._get_now()
        else:
            self.data[code] = {
                "code": code,
                "status": status,
                "source": "Manual",
                "timestamp": self._get_now(),
                "updated_at": self._get_now()
            }
        self.save()

    def get_all(self):
        """Return list of all records sorted newest first."""
        records = list(self.data.values())
        records.reverse()
        return records

    @staticmethod
    def _get_now() -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

