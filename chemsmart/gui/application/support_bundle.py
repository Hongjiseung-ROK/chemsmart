"""Create a bounded, redacted desktop support bundle on explicit request."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sys
import tempfile
import zipfile

from chemsmart import __version__
from chemsmart.gui.application.desktop_logging import desktop_log_root


MAX_LOG_FILES = 4
MAX_LOG_BYTES = 256 * 1024
MAX_TOTAL_LOG_BYTES = 1024 * 1024
_TRUNCATION_NOTICE = (
    "[Earlier log content omitted by support-bundle limit.]\n"
)
_ASSIGNMENT_SECRET = re.compile(
    r"(?i)\b([A-Za-z0-9_.-]*"
    r"(?:api[_-]?key|token|authorization|password|secret)"
    r"[A-Za-z0-9_.-]*[\"']?\s*[:=]\s*)([^\r\n;]+)"
)
_BEARER_SECRET = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")
_PROVIDER_SECRET = re.compile(
    r"\b(?:"
    r"(?:sk-(?:proj-)?|sk-ant-)[A-Za-z0-9_-]{12,}"
    r"|AIza[A-Za-z0-9_-]{20,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|xox[baprs]-[A-Za-z0-9-]{12,}"
    r")\b"
)


@dataclass(frozen=True)
class SupportBundleReceipt:
    output_path: Path
    bytes: int
    sha256: str
    included_log_count: int
    redaction_count: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _redact(text: str, *, home: Path) -> tuple[str, int]:
    redactions = 0
    home_text = str(home)
    if home_text and home_text in text:
        redactions += text.count(home_text)
        text = text.replace(home_text, "$HOME")

    def replace_assignment(match: re.Match[str]) -> str:
        nonlocal redactions
        redactions += 1
        return f"{match.group(1)}[REDACTED]"

    text = _ASSIGNMENT_SECRET.sub(replace_assignment, text)
    text, count = _BEARER_SECRET.subn("Bearer [REDACTED]", text)
    redactions += count
    text, count = _PROVIDER_SECRET.subn("[REDACTED_PROVIDER_KEY]", text)
    redactions += count
    return text, redactions


def _log_candidates(root: Path) -> list[Path]:
    if not root.is_dir() or root.is_symlink():
        return []
    candidates: list[Path] = []
    for path in root.glob("desktop.log*"):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            path.relative_to(root)
        except ValueError:
            continue
        candidates.append(path)
    return sorted(
        candidates,
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )[:MAX_LOG_FILES]


def _whole_line_tail(text: str, limit: int) -> str:
    selected: list[str] = []
    used = 0
    for line in reversed(text.splitlines(keepends=True)):
        line_bytes = len(line.encode("utf-8"))
        if line_bytes > limit - used:
            break
        selected.append(line)
        used += line_bytes
    return "".join(reversed(selected))


def _bounded_log_text(path: Path, *, limit: int = MAX_LOG_BYTES) -> str:
    if limit <= 0:
        return ""
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size <= limit:
            return handle.read(limit).decode("utf-8", errors="replace")
        start = max(0, size - limit)
        handle.seek(max(0, start - 1))
        payload = handle.read(limit + 1)
    if start > 0:
        if payload[:1] == b"\n":
            payload = payload[1:]
        else:
            boundary = payload.find(b"\n", 1)
            payload = b"" if boundary < 0 else payload[boundary + 1 :]
    notice_bytes = len(_TRUNCATION_NOTICE.encode("utf-8"))
    if notice_bytes >= limit:
        return _whole_line_tail(_TRUNCATION_NOTICE, limit)
    text = payload.decode("utf-8", errors="replace")
    return _TRUNCATION_NOTICE + _whole_line_tail(
        text,
        limit - notice_bytes,
    )


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    return info


def _manifest(*, log_count: int, redaction_count: int) -> dict[str, object]:
    return {
        "application": {
            "frozen": bool(getattr(sys, "frozen", False)),
            "release_level": "desktop-support-diagnostic",
            "version": __version__,
        },
        "collection": {
            "config_contents_included": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "log_count": log_count,
            "project_files_included": False,
            "provider_payloads_included": False,
            "redaction_count": redaction_count,
            "session_transcripts_included": False,
        },
        "runtime": {
            "architecture": platform.machine(),
            "macos_version": platform.mac_ver()[0],
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "schema_version": 1,
    }


def create_support_bundle(
    output_path: Path,
    *,
    log_root: Path | None = None,
    home: Path | None = None,
) -> SupportBundleReceipt:
    """Atomically create one review-before-sharing ZIP without config data."""
    output_path = output_path.expanduser().absolute()
    if output_path.suffix.lower() != ".zip":
        raise ValueError("Support bundle destination must end in .zip.")
    if output_path.exists() or output_path.is_symlink():
        raise FileExistsError(f"Support bundle already exists: {output_path}")
    if not output_path.parent.is_dir() or output_path.parent.is_symlink():
        raise ValueError("Support bundle parent must be an existing directory.")

    selected_root = (log_root or desktop_log_root()).expanduser().absolute()
    selected_home = (home or Path.home()).expanduser().absolute()
    logs: list[tuple[str, str]] = []
    redaction_count = 0
    total_bytes = 0
    for index, path in enumerate(_log_candidates(selected_root)):
        remaining = MAX_TOTAL_LOG_BYTES - total_bytes
        if remaining <= 0:
            break
        text = _bounded_log_text(path, limit=min(MAX_LOG_BYTES, remaining))
        redacted, count = _redact(text, home=selected_home)
        if len(redacted.encode("utf-8")) > remaining:
            redacted = _whole_line_tail(redacted, remaining)
        redaction_count += count
        total_bytes += len(redacted.encode("utf-8"))
        logs.append((f"logs/desktop-{index}.log", redacted))

    manifest = _manifest(
        log_count=len(logs),
        redaction_count=redaction_count,
    )
    notice = (
        "Review this bundle before sharing it. ChemSmart excludes configuration "
        "contents, project files, provider payloads, session transcripts, and "
        "Keychain data. Recent desktop logs are bounded and common secret forms "
        "and the home-directory prefix are redacted.\n"
    )
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        dir=output_path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        os.close(fd)
        os.chmod(temporary_path, 0o600)
        with zipfile.ZipFile(
            temporary_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            archive.writestr(
                _zip_info("manifest.json"),
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            )
            archive.writestr(_zip_info("README.txt"), notice)
            for name, content in logs:
                archive.writestr(_zip_info(name), content)
        with temporary_path.open("rb") as handle:
            os.fsync(handle.fileno())
        os.link(temporary_path, output_path, follow_symlinks=False)
        temporary_path.unlink()
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return SupportBundleReceipt(
        output_path=output_path,
        bytes=output_path.stat().st_size,
        sha256=_sha256(output_path),
        included_log_count=len(logs),
        redaction_count=redaction_count,
    )


def receipt_dict(receipt: SupportBundleReceipt) -> dict[str, object]:
    payload = asdict(receipt)
    payload["output_path"] = str(receipt.output_path)
    return payload
