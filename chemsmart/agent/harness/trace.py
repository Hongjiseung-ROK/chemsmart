from __future__ import annotations

import json
from pathlib import Path

from chemsmart.agent.harness.models import HarnessResult
from chemsmart.agent.private_io import write_private_text


def write_harness_result(session_dir: Path, result: HarnessResult) -> None:
    write_private_text(
        session_dir / "harness_result.json",
        json.dumps(result.to_dict(), indent=2, sort_keys=True),
    )
