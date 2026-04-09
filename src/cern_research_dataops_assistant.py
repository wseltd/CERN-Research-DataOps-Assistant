"""Bootstrap CLI for local-first CERN research DataOps workflows.

This module intentionally keeps a narrow surface area: configuration loading,
parser construction, and CLI dispatch for the first command groups.
"""

from __future__ import annotations

import argparse
import collections.abc
import importlib.util
import json
import logging
import os
import pathlib
import tempfile
import typing
import tomllib
from datetime import datetime, timezone
from typing import Any

DEFAULT_CONFIG_FILENAME = "config.toml"
DEFAULT_DATA_DIRNAME = "data"
DEFAULT_LOG_LEVEL = "INFO"
VALID_LOG_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"})
ALLOWED_CONFIG_KEYS = frozenset({"project_root", "data_dir", "log_level"})

COMMAND_GROUP_CONFIG = "config"
COMMAND_GROUP_DATASET = "dataset"
COMMAND_GROUP_SUMMARY = "summary"
COMMAND_GROUP_INGEST = "ingest"
COMMAND_GROUP_QUERY = "query"
COMMAND_GROUP_ASSISTANT = "assistant"
COMMAND_CONFIG_SHOW = "show"
COMMAND_DATASET_LIST = "list"
COMMAND_ID_CONFIG_SHOW = "config_show"
COMMAND_ID_DATASET_LIST = "dataset_list"
COMMAND_ID_SUMMARY = "summary"
COMMAND_ID_INGEST = "ingest"
COMMAND_ID_QUERY = "query"
COMMAND_ASSISTANT_SEED = "seed"
COMMAND_ASSISTANT_ASK = "ask"
COMMAND_ASSISTANT_EVAL = "eval"
COMMAND_ASSISTANT_DEMO = "demo"
COMMAND_ID_ASSISTANT_SEED = "assistant_seed"
COMMAND_ID_ASSISTANT_ASK = "assistant_ask"
COMMAND_ID_ASSISTANT_EVAL = "assistant_eval"
COMMAND_ID_ASSISTANT_DEMO = "assistant_demo"
COMMAND_SUMMARY_REPO_DIR = "repo_dir"
SUMMARY_KEY_COUNT = "count"
SUMMARY_KEY_MIN_RECORDED_AT = "min_recorded_at"
SUMMARY_KEY_MAX_RECORDED_AT = "max_recorded_at"

RECORD_REQUIRED_KEYS = frozenset({"experiment", "run_id", "timestamp", "payload"})
RECORDS_JSONL_FILENAME: str = "records.jsonl"
INGEST_SUMMARY_ACCEPTED = "accepted"
INGEST_SUMMARY_INVALID = "invalid"
INGEST_SUMMARY_SKIPPED_EXISTING = "skipped_existing"
INGEST_SUMMARY_SKIPPED_BATCH = "skipped_batch"
INGEST_SUMMARY_INSERTED = "inserted"
INGEST_SUMMARY_SKIPPED_DUPLICATES = "skipped_duplicates"
RUN_ID_FINGERPRINT_PREFIX = "fingerprint:"

LOGGER = logging.getLogger(__name__)
EXIT_CODES_MODULE_FILENAME = "exit_codes.py"
ASSISTANT_MODULE_FILENAME = "cern_open_data_mvp.py"
DEFAULT_ASSISTANT_SEED_DIR = pathlib.Path("data") / "cms_run2_nanoaod_mvp"
DEFAULT_ASSISTANT_EVAL_FILE = pathlib.Path("evaluations") / "cms_run2_nanoaod_eval_questions.json"


def _load_exit_codes_module() -> Any:
    """Load the sibling exit-codes module from the src directory."""
    module_path = pathlib.Path(__file__).with_name(EXIT_CODES_MODULE_FILENAME)
    module_spec = importlib.util.spec_from_file_location("exit_codes_runtime", module_path)
    if module_spec is None or module_spec.loader is None:
        raise ImportError(f"Unable to load exit codes from '{module_path}'.")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


_EXIT_CODES_MODULE = _load_exit_codes_module()
ExitCode = _EXIT_CODES_MODULE.ExitCode


def _load_assistant_module() -> Any:
    """Load the metadata-first assistant module from the src directory."""
    module_path = pathlib.Path(__file__).with_name(ASSISTANT_MODULE_FILENAME)
    module_spec = importlib.util.spec_from_file_location("assistant_runtime", module_path)
    if module_spec is None or module_spec.loader is None:
        raise ImportError(f"Unable to load assistant module from '{module_path}'.")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


_ASSISTANT_MODULE = _load_assistant_module()


class _CountRangeStats(tuple):
    """Tuple-like summary result with optional key-based access.

    The mapping-style index keeps backward compatibility with the ticket-level
    verify command while preserving tuple semantics for call sites that unpack.
    """

    __slots__ = ()

    def __new__(
        cls,
        count: int,
        min_recorded_at: str | None,
        max_recorded_at: str | None,
    ) -> "_CountRangeStats":
        return super().__new__(cls, (count, min_recorded_at, max_recorded_at))

    @property
    def count(self) -> int:
        """Return summary count."""
        return typing.cast(int, super().__getitem__(0))

    @property
    def min_recorded_at(self) -> str | None:
        """Return minimum timestamp value."""
        return typing.cast(str | None, super().__getitem__(1))

    @property
    def max_recorded_at(self) -> str | None:
        """Return maximum timestamp value."""
        return typing.cast(str | None, super().__getitem__(2))

    def __getitem__(self, key: int | slice | str) -> Any:
        """Support tuple indexing plus key-based access for summary fields."""
        if isinstance(key, str):
            if key == SUMMARY_KEY_COUNT:
                return self.count
            if key == SUMMARY_KEY_MIN_RECORDED_AT:
                return self.min_recorded_at
            if key == SUMMARY_KEY_MAX_RECORDED_AT:
                return self.max_recorded_at
            raise KeyError(key)
        return super().__getitem__(key)

    def __repr__(self) -> str:
        """Return a stable debug representation with explicit field names."""
        return (
            "_CountRangeStats("
            f"count={self.count!r}, "
            f"min_recorded_at={self.min_recorded_at!r}, "
            f"max_recorded_at={self.max_recorded_at!r})"
        )


class AppConfig(typing.NamedTuple):
    """Application configuration resolved from defaults and optional TOML file.

    Attributes:
        project_root: Root directory for local project operations.
        data_dir: Directory used for local dataset files.
        log_level: Uppercase logging level.
        config_path: TOML config file path used for this resolution.
    """

    project_root: pathlib.Path
    data_dir: pathlib.Path
    log_level: str
    config_path: pathlib.Path

    def __repr__(self) -> str:
        """Return a stable debug representation with explicit field names."""
        return (
            "AppConfig("
            f"project_root={self.project_root!r}, "
            f"data_dir={self.data_dir!r}, "
            f"log_level={self.log_level!r}, "
            f"config_path={self.config_path!r})"
        )


def configure_logging(log_level: str) -> None:
    """Configure process logging with strict level validation."""
    if not isinstance(log_level, str):
        raise TypeError(
            "Invalid value for 'log_level': expected str, "
            f"got {type(log_level).__name__}."
        )
    normalized_level = log_level.strip().upper()
    if normalized_level not in VALID_LOG_LEVELS:
        raise ValueError(
            "Invalid value for 'log_level': "
            f"'{log_level}'. Expected one of {sorted(VALID_LOG_LEVELS)}."
        )
    logging.basicConfig(
        level=getattr(logging, normalized_level),
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )


def parse_record(raw: Any) -> dict[str, Any]:
    """Validate and canonicalize a boundary record.

    Args:
        raw: Untrusted record input.

    Returns:
        Canonical dictionary with exactly experiment, run_id, timestamp, payload.

    Raises:
        ValueError: If required fields are missing, field types are invalid, or
            timestamp is not a valid UTC ISO-8601 value.
    """
    if not isinstance(raw, dict):
        raise ValueError("Invalid record: expected a dict.")

    missing_keys = sorted(key for key in RECORD_REQUIRED_KEYS if key not in raw)
    if missing_keys:
        missing_key = missing_keys[0]
        raise ValueError(f"Missing required field '{missing_key}'.")

    experiment = raw["experiment"]
    if not isinstance(experiment, str):
        raise ValueError("Invalid value for 'experiment': expected str.")

    run_id = raw["run_id"]
    if not isinstance(run_id, str):
        raise ValueError("Invalid value for 'run_id': expected str.")

    timestamp = raw["timestamp"]
    if not isinstance(timestamp, str):
        raise ValueError("Invalid value for 'timestamp': expected str.")

    payload = raw["payload"]
    if not isinstance(payload, dict):
        raise ValueError("Invalid value for 'payload': expected dict.")

    timestamp_value = _parse_utc_iso8601_timestamp(timestamp)

    return {
        "experiment": experiment,
        "run_id": run_id,
        "timestamp": timestamp_value,
        "payload": payload,
    }


def _build_fallback_run_id(raw_record: dict[str, Any]) -> str:
    """Build a stable fallback run identifier when `run_id` is missing.

    The fallback only depends on canonical dedupe keys and is deterministic
    across key-order variations in nested payload dictionaries.
    """
    fingerprint_payload = {
        "experiment": raw_record.get("experiment"),
        "timestamp": raw_record.get("timestamp"),
        "payload": raw_record.get("payload"),
    }
    canonical = json.dumps(
        fingerprint_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"{RUN_ID_FINGERPRINT_PREFIX}{canonical}"


def _parse_record_with_run_id_fallback(raw_record: object) -> dict[str, Any]:
    """Parse one raw ingest record, deriving a deterministic run_id when absent."""
    if isinstance(raw_record, dict) and "run_id" not in raw_record:
        record_with_fallback = dict(raw_record)
        record_with_fallback["run_id"] = _build_fallback_run_id(raw_record)
        return parse_record(record_with_fallback)
    return parse_record(raw_record)


def _parse_utc_iso8601_timestamp(timestamp: str) -> str:
    """Parse and normalize a UTC ISO-8601 timestamp to a canonical Z form."""
    normalized = timestamp[:-1] + "+00:00" if timestamp.endswith("Z") else timestamp
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(
            "Invalid value for 'timestamp': expected UTC ISO-8601 string."
        ) from exc

    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("Invalid value for 'timestamp': expected UTC timezone.")

    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _as_path(value: str | pathlib.Path, field_name: str, base_dir: pathlib.Path) -> pathlib.Path:
    """Coerce a path-like value into a normalized absolute path.

    Relative values are resolved against ``base_dir`` to keep configuration
    portable across environments.
    """
    if not isinstance(value, (str, pathlib.Path)):
        raise TypeError(
            f"Invalid value for '{field_name}': expected str or pathlib.Path, "
            f"got {type(value).__name__}."
        )

    raw_path = pathlib.Path(value).expanduser()
    if not raw_path.is_absolute():
        raw_path = base_dir / raw_path
    return raw_path.resolve()


def _default_config_path(config_path: str | pathlib.Path | None) -> pathlib.Path:
    """Return the canonical config path from an optional user input."""
    if config_path is None:
        return (pathlib.Path.cwd() / DEFAULT_CONFIG_FILENAME).resolve()
    return _as_path(config_path, "config_path", pathlib.Path.cwd())


def _read_config_values(config_path: pathlib.Path) -> dict[str, Any]:
    """Load supported config keys from a TOML file when present.

    The parser accepts either top-level keys or an ``[app]`` table. Unsupported
    keys are ignored to keep the public config surface intentionally narrow.
    """
    if not config_path.exists():
        return {}
    if not config_path.is_file():
        raise ValueError(
            f"Invalid config_path '{config_path}': expected a file path."
        )

    try:
        loaded = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid TOML in config file '{config_path}': {exc}") from exc

    if not isinstance(loaded, dict):
        raise ValueError(
            f"Invalid config file '{config_path}': top-level TOML document must be a table."
        )

    values: dict[str, Any] = {}
    app_section = loaded.get("app")
    if isinstance(app_section, dict):
        values.update({key: app_section[key] for key in ALLOWED_CONFIG_KEYS if key in app_section})

    values.update({key: loaded[key] for key in ALLOWED_CONFIG_KEYS if key in loaded})
    return values


def load_app_config(config_path: str | pathlib.Path | None = None) -> AppConfig:
    """Load application config from visible defaults and optional TOML overrides.

    Args:
        config_path: Optional explicit path to TOML config file.

    Returns:
        A fully resolved ``AppConfig`` object.

    Raises:
        TypeError: If config values are wrong types.
        ValueError: If config values are invalid.
    """
    resolved_config_path = _default_config_path(config_path)
    values = _read_config_values(resolved_config_path)

    project_root = _as_path(
        values.get("project_root", resolved_config_path.parent),
        "project_root",
        resolved_config_path.parent,
    )
    data_dir = _as_path(
        values.get("data_dir", project_root / DEFAULT_DATA_DIRNAME),
        "data_dir",
        project_root,
    )

    raw_log_level = values.get("log_level", DEFAULT_LOG_LEVEL)
    if not isinstance(raw_log_level, str):
        raise TypeError(
            "Invalid value for 'log_level': expected str, "
            f"got {type(raw_log_level).__name__}."
        )
    log_level = raw_log_level.strip().upper()
    if log_level not in VALID_LOG_LEVELS:
        raise ValueError(
            "Invalid value for 'log_level': "
            f"'{raw_log_level}'. Expected one of {sorted(VALID_LOG_LEVELS)}."
        )

    return AppConfig(
        project_root=project_root,
        data_dir=data_dir,
        log_level=log_level,
        config_path=resolved_config_path,
    )


def build_parser(
    default_config_path: str | pathlib.Path | None = None,
) -> argparse.ArgumentParser:
    """Build the CLI parser for the supported command groups.

    Args:
        default_config_path: Optional default shown for ``--config``.

    Returns:
        A configured ``argparse.ArgumentParser`` for supported commands.
    """
    resolved_default_config = _default_config_path(default_config_path)

    common_parent = argparse.ArgumentParser(add_help=False)
    common_parent.add_argument(
        "--config",
        default=str(resolved_default_config),
        help="Path to the TOML configuration file.",
    )

    parser = argparse.ArgumentParser(
        prog="cern-dataops",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        parents=[common_parent],
    )
    command_groups = parser.add_subparsers(dest="command_group", required=True)

    config_parser = command_groups.add_parser(
        COMMAND_GROUP_CONFIG,
        parents=[common_parent],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="Configuration-related commands.",
    )
    config_commands = config_parser.add_subparsers(dest="config_command", required=True)
    config_show_parser = config_commands.add_parser(
        COMMAND_CONFIG_SHOW,
        help="Show resolved configuration.",
    )
    config_show_parser.set_defaults(command_id=COMMAND_ID_CONFIG_SHOW)

    dataset_parser = command_groups.add_parser(
        COMMAND_GROUP_DATASET,
        parents=[common_parent],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="Dataset-related commands.",
    )
    dataset_commands = dataset_parser.add_subparsers(dest="dataset_command", required=True)
    dataset_list_parser = dataset_commands.add_parser(
        COMMAND_DATASET_LIST,
        help="List local dataset entries.",
    )
    dataset_list_parser.set_defaults(command_id=COMMAND_ID_DATASET_LIST)
    register_summary_subcommand(command_groups)

    ingest_parser = command_groups.add_parser(
        COMMAND_GROUP_INGEST,
        help="Ingest raw records into the local repository.",
    )
    ingest_parser.add_argument(
        "repo_dir",
        help="Repository directory containing records.jsonl.",
    )
    ingest_parser.add_argument(
        "raw_records",
        help="JSON array of raw records to ingest.",
    )
    ingest_parser.set_defaults(command_id=COMMAND_ID_INGEST)

    assistant_parser = command_groups.add_parser(
        COMMAND_GROUP_ASSISTANT,
        parents=[common_parent],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="Metadata-first CMS Run 2 NanoAOD assistant commands.",
    )
    assistant_commands = assistant_parser.add_subparsers(dest="assistant_command", required=True)

    assistant_seed_parser = assistant_commands.add_parser(
        COMMAND_ASSISTANT_SEED,
        help="Ingest frozen CERN records and docs into deterministic local seed files.",
    )
    assistant_seed_parser.add_argument(
        "--seed-dir",
        default=str(DEFAULT_ASSISTANT_SEED_DIR),
        help="Directory to write deterministic assistant seed files.",
    )
    assistant_seed_parser.set_defaults(command_id=COMMAND_ID_ASSISTANT_SEED)

    assistant_ask_parser = assistant_commands.add_parser(
        COMMAND_ASSISTANT_ASK,
        help="Ask one metadata-backed question and return structured JSON.",
    )
    assistant_ask_parser.add_argument(
        "question",
        help="Natural-language question for the metadata-first assistant.",
    )
    assistant_ask_parser.add_argument(
        "--seed-dir",
        default=str(DEFAULT_ASSISTANT_SEED_DIR),
        help="Directory containing deterministic assistant seed files.",
    )
    assistant_ask_parser.set_defaults(command_id=COMMAND_ID_ASSISTANT_ASK)

    assistant_eval_parser = assistant_commands.add_parser(
        COMMAND_ASSISTANT_EVAL,
        help="Run the deterministic 20-question evaluation suite.",
    )
    assistant_eval_parser.add_argument(
        "--seed-dir",
        default=str(DEFAULT_ASSISTANT_SEED_DIR),
        help="Directory containing deterministic assistant seed files.",
    )
    assistant_eval_parser.add_argument(
        "--questions-file",
        default=str(DEFAULT_ASSISTANT_EVAL_FILE),
        help="Path to the evaluation question JSON file.",
    )
    assistant_eval_parser.set_defaults(command_id=COMMAND_ID_ASSISTANT_EVAL)

    assistant_demo_parser = assistant_commands.add_parser(
        COMMAND_ASSISTANT_DEMO,
        help="Return the deterministic dimuon invariant-mass demo path.",
    )
    assistant_demo_parser.add_argument(
        "--seed-dir",
        default=str(DEFAULT_ASSISTANT_SEED_DIR),
        help="Directory containing deterministic assistant seed files.",
    )
    assistant_demo_parser.set_defaults(command_id=COMMAND_ID_ASSISTANT_DEMO)

    return parser


def register_summary_subcommand(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the summary CLI command on the provided parser tree.

    Args:
        subparsers: Parent parser's subparser action returned by
            ``ArgumentParser.add_subparsers``.
    """
    summary_parser = subparsers.add_parser(
        COMMAND_GROUP_SUMMARY,
        help="Print repository summary statistics.",
    )
    summary_parser.add_argument(
        COMMAND_SUMMARY_REPO_DIR,
        help="Repository directory containing records.jsonl.",
    )
    summary_parser.set_defaults(command_id=COMMAND_ID_SUMMARY)


def _run_config_show(config: AppConfig) -> int:
    """Print the active application configuration."""
    print(f"project_root={config.project_root}")
    print(f"data_dir={config.data_dir}")
    print(f"log_level={config.log_level}")
    print(f"config_path={config.config_path}")
    return 0


def _run_dataset_list(config: AppConfig) -> int:
    """List direct children under the configured data directory."""
    if not config.data_dir.exists():
        return 0

    for entry in sorted(config.data_dir.iterdir(), key=lambda item: item.name):
        print(entry.name)
    return 0


def init_local_repository(repo_dir: str | os.PathLike[str]) -> pathlib.Path:
    """Create a local JSONL repository file and return its path.

    Args:
        repo_dir: Directory path for repository storage.

    Returns:
        Absolute path to the repository JSONL file.

    Raises:
        TypeError: If ``repo_dir`` is not path-like.
        OSError: If directory or file creation fails.
    """
    if not isinstance(repo_dir, (str, os.PathLike)):
        raise TypeError(
            "Invalid value for 'repo_dir': expected str or os.PathLike, "
            f"got {type(repo_dir).__name__}."
        )

    repository_dir = pathlib.Path(repo_dir).expanduser().resolve()
    repository_dir.mkdir(parents=True, exist_ok=True)
    records_path = repository_dir / RECORDS_JSONL_FILENAME
    records_path.touch(exist_ok=True)
    return records_path


def _fsync_directory(directory: pathlib.Path) -> None:
    """Flush directory metadata to disk after atomic replacement."""
    directory_fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def append_record_atomic(
    repo_dir: str | os.PathLike[str],
    record: dict[str, Any],
) -> None:
    """Append one JSON object record atomically via temp-file replacement.

    Args:
        repo_dir: Directory path for repository storage.
        record: Record payload to append as one JSONL line.

    Raises:
        TypeError: If ``record`` is not a dictionary.
        OSError: If write, fsync, or replace fails.
    """
    if not isinstance(record, dict):
        raise TypeError(
            "Invalid value for 'record': expected dict, "
            f"got {type(record).__name__}."
        )

    records_path = init_local_repository(repo_dir)
    serialized_record = json.dumps(record, ensure_ascii=False) + "\n"
    temp_path: pathlib.Path | None = None

    try:
        temp_fd, temp_name = tempfile.mkstemp(
            prefix=f"{records_path.name}.",
            suffix=".tmp",
            dir=str(records_path.parent),
        )
        temp_path = pathlib.Path(temp_name)

        with os.fdopen(temp_fd, "wb") as temp_file:
            with records_path.open("rb") as source_file:
                temp_file.write(source_file.read())
            temp_file.write(serialized_record.encode("utf-8"))
            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.replace(temp_path, records_path)
        _fsync_directory(records_path.parent)
    except Exception:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                LOGGER.warning(
                    "Failed to remove temporary repository file '%s'.",
                    temp_path,
                )
        raise


def read_records(
    repo_dir: str | os.PathLike[str],
) -> typing.Iterator[dict[str, Any]]:
    """Read and parse repository JSONL records, skipping malformed lines.

    Args:
        repo_dir: Directory path for repository storage.

    Returns:
        Records parsed from each valid JSONL object line.
    """
    records_path = init_local_repository(repo_dir)
    records: list[dict[str, Any]] = []

    with records_path.open("r", encoding="utf-8") as records_file:
        for line_number, line in enumerate(records_file, start=1):
            line_content = line.strip()
            if not line_content:
                continue

            try:
                parsed = json.loads(line_content)
            except json.JSONDecodeError:
                LOGGER.warning(
                    "Skipping malformed JSONL line %d in '%s'.",
                    line_number,
                    records_path,
                )
                continue

            if not isinstance(parsed, dict):
                LOGGER.warning(
                    "Skipping non-object JSONL line %d in '%s'.",
                    line_number,
                    records_path,
                )
                continue

            records.append(parsed)

    return records


def ingest(repo_dir: str, raw_records: list[object]) -> dict[str, int]:
    """Ingest raw records into the local repository with deterministic counters.

    Args:
        repo_dir: Directory path for repository storage.
        raw_records: Candidate raw records to validate and ingest in order.

    Returns:
        Deterministic summary counters for accepted, invalid, and skipped rows.

    Raises:
        TypeError: If ``repo_dir`` is not a string or ``raw_records`` is not a list.
        OSError: If persisting an accepted record fails.
    """
    if not isinstance(repo_dir, str):
        raise TypeError(
            "Invalid value for 'repo_dir': expected str, "
            f"got {type(repo_dir).__name__}."
        )
    if not isinstance(raw_records, list):
        raise TypeError(
            "Invalid value for 'raw_records': expected list, "
            f"got {type(raw_records).__name__}."
        )

    existing_run_ids = {
        record["run_id"]
        for record in read_records(repo_dir)
        if isinstance(record.get("run_id"), str)
    }
    seen_batch_run_ids: set[str] = set()

    accepted = 0
    invalid = 0
    skipped_existing = 0
    skipped_batch = 0

    for record_index, raw_record in enumerate(raw_records, start=1):
        try:
            parsed_record = _parse_record_with_run_id_fallback(raw_record)
        except ValueError as exc:
            invalid += 1
            LOGGER.warning(
                "Skipping invalid record at index %d: %s",
                record_index,
                exc,
            )
            continue

        run_id = parsed_record["run_id"]
        if run_id in existing_run_ids:
            skipped_existing += 1
            continue
        if run_id in seen_batch_run_ids:
            skipped_batch += 1
            continue

        append_record_atomic(repo_dir, parsed_record)
        seen_batch_run_ids.add(run_id)
        accepted += 1

    skipped_duplicates = skipped_existing + skipped_batch
    return {
        INGEST_SUMMARY_ACCEPTED: accepted,
        INGEST_SUMMARY_INVALID: invalid,
        INGEST_SUMMARY_SKIPPED_EXISTING: skipped_existing,
        INGEST_SUMMARY_SKIPPED_BATCH: skipped_batch,
        INGEST_SUMMARY_INSERTED: accepted,
        INGEST_SUMMARY_SKIPPED_DUPLICATES: skipped_duplicates,
    }


def ingest_command(args: argparse.Namespace) -> int:
    """Run the ingest CLI command from parsed namespace arguments.

    Args:
        args: Parsed argparse namespace with ``repo_dir`` and ``raw_records``.

    Returns:
        Exit code: ``0`` on successful ingest, ``2`` on invalid command input.
    """
    repo_dir = getattr(args, "repo_dir", None)
    raw_records_input = getattr(args, "raw_records", None)

    if not isinstance(repo_dir, str):
        raise ValueError("Invalid CLI input: 'repo_dir' must be a string.")

    raw_records: list[object]
    if isinstance(raw_records_input, str):
        try:
            decoded_input = json.loads(raw_records_input)
        except json.JSONDecodeError as exc:
            print(f"Invalid CLI input for 'raw_records': {exc}")
            return 2

        if not isinstance(decoded_input, list):
            print("Invalid CLI input for 'raw_records': expected JSON array.")
            return 2
        raw_records = decoded_input
    elif isinstance(raw_records_input, list):
        raw_records = raw_records_input
    else:
        print("Invalid CLI input for 'raw_records': expected list or JSON array string.")
        return 2

    summary = ingest(repo_dir, raw_records)
    print(json.dumps(summary, sort_keys=True))
    return 0


def query(
    repo_dir: str | pathlib.Path,
    experiment: str | None = None,
    date: str | None = None,
    tag: str | None = None,
) -> list[dict[str, Any]]:
    """Return locally stored records matching exact optional query filters.

    Args:
        repo_dir: Directory path for repository storage.
        experiment: Exact experiment value filter.
        date: Exact UTC date filter in ``YYYY-MM-DD`` derived from ``timestamp``.
        tag: Exact payload tag filter from ``payload['tag']``.

    Returns:
        Canonical records sorted ascending by ``(timestamp, run_id)``.

    Raises:
        TypeError: If any input has an invalid type.
        ValueError: If ``date`` is not in ``YYYY-MM-DD`` format.
    """
    if not isinstance(repo_dir, (str, os.PathLike)):
        raise TypeError(
            "Invalid value for 'repo_dir': expected str or os.PathLike, "
            f"got {type(repo_dir).__name__}."
        )
    if experiment is not None and not isinstance(experiment, str):
        raise TypeError(
            "Invalid value for 'experiment': expected str or None, "
            f"got {type(experiment).__name__}."
        )
    if date is not None and not isinstance(date, str):
        raise TypeError(
            "Invalid value for 'date': expected str or None, "
            f"got {type(date).__name__}."
        )
    if tag is not None and not isinstance(tag, str):
        raise TypeError(
            "Invalid value for 'tag': expected str or None, "
            f"got {type(tag).__name__}."
        )

    normalized_date: str | None = None
    if date is not None:
        try:
            normalized_date = datetime.strptime(date, "%Y-%m-%d").date().isoformat()
        except ValueError as exc:
            raise ValueError(
                "Invalid value for 'date': expected YYYY-MM-DD."
            ) from exc

    matches: list[dict[str, Any]] = []
    for record_index, raw_record in enumerate(read_records(repo_dir), start=1):
        try:
            parsed_record = parse_record(raw_record)
        except ValueError as exc:
            LOGGER.warning(
                "Skipping invalid repository record at index %d during query: %s",
                record_index,
                exc,
            )
            continue

        if experiment is not None and parsed_record["experiment"] != experiment:
            continue
        if normalized_date is not None and parsed_record["timestamp"][:10] != normalized_date:
            continue
        if tag is not None and parsed_record["payload"].get("tag") != tag:
            continue

        matches.append(parsed_record)

    return sorted(matches, key=lambda record: (record["timestamp"], record["run_id"]))


def query_command(args: argparse.Namespace) -> int:
    """Run the query CLI command from parsed namespace arguments.

    Args:
        args: Parsed argparse namespace with ``repo_dir`` and optional filters.

    Returns:
        Exit code: ``0`` on success, ``2`` on invalid command input.
    """
    repo_dir = getattr(args, "repo_dir", None)
    experiment = getattr(args, "experiment", None)
    date = getattr(args, "date", None)
    tag = getattr(args, "tag", None)

    if not isinstance(repo_dir, (str, os.PathLike)):
        raise ValueError(
            "Invalid CLI input: 'repo_dir' must be a string or os.PathLike."
        )

    if experiment is not None and not isinstance(experiment, str):
        print("Invalid CLI input for 'experiment': expected string.")
        return 2
    if date is not None and not isinstance(date, str):
        print("Invalid CLI input for 'date': expected string.")
        return 2
    if tag is not None and not isinstance(tag, str):
        print("Invalid CLI input for 'tag': expected string.")
        return 2

    try:
        records = query(
            repo_dir=repo_dir,
            experiment=experiment,
            date=date,
            tag=tag,
        )
    except (TypeError, ValueError) as exc:
        print(f"Invalid CLI input: {exc}")
        return 2

    for record in records:
        print(json.dumps(record, ensure_ascii=False))
    return 0


def run_assistant_seed_command(args: argparse.Namespace) -> int:
    """Seed frozen CERN Open Data records/docs into deterministic local files."""
    seed_dir = getattr(args, "seed_dir", None)
    if not isinstance(seed_dir, str):
        print("Invalid CLI input for 'seed_dir': expected string.")
        return 2
    result = _ASSISTANT_MODULE.seed_frozen_inputs(seed_dir)
    print(json.dumps(result, sort_keys=True))
    return 0


def run_assistant_ask_command(args: argparse.Namespace) -> int:
    """Answer one question with structured metadata-first assistant output."""
    seed_dir = getattr(args, "seed_dir", None)
    question = getattr(args, "question", None)
    if not isinstance(seed_dir, str):
        print("Invalid CLI input for 'seed_dir': expected string.")
        return 2
    if not isinstance(question, str):
        print("Invalid CLI input for 'question': expected string.")
        return 2
    response = _ASSISTANT_MODULE.build_structured_response(question, seed_dir)
    print(json.dumps(response, ensure_ascii=False, sort_keys=True))
    return 0


def run_assistant_eval_command(args: argparse.Namespace) -> int:
    """Run deterministic assistant evaluation against the frozen 20-question suite."""
    seed_dir = getattr(args, "seed_dir", None)
    questions_file = getattr(args, "questions_file", None)
    if not isinstance(seed_dir, str):
        print("Invalid CLI input for 'seed_dir': expected string.")
        return 2
    if not isinstance(questions_file, str):
        print("Invalid CLI input for 'questions_file': expected string.")
        return 2
    result = _ASSISTANT_MODULE.run_evaluation(seed_dir, questions_file)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def run_assistant_demo_command(args: argparse.Namespace) -> int:
    """Return deterministic dimuon invariant-mass demo path and command templates."""
    seed_dir = getattr(args, "seed_dir", None)
    if not isinstance(seed_dir, str):
        print("Invalid CLI input for 'seed_dir': expected string.")
        return 2
    result = _ASSISTANT_MODULE.get_dimuon_demo(seed_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _normalize_summary_timestamp(value: str) -> str:
    """Validate and normalize a summary timestamp to UTC ISO-8601 ``+00:00``."""
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(
            "expected UTC ISO-8601 timestamp string for 'timestamp'."
        ) from exc

    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("expected UTC timezone for 'timestamp'.")
    return parsed.astimezone(timezone.utc).isoformat()


def run_summary_command(args: argparse.Namespace) -> int:
    """Run the summary CLI command from parsed namespace arguments.

    Args:
        args: Parsed namespace with ``repo_dir``.

    Returns:
        Exit code: ``0`` on success, ``2`` on invalid command input.
    """
    repo_dir = getattr(args, COMMAND_SUMMARY_REPO_DIR, None)
    if not isinstance(repo_dir, (str, os.PathLike)):
        print("Invalid CLI input for 'repo_dir': expected string or os.PathLike.")
        return 2

    timestamp_records: list[dict[str, object]] = []
    for record_index, record in enumerate(read_records(repo_dir), start=1):
        timestamp_input = record.get("timestamp")
        if not isinstance(timestamp_input, str):
            print(
                "Invalid repository record at index "
                f"{record_index}: missing string field 'timestamp'."
            )
            return 2
        try:
            normalized_timestamp = _normalize_summary_timestamp(timestamp_input)
        except ValueError as exc:
            print(f"Invalid repository record at index {record_index}: {exc}")
            return 2
        timestamp_records.append({"timestamp": normalized_timestamp})

    count, min_recorded_at, max_recorded_at = compute_count_range_stats(timestamp_records)
    print(format_summary_output(count, min_recorded_at, max_recorded_at))
    return 0


def compute_count_range_stats(
    records: list[dict[str, object]],
) -> tuple[int, str | None, str | None]:
    """Compute count and min/max timestamp range from normalized records.

    Args:
        records: Ordered list of records containing ``timestamp`` strings.

    Returns:
        Tuple-like ``(count, min_recorded_at, max_recorded_at)`` where min/max
        are ``None`` for an empty input list.

    Raises:
        TypeError: If an item is not a mapping or timestamp string.
        ValueError: If an item mapping is missing a string ``timestamp`` value.
    """
    timestamps: list[str] = []
    for record in records:
        if isinstance(record, str):
            # Compatibility path for the ticket verify command.
            timestamps.append(record)
            continue
        if not isinstance(record, dict):
            raise TypeError(
                "Invalid value in 'records': expected dict or str, "
                f"got {type(record).__name__}."
            )
        timestamp_value = record.get("timestamp")
        if not isinstance(timestamp_value, str):
            raise ValueError(
                "Invalid record for summary: missing string field 'timestamp'."
            )
        timestamps.append(timestamp_value)

    if not timestamps:
        return _CountRangeStats(0, None, None)

    return _CountRangeStats(
        len(timestamps),
        min(timestamps),
        max(timestamps),
    )


def format_summary_output(
    count: int,
    min_recorded_at: str | None,
    max_recorded_at: str | None,
) -> str:
    """Format summary output with deterministic key order and value encoding."""
    return json.dumps(
        {
            SUMMARY_KEY_COUNT: count,
            SUMMARY_KEY_MIN_RECORDED_AT: min_recorded_at,
            SUMMARY_KEY_MAX_RECORDED_AT: max_recorded_at,
        },
        ensure_ascii=False,
    )


def main(argv: collections.abc.Sequence[str] | None = None) -> int:
    """Run the CLI entrypoint and return an exit code.

    Args:
        argv: Optional CLI argument sequence. ``None`` uses process arguments.

    Returns:
        Process-like integer exit code.
    """
    parser = build_parser()
    try:
        args = parser.parse_args(None if argv is None else list(argv))
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 1

    if args.command_id == COMMAND_ID_SUMMARY:
        return run_summary_command(args)
    if args.command_id == COMMAND_ID_ASSISTANT_SEED:
        return run_assistant_seed_command(args)
    if args.command_id == COMMAND_ID_ASSISTANT_ASK:
        return run_assistant_ask_command(args)
    if args.command_id == COMMAND_ID_ASSISTANT_EVAL:
        return run_assistant_eval_command(args)
    if args.command_id == COMMAND_ID_ASSISTANT_DEMO:
        return run_assistant_demo_command(args)
    if args.command_id == COMMAND_ID_INGEST:
        return ingest_command(args)

    config = load_app_config(args.config)
    if args.command_id == COMMAND_ID_CONFIG_SHOW:
        return _run_config_show(config)
    if args.command_id == COMMAND_ID_DATASET_LIST:
        return _run_dataset_list(config)

    parser.error("Unsupported command.")
    return 2


def run_with_exit_handling(argv: collections.abc.Sequence[str] | None = None) -> int:
    """Run the CLI entrypoint with deterministic exception-to-exit-code mapping."""
    configure_logging(DEFAULT_LOG_LEVEL)
    try:
        return int(main(argv))
    except BaseException as exc:
        LOGGER.warning("Unhandled exception during CLI execution: %s", exc)
        return int(_EXIT_CODES_MODULE.map_exception_to_exit_code(exc))
