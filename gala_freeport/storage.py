from __future__ import annotations

from dataclasses import asdict, is_dataclass
import gzip
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterable


def _dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return value
    raise TypeError(f"unsupported record type: {type(value)!r}")


def deterministic_json(value: Any, *, pretty: bool = False) -> str:
    kwargs: dict[str, Any] = {"ensure_ascii": False, "sort_keys": True, "allow_nan": False}
    if pretty:
        kwargs["indent"] = 2
    else:
        kwargs["separators"] = (",", ":")
    return json.dumps(_dict(value) if not isinstance(value, (dict, list)) else value, **kwargs)


def write_jsonl_gz(path: Path, records: Iterable[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="\n") as text:
                for record in records:
                    text.write(deterministic_json(record) + "\n")


def read_jsonl_gz(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from error
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected JSON object")
            rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(deterministic_json(value, pretty=True) + "\n", encoding="utf-8")


def snapshot_files(snapshot_dir: Path, channel: str) -> list[Path]:
    suffix = f".{channel}.jsonl.gz" if channel != "manifest" else ".manifest.json"
    return sorted(snapshot_dir.glob(f"????-??-??{suffix}"))


def write_snapshot_bundle(
    snapshot_dir: Path,
    snapshot_date: str,
    catalog: Iterable[Any],
    promotions: Iterable[Any],
    manifest: Any,
) -> tuple[Path, Path, Path]:
    """Stage and transactionally replace the three same-day snapshot channels."""
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    finals = (
        snapshot_dir / f"{snapshot_date}.catalog.jsonl.gz",
        snapshot_dir / f"{snapshot_date}.promotions.jsonl.gz",
        snapshot_dir / f"{snapshot_date}.manifest.json",
    )
    stage = Path(tempfile.mkdtemp(prefix=f".{snapshot_date}.stage-", dir=snapshot_dir))
    backup = stage / "backup"
    backup.mkdir()
    staged = (stage / finals[0].name, stage / finals[1].name, stage / finals[2].name)
    try:
        write_jsonl_gz(staged[0], catalog)
        write_jsonl_gz(staged[1], promotions)
        write_json(staged[2], manifest)
        for final in finals:
            if final.exists():
                shutil.copy2(final, backup / final.name)
        replaced: list[Path] = []
        try:
            for source, final in zip(staged, finals):
                os.replace(source, final)
                replaced.append(final)
        except BaseException:
            for final in replaced:
                saved = backup / final.name
                if saved.exists():
                    os.replace(saved, final)
                else:
                    final.unlink(missing_ok=True)
            raise
        return finals
    finally:
        shutil.rmtree(stage, ignore_errors=True)
