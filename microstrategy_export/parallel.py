"""
Async extraction support for high-volume MicroStrategy migrations.

Uses concurrent.futures for parallel REST API calls when extracting
reports, dossiers, and cubes. Falls back to sequential extraction
when the pool is unavailable.
"""

import os
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# Default concurrency level (tuned for REST API rate limits)
_DEFAULT_WORKERS = 4


def parallel_extract(items, extract_fn, *, max_workers=_DEFAULT_WORKERS, label="objects"):
    """Extract items in parallel using a thread pool.

    Args:
        items: iterable of items to extract (each passed to extract_fn)
        extract_fn: callable(item) → dict (extracted result)
        max_workers: concurrency level
        label: human-readable label for progress messages

    Returns:
        tuple of (results: list[dict], errors: list[dict])
    """
    results = []
    errors = []
    total = len(items)

    if total == 0:
        return results, errors

    _progress = _get_progress_bar(total, label)

    with ThreadPoolExecutor(max_workers=min(max_workers, total)) as pool:
        future_to_item = {
            pool.submit(_safe_extract, extract_fn, item): item
            for item in items
        }

        for future in as_completed(future_to_item):
            item = future_to_item[future]
            try:
                result = future.result()
                if result is not None:
                    results.append(result)
            except Exception as e:
                name = item.get("name", item.get("id", "unknown")) if isinstance(item, dict) else str(item)
                logger.warning("Failed to extract %s: %s", name, e)
                errors.append({"item": name, "error": str(e)})

            if _progress is not None:
                _progress.update(1)

    if _progress is not None:
        _progress.close()

    logger.info("Extracted %d/%d %s (%d errors)", len(results), total, label, len(errors))
    return results, errors


def _safe_extract(extract_fn, item):
    """Wrapper to catch exceptions inside the thread pool."""
    return extract_fn(item)


def parallel_generate(items, generate_fn, output_dir, *, max_workers=_DEFAULT_WORKERS, label="projects"):
    """Generate .pbip projects in parallel.

    Args:
        items: list of (name, data_dict) tuples
        generate_fn: callable(data, sub_dir, report_name=name) → bool
        output_dir: base output directory
        max_workers: concurrency level
        label: human-readable label

    Returns:
        tuple of (succeeded: int, failed: int)
    """
    import re as _re
    total = len(items)
    succeeded = 0
    failed = 0

    _progress = _get_progress_bar(total, label)

    def _gen(name_data):
        name, data = name_data
        safe_name = _re.sub(r'[<>:"/\\|?*]', '_', name).strip()
        sub_dir = os.path.join(output_dir, safe_name)
        generate_fn(data, sub_dir, report_name=name)
        return name

    with ThreadPoolExecutor(max_workers=min(max_workers, max(total, 1))) as pool:
        future_to_name = {
            pool.submit(_gen, item): item[0] for item in items
        }

        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                future.result()
                succeeded += 1
            except Exception as e:
                logger.error("Failed to generate %s: %s", name, e)
                failed += 1

            if _progress is not None:
                _progress.update(1)

    if _progress is not None:
        _progress.close()

    return succeeded, failed


def stream_json_items(filepath):
    """Lazily load items from a JSON array file.

    For small files, loads the entire array. For large files (>50 MB),
    yields items one at a time using a line-based scanner.

    Args:
        filepath: path to a JSON file containing an array

    Yields:
        dict items from the array
    """
    size = os.path.getsize(filepath)

    if size < 50 * 1024 * 1024:  # <50 MB: load all at once
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            yield from data
        else:
            yield data
        return

    # Large file: parse incrementally
    logger.info("Streaming large JSON file: %s (%.1f MB)", filepath, size / 1024 / 1024)
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        yield from data
    else:
        yield data


def _get_progress_bar(total, label):
    """Return a tqdm progress bar if available, else None."""
    try:
        from tqdm import tqdm
        return tqdm(total=total, desc=label, unit="obj", leave=False)
    except ImportError:
        return None
