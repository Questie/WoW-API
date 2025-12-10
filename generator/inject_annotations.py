#!/usr/bin/env python3
import os
import re
import argparse
from inject_mixin_skip import MIXIN_SKIP_PATTERNS, FUNCTION_SKIP_PATTERNS


def parse_annotations(source_dir):
    """
    Parses all .lua files in source_dir.
    Returns a dict: { "FunctionName": { "lines": ["line1\n", "line2\n"], "source": "/path/to/file.lua" } }
    """
    annotations = {}
    # Regex to find function definitions.
    # Matches: function Name(...) or function Table.Name(...)
    # Does NOT match 'local function ...' (as local is a separate word)
    # logic: strict match on 'function' at start of stripped line?
    # No, we use regex on the line.
    # But for parsing the META files, we expect standard "function Class.Name()" syntax.
    func_regex = re.compile(r"^\s*function\s+([a-zA-Z0-9_.:]+)\s*\(", re.MULTILINE)

    print(f"Scanning source directory: {source_dir}")

    for root, _, files in os.walk(source_dir):
        for file in files:
            if not file.endswith(".lua"):
                continue

            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except Exception as e:
                print(f"Warning: Could not read {path}: {e}")
                continue

            current_block = []

            for line in lines:
                stripped = line.strip()

                # Check for comment lines (captures -- and ---)
                if stripped.startswith("--"):
                    # We store the stripped line + newline to normalize indentation for storage.
                    # This allows us to re-indent correctly when injecting.
                    current_block.append(stripped + "\n")

                elif stripped.startswith("function"):
                    # Check if this is a function definition
                    m = func_regex.match(line)
                    if m:
                        func_name = m.group(1)
                        # We found a function. Even if it has no preceding annotations (current_block is empty),
                        # we record it so we can later check if it exists in the target and remove it from source if so.
                        annotations[func_name] = {
                            "lines": current_block,
                            "source": path,
                        }

                        # Reset block after function definition
                        current_block = []

                elif not stripped:
                    # Empty line. Clear block to avoid attaching disconnected comments.
                    current_block = []

                else:
                    # Any other line (code, tables, etc.)
                    current_block = []

    print(f"Found annotations for {len(annotations)} functions.")
    return annotations


def parse_mixins(source_dir):
    """
    Parses all .lua files in source_dir for mixin definitions.
    Returns a dict: { "MixinName": { "lines": ["line1\n", "line2\n"], "source": "/path/to/file.lua" } }
    """
    mixins = {}
    # Matches: MixinName = {} or MixinName = {};
    # Capture group 1: MixinName
    mixin_regex = re.compile(r"^([a-zA-Z0-9_]+)\s*=\s*\{\}\s*;?$", re.MULTILINE)

    print(f"Scanning source directory for mixins: {source_dir}")

    for root, _, files in os.walk(source_dir):
        for file in files:
            if not file.endswith(".lua"):
                continue

            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except Exception as e:
                print(f"Warning: Could not read {path}: {e}")
                continue

            current_block = []

            for line in lines:
                stripped = line.strip()

                if stripped.startswith("--"):
                    current_block.append(stripped + "\n")

                elif "=" in stripped:  # Optimization check
                    m = mixin_regex.match(stripped)
                    if m:
                        mixin_name = m.group(1)
                        # We capture it even if no annotations, same logic as functions
                        mixins[mixin_name] = {
                            "lines": current_block,
                            "source": path,
                        }
                        current_block = []
                    else:
                        current_block = []
                elif not stripped:
                    current_block = []
                else:
                    current_block = []

    print(f"Found definitions for {len(mixins)} mixins/tables.")
    return mixins


def inject_mixins(target_dir, mixins_map, dry_run=False):
    """
    Scans target_dir for mixin definitions and injects annotations.
    """
    # Same regex for target matching
    mixin_regex = re.compile(r"^([a-zA-Z0-9_]+)\s*=\s*\{\}\s*;?$", re.MULTILINE)

    print(f"Scanning target directory for mixins: {target_dir}")

    modified_count = 0
    matched_mixins_set = set()

    for root, _, files in os.walk(target_dir):
        for file in files:
            if not file.endswith(".lua"):
                continue

            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except Exception as e:
                print(f"Warning: Could not read {path}: {e}")
                continue

            new_lines = []
            file_modified = False

            for line in lines:
                stripped = line.strip()
                m = mixin_regex.match(stripped)

                if m:
                    mixin_name = m.group(1)
                    if mixin_name in mixins_map:
                        matched_mixins_set.add(mixin_name)
                        anno_data = mixins_map[mixin_name]
                        anno_lines = anno_data["lines"]
                        source_file = anno_data["source"]

                        # Duplicate check (heuristic)
                        already_present = False
                        if len(new_lines) >= len(anno_lines):
                            last_n = new_lines[-len(anno_lines) :]
                            clean_last_n = [l.strip() for l in last_n]
                            clean_anno = [l.strip() for l in anno_lines]
                            if clean_last_n == clean_anno:
                                already_present = True

                        if not already_present and anno_lines:
                            if dry_run:
                                print(
                                    f"[Dry Run] Injecting mixin docs for: {mixin_name} in {path} (from {source_file})"
                                )
                            else:
                                print(
                                    f"Injecting mixin docs for: {mixin_name} in {path} (from {source_file})"
                                )

                            # Mixins are usually global, assume 0 indentation for docs
                            # Or matches line indentation?
                            # stripped matched, so we need indentation from original line
                            # Fix for potential bug where indent includes part of the line content if trailing whitespace exists
                            # Use lstrip to calculate indentation correctly
                            indent = line[: len(line) - len(line.lstrip())]

                            # Get skip patterns for this mixin
                            skip_patterns = [
                                re.compile(p)
                                for p in MIXIN_SKIP_PATTERNS.get(mixin_name, [])
                            ]

                            for al in anno_lines:
                                # Filter out ---@meta and ---@class tags
                                if re.match(r"^\s*---@meta", al) or re.match(
                                    r"^\s*---@class", al
                                ):
                                    continue

                                # Check against manual skip patterns
                                should_skip = False
                                for pattern in skip_patterns:
                                    if pattern.match(al):
                                        should_skip = True
                                        break
                                if should_skip:
                                    continue

                                new_lines.append(indent + al)

                            file_modified = True
                            modified_count += 1

                new_lines.append(line)

            if file_modified and not dry_run:
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.writelines(new_lines)
                except Exception as e:
                    print(f"Error writing to {path}: {e}")

    if dry_run:
        print(f"[Dry Run] Would have injected docs into {modified_count} mixins.")
    else:
        print(f"Injected docs into {modified_count} mixins.")

    return matched_mixins_set


def remove_source_mixins(mixins_map, matched_mixins, dry_run=False):
    """
    Removes mixin definitions and their annotations from source files.
    """
    print("Cleaning up source mixins...")

    files_to_process = {}
    for name in matched_mixins:
        if name in mixins_map:
            source_file = mixins_map[name]["source"]
            if source_file not in files_to_process:
                files_to_process[source_file] = set()
            files_to_process[source_file].add(name)

    removed_count = 0
    mixin_regex = re.compile(r"^([a-zA-Z0-9_]+)\s*=\s*\{\}\s*;?$", re.MULTILINE)

    for source_file, mixin_names in files_to_process.items():
        try:
            with open(source_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Warning: Could not read {source_file}: {e}")
            continue

        new_lines = []
        pending_block = []
        file_modified = False

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("--"):
                pending_block.append(line)
                continue

            m = mixin_regex.match(stripped)
            if m:
                name = m.group(1)
                if name in mixin_names:
                    # Found mixin to remove
                    if dry_run:
                        print(
                            f"[Dry Run] Removing source mixin definition {name} in {source_file}"
                        )
                    else:
                        print(
                            f"Removing source mixin definition {name} in {source_file}"
                        )

                    file_modified = True
                    removed_count += 1
                    pending_block = []  # Discard annotations
                    continue  # Skip line

            # Not matched or not to remove
            if not stripped:
                new_lines.extend(pending_block)
                pending_block = []
                new_lines.append(line)
                continue

            new_lines.extend(pending_block)
            pending_block = []
            new_lines.append(line)

        new_lines.extend(pending_block)

        # Cleanup blank lines
        cleaned_lines = []
        last_was_blank = False
        for line in new_lines:
            is_blank = not line.strip()
            if is_blank:
                if last_was_blank:
                    continue
                cleaned_lines.append(line)
                last_was_blank = True
            else:
                cleaned_lines.append(line)
                last_was_blank = False

        if file_modified and not dry_run:
            try:
                with open(source_file, "w", encoding="utf-8") as f:
                    f.writelines(cleaned_lines)
            except Exception as e:
                print(f"Error writing {source_file}: {e}")

    if dry_run:
        print(f"[Dry Run] Would have removed {removed_count} mixins.")
    else:
        print(f"Removed {removed_count} mixins.")


def inject_annotations(target_dir, annotations_map, dry_run=False):
    """
    Scans target_dir for .lua files.
    If a function definition matches a key in annotations_map,
    injects the annotation lines before it.
    """
    # Regex to capture indentation and function name
    # We use standard regex, but we will clean lines with prefixes before matching
    func_regex = re.compile(r"^(\s*)function\s+([a-zA-Z0-9_.:]+)\s*\(", re.MULTILINE)

    # Regex to identify and strip prefixes like --[[static]]
    prefix_regex = re.compile(r"^(\s*)(--\[\[.*?\]\]\s*)(function.*)$")

    print(f"Scanning target directory: {target_dir}")
    if dry_run:
        print("Dry run enabled. No files will be modified.")

    modified_count = 0
    total_files_checked = 0
    matched_functions_set = set()

    for root, _, files in os.walk(target_dir):
        for file in files:
            if not file.endswith(".lua"):
                continue

            total_files_checked += 1
            path = os.path.join(root, file)

            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except Exception as e:
                print(f"Warning: Could not read {path}: {e}")
                continue

            new_lines = []
            file_modified = False

            for line in lines:
                # Pre-processing: Strip prefix if present
                clean_line_content = line
                pm = prefix_regex.match(line)
                if pm:
                    indent = pm.group(1)
                    # prefix = pm.group(2) # e.g. "--[[static]] "
                    rest = pm.group(3)
                    clean_line_content = indent + rest
                    # We will append this cleaned line to new_lines instead of the original line
                    # But we also need to use it for matching

                    if not file_modified:
                        # We are modifying the file by cleaning it (even if we don't inject)
                        # But strictly speaking, the user said "clean the lines into being parsed"
                        # If we just clean it in memory for parsing, we don't remove it from file.
                        # User said: "lets just remove it... clean the lines... into being parsed"
                        # implying we should save the cleaned version.
                        file_modified = True  # We are stripping the prefix
                        if dry_run:
                            print(f"[Dry Run] Stripping prefix from line in {path}")

                    # Update line to be the cleaned version for subsequent logic
                    # Ensure we preserve newline if original had one
                    suffix = ""
                    if line.endswith("\n") and not clean_line_content.endswith("\n"):
                        suffix = "\n"

                    line = clean_line_content + suffix

                m = func_regex.match(line)
                if m:
                    indent = m.group(1)
                    func_name = m.group(2)

                    if func_name in annotations_map:
                        matched_functions_set.add(func_name)
                        anno_data = annotations_map[func_name]
                        anno_lines = anno_data["lines"]
                        source_file = anno_data["source"]

                        # Check for duplicates to prevent double injection
                        # Heuristic: Compare the last N lines of new_lines with the annotation
                        already_present = False
                        if len(new_lines) >= len(anno_lines):
                            last_n = new_lines[-len(anno_lines) :]
                            # Normalize for comparison
                            clean_last_n = [l.strip() for l in last_n]
                            clean_anno = [l.strip() for l in anno_lines]

                            if clean_last_n == clean_anno:
                                already_present = True

                        if not already_present:
                                    # Inject annotations
                            # We prepend the indentation found on the function line

                            # Get skip patterns for this function
                            skip_patterns = [
                                re.compile(p)
                                for p in FUNCTION_SKIP_PATTERNS.get(func_name, [])
                            ]

                            # --- Parameter Matching Logic ---
                            # Check if parameters match between code and docs
                            # Target: function Name(p1, p2) -> "p1, p2"
                            # We already matched func_regex on 'line', which captured groups 1(indent) and 2(name).
                            # We need to capture the args part now.
                            args_match = re.search(r"\(([^)]*)\)", line)
                            if args_match:
                                target_args_str = args_match.group(1)
                                target_params = [
                                    p.strip()
                                    for p in target_args_str.split(",")
                                    if p.strip()
                                ]

                                # Parse doc params from anno_lines
                                # anno_lines are strings like "---@param foo string\n"
                                doc_params_indices = []
                                doc_params_names = []

                                for i, al in enumerate(anno_lines):
                                    pm = re.search(r"^\s*---@param\s+(\w+)", al)
                                    if pm:
                                        doc_params_indices.append(i)
                                        doc_params_names.append(pm.group(1))

                                # Compare
                                if (
                                    len(target_params) == len(doc_params_names)
                                    and len(target_params) > 0
                                ):
                                    # Attempt to map
                                    replacements = {}
                                    for i, (tp, dp) in enumerate(
                                        zip(target_params, doc_params_names)
                                    ):
                                        if tp != dp:
                                            # Mismatch found: e.g. target='self', doc='button'
                                            replacements[dp] = tp
                                            if dry_run:
                                                print(
                                                    f"[Dry Run] Param mismatch for {func_name}: doc='{dp}' vs code='{tp}'. fixing."
                                                )
                                            else:
                                                print(
                                                    f"Param mismatch for {func_name}: doc='{dp}' vs code='{tp}'. fixing."
                                                )

                                    # Apply replacements to anno_lines (in memory copy)
                                    if replacements:
                                        new_anno_lines = list(anno_lines)  # copy
                                        for idx in doc_params_indices:
                                            original_line = new_anno_lines[idx]
                                            # We need to find which param this line is for
                                            pm = re.search(
                                                r"^\s*---@param\s+(\w+)", original_line
                                            )
                                            if pm:
                                                pname = pm.group(1)
                                                if pname in replacements:
                                                    new_name = replacements[pname]
                                                    # Replace the word 'pname' with 'new_name' in the line
                                                    # Also append the old name as a comment at the end
                                                    # Check if line ends with newline
                                                    suffix = ""
                                                    if original_line.endswith("\n"):
                                                        suffix = "\n"
                                                        original_line = (
                                                            original_line.rstrip("\n")
                                                        )

                                                    # Replace name
                                                    # Use regex to replace first occurrence of parameter name after @param
                                                    new_line_content = re.sub(
                                                        r"(@param\s+)"
                                                        + re.escape(pname),
                                                        r"\1" + new_name,
                                                        original_line,
                                                        count=1,
                                                    )

                                                    # Append old name
                                                    new_line = f"{new_line_content} {pname}{suffix}"
                                                    new_anno_lines[idx] = new_line
                                        anno_lines = new_anno_lines
                            # -------------------------------

                            if dry_run:
                                print(
                                    f"[Dry Run] Would inject annotations for: {func_name} in {path} (from {source_file})"
                                )
                            else:
                                print(
                                    f"Injecting annotations for: {func_name} in {path} (from {source_file})"
                                )

                            for anno_line in anno_lines:
                                # Check against manual skip patterns
                                should_skip = False
                                for pattern in skip_patterns:
                                    if pattern.match(anno_line):
                                        should_skip = True
                                        break
                                if should_skip:
                                    continue

                                # anno_line has \n but no indent.
                                new_lines.append(indent + anno_line)

                            file_modified = True
                            modified_count += 1
                            # print(f"Injected {func_name} into {file}")

                new_lines.append(line)

            if file_modified and not dry_run:
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.writelines(new_lines)
                except Exception as e:
                    print(f"Error writing to {path}: {e}")

    print(f"Checked {total_files_checked} files.")
    if dry_run:
        print(f"Would have injected annotations into {modified_count} functions.")
    else:
        print(f"Injected annotations into {modified_count} functions.")

    # Return list of injected/found function names to facilitate source cleanup
    # We re-scan to return all functions that were 'successfully processed' (i.e., exist in target with annotation)
    # The modified_count only tracks *changes*.
    # But for removal, we want to know if the function *exists* in the target, regardless of whether we just added it or it was already there.
    # To do this accurately, we should probably track it inside the loop.
    # Re-running the loop or accumulating in a set is better.
    # Since we are already iterating, let's accumulate in a set in the loop above.
    # But wait, inject_annotations didn't return anything in previous version.
    # I will modify it to return the set.
    return matched_functions_set


def remove_source_annotations(annotations_map, matched_functions, dry_run=False):
    """
    Removes function definitions and their annotations from the source files
    if they were successfully matched in the target directory.
    """
    print("Cleaning up source annotations...")

    # Group matched functions by source file
    files_to_process = {}
    for func_name in matched_functions:
        if func_name in annotations_map:
            source_file = annotations_map[func_name]["source"]
            if source_file not in files_to_process:
                files_to_process[source_file] = set()
            files_to_process[source_file].add(func_name)

    removed_count = 0

    # Regex to capture function definition for matching
    func_regex = re.compile(r"^\s*function\s+([a-zA-Z0-9_.:]+)\s*\(", re.MULTILINE)
    # Regex to check for end of function at column 0
    end_regex = re.compile(r"^end\s*$", re.MULTILINE)

    for source_file, func_names in files_to_process.items():
        try:
            with open(source_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Warning: Could not read source file {source_file}: {e}")
            continue

        new_lines = []
        pending_block = []
        file_modified = False
        skip_lines_until_end = False

        for i, line in enumerate(lines):
            # If we are inside a deleted block, check if this line ends it
            if skip_lines_until_end:
                # We assume function body lines are indented, so they won't match ^end
                # But the user said "function always starts at column 0 and so does the closing end."
                # So we just look for ^end
                if end_regex.match(line):
                    skip_lines_until_end = False
                    # We consumed the 'end' line too.
                continue

            stripped = line.strip()

            # Accumulate comments (annotations)
            if stripped.startswith("--"):
                pending_block.append(line)
                continue

            # Check function definition
            if stripped.startswith("function"):
                m = func_regex.match(line)
                if m:
                    func_name = m.group(1)
                    if func_name in func_names:
                        # Found a function to remove.
                        if dry_run:
                            print(
                                f"[Dry Run] Removing source definition for {func_name} in {source_file}"
                            )
                        else:
                            print(
                                f"Removing source definition for {func_name} in {source_file}"
                            )

                        file_modified = True
                        removed_count += 1
                        pending_block = []  # Discard annotations

                        # Check if it's a one-liner
                        if stripped.endswith("end"):
                            # One-liner, just skip this line
                            continue
                        else:
                            # Multi-line, start skipping until we find 'end' at column 0
                            skip_lines_until_end = True
                            continue

                # If regex didn't match or not in removal list: keep.
                new_lines.extend(pending_block)
                pending_block = []
                new_lines.append(line)
                continue

            # Empty line or other code
            if not stripped:
                new_lines.extend(pending_block)
                pending_block = []
                new_lines.append(line)
                continue

            # Other line (e.g. table def)
            new_lines.extend(pending_block)
            pending_block = []
            new_lines.append(line)

        # End of loop, flush remaining
        new_lines.extend(pending_block)

        # Post-processing: Collapse multiple blank lines
        cleaned_lines = []
        last_was_blank = False

        for line in new_lines:
            is_blank = not line.strip()

            if is_blank:
                if last_was_blank:
                    # Skip duplicate blank line
                    continue
                else:
                    # Keep first blank line
                    cleaned_lines.append(line)
                    last_was_blank = True
            else:
                cleaned_lines.append(line)
                last_was_blank = False

        if file_modified and not dry_run:
            try:
                with open(source_file, "w", encoding="utf-8") as f:
                    f.writelines(cleaned_lines)
            except Exception as e:
                print(f"Error writing to {source_file}: {e}")

    if dry_run:
        print(
            f"[Dry Run] Would have removed {removed_count} function definitions from source."
        )
    else:
        print(f"Removed {removed_count} function definitions from source.")


def cleanup_empty_files(source_dir, dry_run=False):
    """
    Scans the source directory and removes files that contain only whitespace or meta tags.
    """
    print("Cleaning up empty source files...")

    # Regex for lines that are allowed (whitespace or meta tags)
    # If a line matches this, it counts as "skippable" for deletion purposes.
    # If a line does NOT match this, the file is kept.
    allowed_line_regex = re.compile(r"^\s*(?:---@meta.*)?$")

    removed_count = 0

    for root, _, files in os.walk(source_dir):
        for file in files:
            if not file.endswith(".lua"):
                continue

            path = os.path.join(root, file)

            should_remove = True
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    for line in lines:
                        # If we find any line that is NOT whitespace and NOT ---@meta
                        # then the file contains "real" content and should be kept.
                        if not allowed_line_regex.match(line):
                            should_remove = False
                            break
            except Exception as e:
                print(f"Warning: Could not read {path}: {e}")
                continue

            if should_remove:
                if dry_run:
                    print(f"[Dry Run] Removing empty file: {path}")
                else:
                    print(f"Removing empty file: {path}")
                    try:
                        os.remove(path)
                    except Exception as e:
                        print(f"Error removing {path}: {e}")

                removed_count += 1

    if dry_run:
        print(f"[Dry Run] Would have removed {removed_count} empty files.")
    else:
        print(f"Removed {removed_count} empty files.")


def main():
    parser = argparse.ArgumentParser(
        description="Inject LuaLS annotations from source definitions to implementation files."
    )
    parser.add_argument(
        "--source",
        default="./API-Vanilla/FrameXML",
        help="Path to folder containing annotated source files (default: ./API-Vanilla/FrameXML)",
    )
    parser.add_argument(
        "--target",
        default="./API-Vanilla/_UI",
        help="Path to folder containing implementation files to update (default: ./API-Vanilla/_UI)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without modifying files",
    )
    parser.add_argument(
        "--keep-source",
        action="store_true",
        help="Do not remove functions and annotations from source files after successful injection",
    )

    args = parser.parse_args()

    # Resolve paths relative to current working directory (which is usually generator/)
    source_path = os.path.abspath(args.source)
    target_path = os.path.abspath(args.target)

    if not os.path.isdir(source_path):
        print(f"Error: Source directory not found: {source_path}")
        return

    if not os.path.isdir(target_path):
        print(f"Error: Target directory not found: {target_path}")
        return

    # 1. Load Annotations
    annotations = parse_annotations(source_path)

    # 1b. Load Mixins
    mixins = parse_mixins(source_path)

    if not annotations and not mixins:
        print("No annotations or mixins found. Exiting.")
        return

    # 2. Inject
    injected_funcs = inject_annotations(target_path, annotations, dry_run=args.dry_run)
    injected_mixins = inject_mixins(target_path, mixins, dry_run=args.dry_run)

    # 3. Report Missing
    all_funcs = set(annotations.keys())
    missing_funcs = all_funcs - injected_funcs
    if missing_funcs:
        print("\nFunctions found in Source but NOT found in Target:")
        for func in sorted(missing_funcs):
            # Print function name and its source file for clarity
            source_file = annotations[func]["source"]
            print(f" - {func} ({source_file})")
        print("\n")

    all_mixins = set(mixins.keys())
    missing_mixins = all_mixins - injected_mixins
    if missing_mixins:
        print("\nMixins found in Source but NOT found in Target:")
        for mixin in sorted(missing_mixins):
            source_file = mixins[mixin]["source"]
            print(f" - {mixin} ({source_file})")
        print("\n")

    # 4. Cleanup Source
    if not args.keep_source:
        remove_source_annotations(annotations, injected_funcs, dry_run=args.dry_run)
        remove_source_mixins(mixins, injected_mixins, dry_run=args.dry_run)
        # cleanup_empty_files(source_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
