#!/usr/bin/env python3
import os
import argparse
import shutil
import re
import subprocess
import datetime


def parse_toc_file(toc_path):
    """
    Reads a .toc file and returns a set of allowed file paths.
    Ignores header lines (starting with '##') and blank lines.
    Each file entry is normalized (and Windows-style backslashes are converted).
    """
    allowed = set()
    try:
        with open(toc_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("##"):
                    continue
                normalized = os.path.normpath(stripped.replace("\\", os.sep))
                allowed.add(normalized)
    except Exception as e:
        print(f"Error reading {toc_path}: {e}")
    return allowed


unfold_folders = [
    "shared",
    "mists",
    "cata",
    "wrath",
    "tbc",
    "classic",
    "vanilla",
]


def adjust_file_entry(entry, version, addon_name):
    """
    Checks whether the file entry has an extra (redundant) folder level corresponding
    to the version. For example, if entry is:

        Classic/Blizzard_AchievementUI.lua

    and version is "Classic" (and addon_name is "Blizzard_AchievementUI"),
    then remove the third folder so that the result becomes:

        Blizzard_AchievementUI.lua

    If the expected pattern is not detected, return the entry unchanged.
    """
    entry = os.path.normpath(entry)
    parts = entry.split(os.sep)
    # Look for the pattern:
    # parts[0] == version, parts[1] == addon_name, and parts[2] == version.
    if len(parts) >= 2:
        if parts[0].lower() in unfold_folders:
            new_entry = os.sep.join(parts[1:])
            print(f"    Adjusted file entry: {entry} -> {new_entry}")
            return new_entry
    return entry


def create_mixin(file, dest_root, branch, original_path):
    # Extra manual inheritance mapping
    # Will be appended last on the line
    extra_class_inheritence = {
        "MapCanvasMixin": ", Frame",
        "MapCanvasDetailLayerMixin": " : Frame",
        "MapCanvasScrollControllerMixin": " : ScrollFrame",  # Scroll container, i assume is a ScrollFrame
        "MapCanvasPinMixin": " : Button",  # Uses Frame functions, i would assume most icons will be buttons
    }

    # Lookup table for classes that need extra field annotations
    class_fields = {
        "AccountSaveFrameMixin": [
            "---@field LockEditBox EditBox",
            "---@field SaveButton UIButtonMixin",
            "---@field Text FontString",
            "---@field ContentInsets Frame",
            "---@field AlertIcon Texture",
        ],
        "MapCanvasMixin": [
            "---@field ScrollContainer MapCanvasScrollControllerMixin",
            "---@field BorderFrame Frame|unknown",
            "---@diagnostic disable: param-type-mismatch",  # There is a bug in the code we want to ignore
        ],
        "MapCanvasDataProviderMixin": [
            "---@field owningMap MapCanvasMixin",
        ],
        "MapCanvasScrollControllerMixin": [
            "---@field Child Frame|unknown ScrollChild",
            "---@field GetMap fun(): MapCanvasMixin",
        ],
        "MapCanvasPinMixin": [
            "---@field owningMap MapCanvasMixin",
        ],
        # Add more classes and their fields here:
        # "AnotherMixin": [
        #   "---@field SomeField SomeType",
        #   "---@field AnotherField AnotherType"
        # ]
    }

    # Configuration for different patterns and their behaviors
    pattern_configs = [
        {
            "regex": r"^([_A-Z]{3,100}) = {}",
            "action": "markdown",
            "group_index": 1,
        },
        {
            # These use <FrameType>Mixin in their name, so we can use
            "regex": r"^(\w+(Button|ColorSelect|Cooldown|EditBox|FogOfWarFrame|Frame|GameTooltip|MessageFrame|Minimap|ModelScene|ModelSceneActor|MovieFrame|ScrollFrame|SimpleHTML|Slider|StatusBar|UnitPositionFrame)Mixin) = {\s*}",
            "action": "template",
            "output_string": "---@class {0} : {1}",
            "group_index": [1, 2],
        },
        {
            "regex": r"^(\w+(Button|ColorSelect|Cooldown|EditBox|FogOfWarFrame|Frame|GameTooltip|MessageFrame|Minimap|ModelScene|ModelSceneActor|MovieFrame|ScrollFrame|SimpleHTML|Slider|StatusBar|UnitPositionFrame)Mixin) *= *CreateFromMixins\(([^)]+)\);",
            # "regex": r"^(\w+ButtonMixin)\s*=\s*CreateFromMixins\(([^)]+)\);",
            "action": "template",
            # "output_string": "---@class {0} : Button, {1}",
            "output_string": "---@class {0} : {1}, {2}",
            "group_index": [1, 2, 3],  # LHS, RHS
        },
        {
            # Empty mixins
            "regex": r"^(\w+) *= *CreateFromMixins\(\);?",
            "action": "template",
            "output_string": "---@class {0}",
            "group_index": [1],
        },
        {
            "regex": r"^(\w+) *= *CreateFromMixins\(([^)]+)\);?",
            "action": "template",
            "output_string": "---@class {0} : {1}",
            "group_index": [1, 2],  # LHS, RHS
        },
        {
            # Mixed mixins with table (Added Mixin to the end to be safe)
            "regex": r"^(\w+) *= *CreateFromMixins\((.+Mixin), *\{",
            "action": "template",
            "output_string": "---@class {0} : {1}",
            "group_index": [1, 2],
        },
        {
            "regex": r"^(\w+) = (\w+):CreateSubPin\(",
            "action": "template",
            "output_string": "---@class {0} : {1}",
            "group_index": [1, 2],  # [child_class, parent_class]
        },
        {
            # Adds support for CameraRegistry and DoublyLinkedListMixin
            "regex": r"^(\w+Mixin|\w+Registry) *= *{.*?};?$",
            "action": "template",
            "output_string": "---@class {0}",
            "group_index": [1],
        },
        {
            "regex": r"^local (\w+) = {\s*}",
            "action": "template",
            "output_string": "---@class {0}",
            "group_index": [1],
        },
        {
            "regex": r"^(\w+) *= *{\s*}",
            "action": "template",
            "output_string": "---@class {0}",
            "group_index": [1],
        },
        {
            # Match multi-line table assignments
            "regex": r"^(\w+) *= *{*$",
            "action": "template",
            "output_string": "---@class {0}",
            "group_index": [1],
        },
        # Add more patterns here as needed:
        # {
        #   "regex": r"^(\w+) = (\w+):SomeMethod\(",
        #   "action": "template",
        #   "output_string": "---@class {0} : {1}",
        #   "group_index": [1, 2]
        # }
        # ? Always leave this last
        {
            "regex": r"^(\w+Mixin) =",
            "action": "markdown",
            "group_index": 1,
        },
    ]

    with open(file, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    with open(file, "w", encoding="utf-8") as f:
        # Determine comment style based on file extension
        is_xml = file.lower().endswith(".xml")
        if is_xml:
            f.write(f"<!-- Original Path: {original_path} -->\n")
            f.write("<!-- Auto-moved, do not edit manually -->\n")
        else:
            f.write(f"-- Original Path: {original_path}\n")
            f.write("-- Auto-generated LuaLS Annotations, do not edit manually\n")
            f.write("---@meta _\n")

        for line in lines:
            # Remove strange BOM character if present
            line = line.replace("\ufeff", "")
            if is_xml:
                url = f"https://raw.githubusercontent.com/BigWigsMods/WoWUI/refs/heads/{branch}/Interface/AddOns/Blizzard_SharedXML/UI.xsd"
                line = re.sub(
                    r"(?:\.\.[\\/])+(?:.*?[\\/])?UI\.xsd",
                    url,
                    line,
                )

            matched = False

            for config in pattern_configs:
                m = re.match(config["regex"], line)
                if m:
                    if config["action"] == "template":
                        groups = [m.group(i) for i in config["group_index"]]
                        annotation = config["output_string"].format(*groups)

                        class_name = groups[0]  # First group is always the class name
                        if class_name in extra_class_inheritence:
                            extra_class = extra_class_inheritence[class_name]
                            annotation += extra_class

                        f.write(f"{annotation}\n")

                        # Check if this class has extra fields to inject
                        if class_name in class_fields:
                            for field in class_fields[class_name]:
                                f.write(f"{field}\n")

                        f.write(line)
                    elif config["action"] == "markdown":
                        if isinstance(config["group_index"], list):
                            class_name = m.group(config["group_index"][0])
                        else:
                            class_name = m.group(config["group_index"])
                        potential_classes_file = os.path.join(
                            dest_root, "potential_classes.md"
                        )
                        with open(
                            potential_classes_file, "a", encoding="utf-8"
                        ) as md_file:
                            md_file.write(f"- {class_name}\n")
                        f.write(line)  # Write original line without annotation

                    matched = True
                    break

            if not matched:
                f.write(line)


def process_addon_directory(
    addon_dir, version, source_addons_root, dest_addons_root, branch
):
    """
    For a given addon folder, select the appropriate TOC file based on version priority,
    then copy the referenced files.
    """
    addon_name = os.path.basename(addon_dir)
    toc_files = [f for f in os.listdir(addon_dir) if f.lower().endswith(".toc")]
    if not toc_files:
        return

    selected_toc = None

    # Map version to specific suffix
    # version is expected to be capitalized e.g. "Vanilla", "Classic", "Mainline"

    # We need to handle case insensitivity for file lookups
    toc_map = {t.lower(): t for t in toc_files}

    # 1. Try specific version match (e.g. Addon_Vanilla.toc)
    target_specific = f"{addon_name}_{version}.toc".lower()
    if target_specific in toc_map:
        selected_toc = toc_map[target_specific]
        print(f"  Selected TOC (Specific): {selected_toc}")

    # 2. If not found, and version is a classic version, try _Classic.toc
    if not selected_toc and version in ["Vanilla", "TBC", "Wrath", "Cata", "Mists"]:
        target_classic = f"{addon_name}_Classic.toc".lower()
        if target_classic in toc_map:
            selected_toc = toc_map[target_classic]
            print(f"  Selected TOC (Classic): {selected_toc}")

    # 3. If not found, try base Addon.toc
    if not selected_toc:
        target_base = f"{addon_name}.toc".lower()
        if target_base in toc_map:
            selected_toc = toc_map[target_base]
            print(f"  Selected TOC (Base): {selected_toc}")

    if not selected_toc:
        print(
            f"  No suitable TOC file found for version '{version}' in {addon_dir}. Skipping."
        )
        return

    toc_path = os.path.join(addon_dir, selected_toc)
    print(f"\nProcessing addon in folder: {addon_dir}")
    print(f"  Using TOC: {selected_toc}")

    # Parse the TOC file
    file_entries = []
    try:
        with open(toc_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("##"):
                continue

            # Handle file entry
            normalized = os.path.normpath(stripped.replace("\\", os.sep))
            file_entries.append(normalized)

            if normalized.lower().endswith(".xml"):
                # Load XML includes
                xml_files = load_xml(os.path.join(addon_dir, normalized))
                for xml_file in xml_files:
                    print(f"    Adding XML file: {xml_file}")
                    file_entries.append(xml_file)

    except Exception as e:
        print(f"Error processing {toc_path}: {e}")
        return

    # Determine the addon folder's relative path (relative to the source addons root)
    rel_addon_dir = os.path.relpath(addon_dir, source_addons_root)
    dest_addon_dir = os.path.join(dest_addons_root, rel_addon_dir)
    os.makedirs(dest_addon_dir, exist_ok=True)

    for entry in file_entries:
        if entry.lower().endswith(".toc"):
            print(f"    Skipping .toc file: {entry}")
            continue

        adjusted_entry = adjust_file_entry(entry, version, addon_name)
        src_file = os.path.join(addon_dir, entry)
        dest_file = os.path.join(dest_addon_dir, adjusted_entry)

        if os.path.exists(src_file):
            os.makedirs(os.path.dirname(dest_file), exist_ok=True)
            try:
                shutil.copy2(src_file, dest_file)
                print(f"    Copied: {src_file} -> {dest_file}")
                create_mixin(dest_file, dest_addons_root, branch, src_file)
            except Exception as e:
                print(f"    Error copying {src_file} to {dest_file}: {e}")
        else:
            print(f"    Source file {src_file} does not exist; skipping copy.")


def copy_annotations():
    """
    Copies all folders from './vscode-wow-api/Annotations/Core/*' to './API/*'.
    """
    src_annotations = os.path.join(".", "vscode-wow-api", "Annotations", "Core")
    dest_api = os.path.join(".", "API")
    if not os.path.isdir(src_annotations):
        print(f"Annotations source folder {src_annotations} not found.")
        return
    for item in os.listdir(src_annotations):
        src_item = os.path.join(src_annotations, item)
        dest_item = os.path.join(dest_api, item)
        if os.path.isdir(src_item):
            try:
                shutil.copytree(src_item, dest_item, dirs_exist_ok=True)
                print(f"Copied annotations folder: {src_item} -> {dest_item}")
            except Exception as e:
                print(
                    f"Error copying annotations folder {src_item} to {dest_item}: {e}"
                )


def load_xml(file_path):
    """
    Loads file paths from an XML file containing <Script> tags.

    The XML is expected to include tags like:
        <Script file="Blizzard_EventTrace.lua"/>

    Args:
        file_path (str): The path to the XML file, e.g.,
            ".generate_database_lua/Questie/Localization/Translations/Translations.xml"

    Returns:
        list: A list of the files referenced in the XML.
    """
    files_to_load = []

    # Only process if the file exists.
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            file_text = f.read()

        # Find all occurrences of <Script ... file="..." using a non-greedy regex.
        # This pattern matches the value inside the file attribute.
        matches = re.findall(r'<Script.*?file="(.*?)"', file_text)

        # Get the directory of the XML file to resolve relative paths
        xml_dir = os.path.dirname(file_path)

        for xml_file in matches:
            # Replace backslashes with forward slashes for consistency.
            xml_file = xml_file.replace("\\", "/")

            # Resolve the absolute path of the referenced file
            absolute_path = os.path.join(xml_dir, xml_file)
            normalized_path = os.path.normpath(absolute_path)

            # Convert back to relative path from the addon directory
            # We need to find the addon root (should be 3 levels up from Interface/AddOns/AddonName/)
            try:
                # Find the AddOns directory in the path
                path_parts = normalized_path.split(os.sep)
                addons_index = None
                for i, part in enumerate(path_parts):
                    if part == "AddOns":
                        addons_index = i
                        break

                if addons_index is not None and addons_index + 2 < len(path_parts):
                    # Extract just the relative path from the addon directory
                    addon_relative_path = os.path.join(*path_parts[addons_index + 2 :])
                    addon_relative_path = addon_relative_path.replace("\\", "/")
                    print("  Loading file:", addon_relative_path)
                    files_to_load.append(addon_relative_path)
                else:
                    # Fallback: use the original path if we can't parse it properly
                    print("  Loading file (fallback):", xml_file)
                    files_to_load.append(xml_file)
            except Exception as e:
                print(f"  Error processing XML file path {xml_file}: {e}")
                # Fallback: use the original path
                files_to_load.append(xml_file)

    return files_to_load


def get_git_commit_hash(repo_path):
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"Error getting commit hash for {repo_path}: {e}")
        return "Unknown"


def get_git_branch(repo_path):
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"Error getting branch for {repo_path}: {e}")
        return "Unknown"


def ensure_meta_tag(directory):
    print(f"\nEnsuring ---@meta tags in {directory}")
    for root, dirs, files in os.walk(directory):
        for file in files:
            if not file.lower().endswith(".lua"):
                continue

            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except Exception as e:
                print(f"Error reading {path}: {e}")
                continue

            # Check for existing meta tag in first 5 lines
            meta_index = -1
            for i in range(min(5, len(lines))):
                if lines[i].startswith("---@meta"):
                    meta_index = i
                    break

            modified = False

            if meta_index != -1:
                # Meta tag found
                if meta_index + 1 < len(lines):
                    if lines[meta_index + 1].strip():
                        lines.insert(meta_index + 1, "\n")
                        modified = True
                else:
                    # It is the last line.
                    if not lines[meta_index].endswith("\n"):
                        lines[meta_index] += "\n"
                    lines.append("\n")
                    modified = True
            else:
                # Meta tag not found
                lines.insert(0, "---@meta _\n")
                lines.insert(1, "\n")
                modified = True

            if modified:
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                except Exception as e:
                    print(f"Error writing {path}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Recreate a copy of the WoWUI folder structure containing only files "
        "referenced by the version-specific TOC files (excluding .toc files). "
        "You can supply one or more versions. If 'Classic' is chosen, 'Vanilla' is automatically added."
    )
    parser.add_argument("--version", required=True, help="Version suffix (e.g. Wrath)")
    args = parser.parse_args()
    version = args.version

    # Change internal cwd to the script's directory.
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Switch git branch based on version
    branch_mapping = {
        "classic": "vanilla",
        "vanilla": "vanilla",
        "tbc": "tbc",
        "wrath": "wrath",
        "cata": "cata",
        "mists": "mists",
    }
    target_branch = branch_mapping.get(version.lower(), version.lower())

    wowui_dir = os.path.join(".", "WoWUI")
    if os.path.isdir(os.path.join(wowui_dir, ".git")):
        print(f"Switching WoWUI repo to branch: {target_branch}")
        try:
            subprocess.run(
                ["git", "checkout", target_branch], cwd=wowui_dir, check=True
            )
            subprocess.run(["git", "pull"], cwd=wowui_dir, check=True)

            # Verify branch switch
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=wowui_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            current_branch = result.stdout.strip()
            if current_branch != target_branch:
                print(
                    f"Warning: Failed to switch branch. Expected '{target_branch}', but on '{current_branch}'"
                )
                return
            print(f"Successfully switched to branch: {current_branch}")
        except subprocess.CalledProcessError as e:
            print(f"Error switching branch: {e}")
            return

    versions = [version]

    # Normalize version names using a mapping.
    mapping = {
        "wrath": "Wrath",
        "tbc": "TBC",
        "cata": "Cata",
        "classic": "Classic",
        "vanilla": "Vanilla",
        "mists": "Mists",
    }
    versions = [mapping.get(v.lower(), v) for v in versions]

    # If 'Classic' is one of the versions and 'Vanilla' isn't explicitly specified, add it.
    if "Classic" in versions and "Vanilla" not in versions:
        versions.append("Vanilla")

    print(f"Processing versions: {', '.join(versions)}")  # type: ignore

    # Define the source AddOns folder.
    source_addons_root = os.path.join(".", "WoWUI", "Interface", "AddOns")
    if not os.path.isdir(source_addons_root):
        print(f"Source AddOns folder not found at {source_addons_root}")
        return

    # For each version, create a destination folder under API/<Version> and process each addon.
    for version in versions:
        dest_addons_root = os.path.join(".", "API", "_UI")
        print(
            f"\n=== Processing destination for version '{version}' at {dest_addons_root} ==="
        )
        for addon in os.listdir(source_addons_root):
            if addon in [
                "Blizzard_APIDocumentation",
                "Blizzard_APIDocumentationGenerated",
            ]:
                continue

            addon_dir = os.path.join(source_addons_root, addon)
            if os.path.isdir(addon_dir):
                process_addon_directory(
                    addon_dir,
                    version,
                    source_addons_root,
                    dest_addons_root,
                    target_branch,
                )

    # --- New post-processing steps ---
    print("\n--- Post-processing API folders ---")
    copy_annotations()

    # Rename the API folder to the version from args.version
    print(f"\nRenaming API folder to API-{args.version}")
    dest_api = os.path.join(".", "API")
    dest_version = os.path.join(".", f"API-{args.version}")

    if os.path.isdir(dest_version):
        print(f"Destination folder {dest_version} already exists. Removing directory.")
        shutil.rmtree(dest_version)

    os.rename(dest_api, dest_version)

    # Check if Functions-Classic-AI folder exists
    print("\nChecking if Functions-Classic-AI folder exists")
    dest_functions = os.path.join(".", "Functions-Classic-AI")
    if os.path.isdir(dest_functions):
        # Copy the folder into the API folder
        print("Copying Functions-Classic-AI folder into API folder")
        dest = os.path.join(dest_version, "Functions-AI")
        shutil.copytree(dest_functions, dest, dirs_exist_ok=True)

    # Copy ManualTypes folder
    print("\nCopying ManualTypes folder into API folder")
    src_manual_types = os.path.join(".", "ManualTypes")
    dest_manual_types = os.path.join(dest_version, "ManualTypes")
    if os.path.isdir(src_manual_types):
        shutil.copytree(src_manual_types, dest_manual_types, dirs_exist_ok=True)
        print(f"Copied ManualTypes folder: {src_manual_types} -> {dest_manual_types}")
    else:
        print(f"ManualTypes source folder {src_manual_types} not found.")

    # Create .vscode/settings.json in the output directory
    print("\nCreating .vscode/settings.json in output directory")
    vscode_dir = os.path.join(dest_version, ".vscode")
    os.makedirs(vscode_dir, exist_ok=True)

    settings_content = """{
  "Lua.diagnostics.disable": [
    // We don't care about undefined globals because the WoW API defines a lot of them.
    "undefined-global",
    // A lot of the code at blizzard has a ton of redundant parameters for some reason.
    "redundant-parameter",
    // Some languages support multiple assignment counts, but Lua does not. (e.g. local a, b = 1)
    "unbalanced-assignments",
    // Some functions say the don't support certain parameters, but they actually do. (GetAchievementCriteriaInfo vs GetAchievementCriteriaInfoByID)
    // So we disable this check.
    "missing-parameter",
    // Some of Blizzard's code uses lowercase globals, which is against Lua conventions.
    "lowercase-global",
    // Deprecated functions and features are common in the WoW API, so we disable this warning.
    "deprecated",
    // Due to the merge nature of this there are some duplication issues.
    "duplicate-doc-field",
    "duplicate-doc-alias",
    // Some string concatenations are done in a way that confuses the type checker.
    "ambiguity-1",
    // Not all type annotations are accurate in the WoW API, so we disable these type mismatch warnings.
    "return-type-mismatch",
    // Not all type annotations are accurate in the WoW API, so we disable these type mismatch warnings.
    "param-type-mismatch",
    // The Lua checker sometimes gets a number assignment but somewhere else it gets assigned nil.
    "assign-type-mismatch",
    // Because we add casts after the fact to satisfy the type checker, we disable this warning.
    "cast-local-type",
    // Classes do not like injecting fields but that requires refactoring which we can't do.
    "inject-field",
    // Not checking nil values is common in WoW API code.
    "need-check-nil",
    // Trailing spaces are not a big deal.
    "trailing-space",
  ]
}"""

    settings_path = os.path.join(vscode_dir, "settings.json")
    with open(settings_path, "w", encoding="utf-8") as f:
        f.write(settings_content)
    print(f"Created VS Code settings file: {settings_path}")

    # Generate COMMIT_HASHES.md
    print("\nGenerating COMMIT_HASHES.md")
    vscode_wow_api_hash = get_git_commit_hash(os.path.join(".", "vscode-wow-api"))
    vscode_wow_api_branch = get_git_branch(os.path.join(".", "vscode-wow-api"))
    wowui_hash = get_git_commit_hash(os.path.join(".", "WoWUI"))
    wowui_branch = get_git_branch(os.path.join(".", "WoWUI"))

    commit_hashes_content = f"""# Commit Hashes

This API documentation was generated using the following commit hashes:

- **vscode-wow-api**: `{vscode_wow_api_branch}` @ `{vscode_wow_api_hash}`
- **WoWUI**: `{wowui_branch}` @ `{wowui_hash}`

Generated on: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

    commit_hashes_path = os.path.join(dest_version, "COMMIT_HASHES.md")
    with open(commit_hashes_path, "w", encoding="utf-8") as f:
        f.write(commit_hashes_content)
    print(f"Created COMMIT_HASHES.md: {commit_hashes_path}")

    ensure_meta_tag(dest_version)


if __name__ == "__main__":
    main()
