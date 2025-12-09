#!/usr/bin/env python3
import os
import re
import argparse
import sys


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
                        if current_block:
                            # We found a function with preceding annotations
                            annotations[func_name] = {
                                "lines": current_block,
                                "source": path,
                            }
                            # print(f"Found annotations for: {func_name}")

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


def inject_annotations(target_dir, annotations_map, dry_run=False):
    """
    Scans target_dir for .lua files.
    If a function definition matches a key in annotations_map,
    injects the annotation lines before it.
    """
    # Regex to capture indentation and function name
    func_regex = re.compile(r"^(\s*)function\s+([a-zA-Z0-9_.:]+)\s*\(", re.MULTILINE)

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
                            if dry_run:
                                print(
                                    f"[Dry Run] Would inject annotations for: {func_name} in {path} (from {source_file})"
                                )
                            else:
                                print(
                                    f"Injecting annotations for: {func_name} in {path} (from {source_file})"
                                )

                            for anno_line in anno_lines:
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

        for line in lines:
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
                        # This is a function we want to remove.
                        # Safety check: ensure it is a one-liner stub (ends with 'end')
                        if stripped.endswith("end"):
                            # One liner. Drop pending block and this line.
                            pending_block = []  # Discard annotations
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
                            continue  # Skip adding this line to new_lines
                        else:
                            # Multi-line. Replace annotations and rename function to "_"
                            if dry_run:
                                print(
                                    f"[Dry Run] Renaming multi-line source definition {func_name} to '_' in {source_file}"
                                )
                            else:
                                print(
                                    f"Renaming multi-line source definition {func_name} to '_' in {source_file}"
                                )

                            # 1. Replace annotations with special comment
                            # We match the indentation of the function line
                            indent = line[: len(line) - len(line.lstrip())]
                            pending_block = [
                                indent + f"--- MultiLine , safe remove with underscore ({func_name})\n"
                            ]

                            # 2. Rename function to _
                            # Use regex match positions to ensure we only replace the function name
                            start, end = m.span(1)
                            new_func_line = line[:start] + "_" + line[end:]

                            # Flush annotations and new line
                            new_lines.extend(pending_block)
                            pending_block = []
                            new_lines.append(new_func_line)

                            file_modified = True
                            removed_count += 1
                            continue

                # If regex didn't match or not in removal list, or unsafe: keep.
                new_lines.extend(pending_block)
                pending_block = []
                new_lines.append(line)
                continue

            # Empty line or other code
            if not stripped:
                # Empty line.
                # If we have pending block, it might be a header or disconnected comment.
                # Keep it.
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

        if file_modified and not dry_run:
            try:
                with open(source_file, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
            except Exception as e:
                print(f"Error writing to {source_file}: {e}")

    if dry_run:
        print(
            f"[Dry Run] Would have removed {removed_count} function definitions from source."
        )
    else:
        print(f"Removed {removed_count} function definitions from source.")


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

    if not annotations:
        print("No annotations found. Exiting.")
        return

    # 2. Inject
    injected_funcs = inject_annotations(target_path, annotations, dry_run=args.dry_run)

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

    # 4. Cleanup Source
    if not args.keep_source:
        remove_source_annotations(annotations, injected_funcs, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
