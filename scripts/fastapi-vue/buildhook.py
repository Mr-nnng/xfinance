"""Hatch build hook: bundle the built Vue app into the wheel."""

from __future__ import annotations

import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

sys.path.insert(0, str(Path(__file__).parent))

from buildutil import build_frontend


class CustomBuildHook(BuildHookInterface):
    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict) -> None:
        if self.target_name != "wheel" or version == "editable":
            return
        files = build_frontend(self.root)
        if not files:
            raise RuntimeError("frontend/package.json is missing")
        build_data["artifacts"].append("/app/frontend-build/**")
