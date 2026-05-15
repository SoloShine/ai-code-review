"""Diff truncation utilities for handling large changesets."""

from dataclasses import dataclass, field


@dataclass
class TruncationResult:
    """Result of diff truncation."""
    diff: str
    truncated: bool
    original_lines: int
    kept_lines: int
    skipped_files: list  # files whose diffs were dropped
    skipped_file_summaries: dict  # {filepath: "N lines of .ext changes"}
    reason: str = ""


@dataclass
class FileDiff:
    """A single file's diff content."""
    filepath: str
    diff: str
    line_count: int


def split_diff_by_file(diff: str) -> list:
    """Split a multi-file diff into per-file diff chunks.

    Returns a list of FileDiff objects, each containing the filepath
    and the raw diff text for that file only.
    """
    if not diff:
        return []

    lines = diff.splitlines(keepends=True)
    file_boundaries = []
    for i, line in enumerate(lines):
        if line.startswith("diff --git"):
            parts = line.split()
            filepath = parts[-1].lstrip("b/") if len(parts) >= 4 else ""
            file_boundaries.append((i, filepath))

    if not file_boundaries:
        return [FileDiff(filepath="unknown", diff=diff, line_count=len(lines))]

    result = []
    for idx, (start, fp) in enumerate(file_boundaries):
        end = file_boundaries[idx + 1][0] if idx + 1 < len(file_boundaries) else len(lines)
        chunk = "".join(lines[start:end])
        result.append(FileDiff(filepath=fp, diff=chunk, line_count=end - start))

    return result


def group_files_for_review(
    file_diffs: list,
    large_file_threshold: int = 200,
    group_max_lines: int = 500,
    group_max_files: int = 15,
) -> list:
    """Group file diffs into review batches.

    Strategy:
    - Files with line_count > large_file_threshold: reviewed individually
    - Small files: grouped together (up to group_max_lines total, group_max_files count)

    Returns a list of lists, where each inner list is a batch of FileDiff
    objects to be reviewed in a single LLM call.
    """
    if not file_diffs:
        return []

    large_files = []
    small_files = []
    for fd in file_diffs:
        if fd.line_count > large_file_threshold:
            large_files.append(fd)
        else:
            small_files.append(fd)

    batches = []
    # Each large file gets its own batch
    for fd in large_files:
        batches.append([fd])

    # Group small files into batches
    current_batch = []
    current_lines = 0
    for fd in small_files:
        if current_batch and (
            len(current_batch) >= group_max_files
            or current_lines + fd.line_count > group_max_lines
        ):
            batches.append(current_batch)
            current_batch = []
            current_lines = 0
        current_batch.append(fd)
        current_lines += fd.line_count

    if current_batch:
        batches.append(current_batch)

    return batches


def truncate_single_file_diff(diff: str, max_lines: int = 500, max_chars: int = 30000) -> str:
    """Truncate a single file's diff using sandwich strategy. Returns the truncated diff."""
    if not diff:
        return diff
    lines = diff.splitlines(keepends=True)
    if len(lines) <= max_lines and len(diff) <= max_chars:
        return diff

    result = truncate_diff(diff, max_lines=max_lines, max_chars=max_chars, max_files=1)
    return result.diff


def _classify_diff_lines(lines: list) -> dict:
    """Classify diff lines into added/removed/context counts."""
    stats = {"added": 0, "removed": 0, "context": 0, "header": 0}
    for line in lines:
        s = line.strip()
        if s.startswith(("diff --git", "---", "+++", "@@", "... (")):
            stats["header"] += 1
        elif s.startswith("+") and not s.startswith("+++"):
            stats["added"] += 1
        elif s.startswith("-") and not s.startswith("---"):
            stats["removed"] += 1
        else:
            stats["context"] += 1
    return stats


def _make_section_summary(lines: list) -> str:
    """Generate a brief summary of what's in a truncated section."""
    stats = _classify_diff_lines(lines)
    parts = []
    if stats["added"]:
        parts.append(f"+{stats['added']}")
    if stats["removed"]:
        parts.append(f"-{stats['removed']}")
    if not parts:
        return f"{len(lines)} lines"
    return f"{len(lines)} lines ({', '.join(parts)})"


def truncate_diff(
    diff: str,
    max_lines: int = 500,
    max_chars: int = 30000,
    max_files: int = 20,
) -> TruncationResult:
    """Truncate a diff to fit within size limits.

    Strategy:
    1. If total file count > max_files, keep first N and summarize the rest
    2. If diff lines > max_lines, use sandwich truncation per-file:
       keep head + tail, summarize middle
    3. If total chars > max_chars, do a hard truncation with a note

    Returns a TruncationResult with the possibly-shortened diff and metadata.
    """
    if not diff:
        return TruncationResult(
            diff="", truncated=False, original_lines=0,
            kept_lines=0, skipped_files=[], skipped_file_summaries={}
        )

    lines = diff.splitlines(keepends=True)
    original_lines = len(lines)

    # --- Phase 1: file count limit ---
    file_boundaries = []  # (start_line_idx, filepath)
    for i, line in enumerate(lines):
        if line.startswith("diff --git"):
            parts = line.split()
            filepath = parts[-1].lstrip("b/") if len(parts) >= 4 else ""
            file_boundaries.append((i, filepath))

    skipped_files = []
    skipped_file_summaries = {}

    if len(file_boundaries) > max_files:
        cutoff = file_boundaries[max_files][0]
        for _, fp in file_boundaries[max_files:]:
            skipped_files.append(fp)

        # Generate summaries for skipped files
        for idx in range(max_files, len(file_boundaries)):
            start = file_boundaries[idx][0]
            end = file_boundaries[idx + 1][0] if idx + 1 < len(file_boundaries) else len(lines)
            fp = file_boundaries[idx][1]
            chunk = lines[start:end]
            skipped_file_summaries[fp] = _make_section_summary(chunk)

        lines = lines[:cutoff]
        file_boundaries = file_boundaries[:max_files]

    # --- Phase 2: per-file sandwich truncation ---
    total = len(lines)
    if total > max_lines:
        num_files = len(file_boundaries) if file_boundaries else 1
        per_file_budget = max(max_lines // max(num_files, 1), 50)

        result_lines = []
        for idx, (start, _fp) in enumerate(file_boundaries):
            end = file_boundaries[idx + 1][0] if idx + 1 < len(file_boundaries) else total
            file_chunk = lines[start:end]

            if len(file_chunk) > per_file_budget:
                # Sandwich: keep header + first half + summary + last quarter
                header_count = 0
                for fl in file_chunk:
                    if fl.startswith(("diff --git", "---", "+++", "@@")):
                        header_count += 1
                    else:
                        break

                content_lines = file_chunk[header_count:]
                budget_for_content = per_file_budget - header_count

                # head_size = 60% of budget, tail_size = 40% of budget
                head_size = int(budget_for_content * 0.6)
                tail_size = budget_for_content - head_size

                head_part = content_lines[:head_size]
                middle_part = content_lines[head_size:-tail_size] if tail_size > 0 else content_lines[head_size:]
                tail_part = content_lines[-tail_size:] if tail_size > 0 else []

                # Build sandwich
                kept = list(file_chunk[:header_count])
                kept.extend(head_part)
                kept.append(
                    f"\n... (省略了 {len(middle_part)} 行变更: "
                    f"{_make_section_summary(middle_part)}) ...\n"
                )
                kept.extend(tail_part)

                result_lines.extend(kept)
            else:
                result_lines.extend(file_chunk)

        # Handle preamble before first file
        if file_boundaries and file_boundaries[0][0] > 0:
            preamble = lines[:file_boundaries[0][0]]
            result_lines = preamble + result_lines

        lines = result_lines

    # --- Phase 3: hard char limit ---
    diff_text = "".join(lines)
    if len(diff_text) > max_chars:
        diff_text = diff_text[:max_chars]
        diff_text += f"\n\n... (hard truncation at {max_chars} chars, original {len(''.join(lines))} chars)"

    # Add skipped files summary as a note at the end if any
    if skipped_file_summaries:
        summary_lines = "\n\n## 已跳过的文件（变更量大，仅保留摘要）\n"
        for fp, summary in skipped_file_summaries.items():
            summary_lines += f"- `{fp}`: {summary}\n"
        diff_text += summary_lines

    kept_lines = len(diff_text.splitlines())
    truncated = (
        len(skipped_files) > 0
        or kept_lines < original_lines
        or len(diff_text) < len("".join(lines))
    )

    reason_parts = []
    if skipped_files:
        reason_parts.append(f"Skipped {len(skipped_files)} file(s)")
    if kept_lines < original_lines:
        reason_parts.append(f"Lines: {original_lines} -> {kept_lines}")

    return TruncationResult(
        diff=diff_text,
        truncated=truncated,
        original_lines=original_lines,
        kept_lines=kept_lines,
        skipped_files=skipped_files,
        skipped_file_summaries=skipped_file_summaries,
        reason="; ".join(reason_parts),
    )
