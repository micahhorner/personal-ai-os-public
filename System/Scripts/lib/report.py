"""Uniform human + JSON reporting for all subcommands."""
from __future__ import annotations
import json, sys

class Report:
    def __init__(self, command: str):
        self.command = command
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: dict = {}
    def error(self, msg: str): self.errors.append(msg)
    def warn(self, msg: str): self.warnings.append(msg)
    @property
    def ok(self) -> bool: return not self.errors
    def emit(self, as_json: bool = False) -> int:
        if as_json:
            print(json.dumps({"command": self.command, "ok": self.ok,
                              "errors": self.errors, "warnings": self.warnings,
                              "info": self.info}, indent=2, default=str))
        else:
            for e in self.errors: print(f"ERROR   {e}")
            for w in self.warnings: print(f"warning {w}")
            for k, v in self.info.items(): print(f"{k}: {v}")
            status = "OK" if self.ok else "FAILED"
            print(f"[{self.command}] {status} — {len(self.errors)} errors, {len(self.warnings)} warnings")
        return 0 if self.ok else 1
