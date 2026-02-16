"""Run logger for strategy sessions."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class TradeRunLogger:
    """Persist structured run events to a JSONL file."""

    strategy_name: str
    coin: str
    interval_minutes: int
    enabled: bool = True
    log_dir: str = "logs/runs"

    def __post_init__(self) -> None:
        self._start_ts = time.time()
        self._log_path: Optional[Path] = None

        if not self.enabled:
            return

        base = Path(self.log_dir)
        base.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        run_id = uuid.uuid4().hex[:8]
        filename = f"{stamp}-{self.strategy_name.lower()}-{self.coin.lower()}-{self.interval_minutes}m-{run_id}.jsonl"
        self._log_path = base / filename

    @property
    def log_path(self) -> Optional[str]:
        if self._log_path is None:
            return None
        return str(self._log_path)

    def event(self, event_type: str, **payload: Any) -> None:
        """Append one JSON event to the run log."""
        if self._log_path is None:
            return

        row: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "elapsed_s": round(time.time() - self._start_ts, 3),
            "event": event_type,
        }
        row.update(payload)

        try:
            with self._log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            # Logging should never interrupt trading flow.
            return
