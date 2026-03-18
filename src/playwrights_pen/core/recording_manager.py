"""Recording manager for test execution artifacts."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ..config import RecordingMode, settings

if TYPE_CHECKING:
    from ..targets.base import TestTarget


class RecordingManager:
    """Manages recording of test execution artifacts.
    
    Supports four modes:
    - NONE: No recording
    - MINIMAL: Only action sequence + final screenshot
    - STANDARD: Screenshot + accessibility snapshot per step (default)
    - FULL: Video recording + detailed logs
    """
    
    def __init__(
        self,
        mode: RecordingMode = RecordingMode.STANDARD,
        session_id: str | None = None,
        output_dir: Path | None = None,
    ) -> None:
        """Initialize recording manager.
        
        Args:
            mode: Recording mode
            session_id: Session ID for organizing recordings
            output_dir: Output directory for recordings
        """
        self.mode = mode
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = output_dir or settings.data_dir / "recordings" / self.session_id
        
        # Video recording state
        self._video_path: Path | None = None
        self._video_started = False
        
        # Step recordings
        self._step_count = 0
        self._screenshots: list[Path] = []
        self._snapshots: list[str] = []
        self._action_log: list[dict] = []
    
    async def start_session(self, target: "TestTarget | None" = None) -> None:
        """Start recording session.
        
        Args:
            target: Test target for video recording (if FULL mode)
        """
        if self.mode == RecordingMode.NONE:
            return
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize action log
        self._action_log = []
        self._step_count = 0
        
        # Start video recording for FULL mode
        if self.mode == RecordingMode.FULL and target:
            self._video_path = self.output_dir / "execution.webm"
            # Note: Video recording would be started via Playwright's video option
            # This is handled at target connection time
            self._video_started = True
    
    async def record_step_start(
        self,
        step_index: int,
        step_description: str,
        target: "TestTarget | None" = None,
    ) -> str | None:
        """Record the start of a step execution.
        
        Args:
            step_index: Current step index
            step_description: Human-readable step description
            target: Test target for screenshots
            
        Returns:
            Accessibility snapshot if STANDARD or FULL mode
        """
        if self.mode == RecordingMode.NONE:
            return None
        
        self._step_count = step_index
        snapshot = None
        
        # Log action
        action_entry = {
            "step": step_index,
            "description": step_description,
            "started_at": datetime.now().isoformat(),
            "status": "running",
        }
        self._action_log.append(action_entry)
        
        # Take snapshot for STANDARD and FULL modes
        if self.mode in (RecordingMode.STANDARD, RecordingMode.FULL) and target:
            try:
                snapshot = await target.get_snapshot()
                self._snapshots.append(snapshot)
                action_entry["snapshot_before"] = f"snapshot_{step_index}_before.txt"
                
                # Save snapshot to file
                snapshot_path = self.output_dir / f"snapshot_{step_index}_before.txt"
                snapshot_path.write_text(snapshot, encoding="utf-8")
            except Exception:
                pass
        
        return snapshot
    
    async def record_step_end(
        self,
        step_index: int,
        success: bool,
        result: str | None = None,
        error: str | None = None,
        target: "TestTarget | None" = None,
    ) -> Path | None:
        """Record the end of a step execution.
        
        Args:
            step_index: Current step index
            success: Whether step succeeded
            result: Step result message
            error: Error message if failed
            target: Test target for screenshots
            
        Returns:
            Screenshot path if taken
        """
        if self.mode == RecordingMode.NONE:
            return None
        
        screenshot_path = None
        
        # Update action log
        if self._action_log and self._action_log[-1]["step"] == step_index:
            self._action_log[-1].update({
                "ended_at": datetime.now().isoformat(),
                "status": "passed" if success else "failed",
                "result": result,
                "error": error,
            })
        
        # Take screenshot after step
        if target and self.mode != RecordingMode.MINIMAL:
            try:
                screenshot_path = self.output_dir / f"screenshot_{step_index}.png"
                await target.take_screenshot(str(screenshot_path))
                self._screenshots.append(screenshot_path)
                
                if self._action_log:
                    self._action_log[-1]["screenshot"] = screenshot_path.name
            except Exception:
                pass
        
        # Take final snapshot for STANDARD and FULL
        if self.mode in (RecordingMode.STANDARD, RecordingMode.FULL) and target:
            try:
                snapshot = await target.get_snapshot()
                snapshot_path = self.output_dir / f"snapshot_{step_index}_after.txt"
                snapshot_path.write_text(snapshot, encoding="utf-8")
                
                if self._action_log:
                    self._action_log[-1]["snapshot_after"] = snapshot_path.name
            except Exception:
                pass
        
        # Save action log after each step
        await self._save_action_log()
        
        return screenshot_path
    
    async def end_session(
        self,
        success: bool,
        target: "TestTarget | None" = None,
    ) -> dict:
        """End recording session and finalize outputs.
        
        Args:
            success: Whether test passed
            target: Test target for final screenshot
            
        Returns:
            Recording summary
        """
        if self.mode == RecordingMode.NONE:
            return {"mode": "none"}
        
        # Take final screenshot for MINIMAL mode
        if self.mode == RecordingMode.MINIMAL and target:
            try:
                final_path = self.output_dir / "final_screenshot.png"
                await target.take_screenshot(str(final_path))
                self._screenshots.append(final_path)
            except Exception:
                pass
        
        # Save final action log
        await self._save_action_log()
        
        # Create summary
        summary = {
            "mode": self.mode.value,
            "session_id": self.session_id,
            "output_dir": str(self.output_dir),
            "success": success,
            "total_steps": self._step_count + 1,
            "screenshots": [str(p) for p in self._screenshots],
            "video": str(self._video_path) if self._video_path else None,
            "action_log": str(self.output_dir / "actions.json"),
        }
        
        # Save summary
        import json
        summary_path = self.output_dir / "summary.json"
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        
        return summary
    
    async def _save_action_log(self) -> None:
        """Save action log to file."""
        import json
        
        log_path = self.output_dir / "actions.json"
        log_path.write_text(
            json.dumps(self._action_log, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    
    @property
    def screenshots(self) -> list[Path]:
        """Get list of screenshot paths."""
        return self._screenshots.copy()
    
    @property
    def action_log(self) -> list[dict]:
        """Get action log entries."""
        return self._action_log.copy()


def get_recording_storage_estimate(
    mode: RecordingMode,
    step_count: int,
) -> dict[str, int]:
    """Estimate storage requirements for recording.
    
    Args:
        mode: Recording mode
        step_count: Number of test steps
        
    Returns:
        Estimated storage in bytes for each component
    """
    estimates = {
        "action_log": step_count * 500,  # ~500 bytes per step
        "snapshots": 0,
        "screenshots": 0,
        "video": 0,
        "total": 0,
    }
    
    if mode == RecordingMode.MINIMAL:
        estimates["screenshots"] = 150_000  # One final screenshot ~150KB
    
    elif mode == RecordingMode.STANDARD:
        estimates["snapshots"] = step_count * 15_000  # ~15KB per snapshot
        estimates["screenshots"] = step_count * 150_000  # ~150KB per screenshot
    
    elif mode == RecordingMode.FULL:
        estimates["snapshots"] = step_count * 15_000
        estimates["screenshots"] = step_count * 150_000
        # Video: ~2MB per minute, estimate 5 seconds per step
        estimates["video"] = (step_count * 5 / 60) * 2_000_000
    
    estimates["total"] = sum(v for k, v in estimates.items() if k != "total")
    
    return estimates
