#!/usr/bin/env python3
import os
import argparse
import shutil
import re
import subprocess


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


def create_mixin(file, dest_root, branch):
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
            "regex": r"^(\w+) *= *CreateFromMixins\(([^)]+)\);",
            "action": "template",
            "output_string": "---@class {0} : {1}",
            "group_index": [1, 2],  # LHS, RHS
        },
        {
            "regex": r"^(\w+) = (\w+):CreateSubPin\(",
            "action": "template",
            "output_string": "---@class {0} : {1}",
            "group_index": [1, 2],  # [child_class, parent_class]
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
            f.write("<!-- Auto-moved, do not edit manually -->\n")
        else:
            f.write("-- Auto-generated LuaLS Annotations, do not edit manually\n")
            f.write("---@meta _\n")

        for line in lines:
            # Remove strange BOM character if present
            line = line.replace("\ufeff", "")
            if is_xml:
                url = f"https://raw.githubusercontent.com/BigWigsMods/WoWUI/refs/heads/{branch}/Interface/AddOns/Blizzard_SharedXML/UI.xsd"
                line = line.replace(r"..\Blizzard_SharedXML\UI.xsd", url)
                line = line.replace(r"../Blizzard_SharedXML/UI.xsd", url)

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
    For a given addon folder, select the appropriate base and version-specific TOC files,
    then:
      - Parse the base TOC to obtain allowed file entries.
      - Read the version-specific TOC, filtering out any file entry not in the allowed set.
      - Recreate the addon's folder under dest_addons_root.
      - Copy all files referenced (with relative paths preserved), except any .toc files.

    The function looks for a TOC file ending with _{version}.toc.
    It also attempts to pick a genuine base TOC (one that does not look version-specific)
    to use for allowed entries. If no such base exists but the version TOC exists, the
    version TOC is used for both roles.
    """
    # List all .toc files in the addon folder.
    toc_files: list[str] = [
        f for f in os.listdir(addon_dir) if f.lower().endswith(".toc")
    ]
    if not toc_files:
        return

    base_toc = None
    version_toc = None
    # Define known version tags (if a TOC file ends with _<tag>.toc, it is considered version-specific).
    known_tags = {"Cata", "TBC", "Vanilla", "Wrath", "Classic", "Mists"}

    for toc in toc_files:
        # If the file name ends with _{version}.toc, mark it as the version-specific TOC.
        if toc.endswith(f"_{version}.toc"):
            version_toc = toc
            continue

        # Otherwise, if the file appears version-specific (its name contains an underscore with a known tag)
        if "_" in toc:
            parts = toc.rsplit("_", 1)
            if len(parts) == 2:
                tag = parts[1].rsplit(".", 1)[0]
                if tag in known_tags:
                    # This TOC file is marked for some version; skip it as a base.
                    continue
                else:
                    base_toc = toc
            else:
                base_toc = toc
        else:
            # If there is no underscore, use it as a base.
            base_toc = toc

    # If no genuine base TOC was found but a version-specific TOC exists,
    # use the version-specific TOC as the base.
    if base_toc is None and version_toc is not None:
        base_toc = version_toc

    # No TOC files found; skip this addon.
    if version_toc is None and base_toc is None:
        print(
            f"Version TOC file for version '{version}' not found in {addon_dir}. Skipping this addon."
        )
        return

    # If only the base toc exists, we use it for all versions.
    if version_toc is None:
        version_toc = base_toc

    base_toc_path = os.path.join(addon_dir, base_toc)  # type: ignore
    version_toc_path = os.path.join(addon_dir, version_toc)  # type: ignore

    print(f"\nProcessing addon in folder: {addon_dir}")
    print(f"  Base TOC: {base_toc}")
    print(f"  Version TOC: {version_toc}")

    allowed_entries = parse_toc_file(base_toc_path)
    if not allowed_entries:
        print(
            f"  No allowed file entries found in base TOC {base_toc_path}. Skipping this addon."
        )
        return

    # Process the version-specific TOC file: filter out file entries not in the allowed set.
    # (We still use its contents to determine what files to copy.)
    filtered_lines = []
    file_entries = []  # normalized file paths that will be copied
    try:
        with open(version_toc_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("##"):
                filtered_lines.append(line)
            else:
                normalized = os.path.normpath(stripped.replace("\\", os.sep))
                if normalized in allowed_entries:
                    filtered_lines.append(line)
                    file_entries.append(normalized)
                    if normalized.lower().endswith(".xml"):
                        # If the file is an XML file, load its contents and add the referenced files.
                        xml_files = load_xml(os.path.join(addon_dir, normalized))
                        for xml_file in xml_files:
                            if xml_file not in allowed_entries:
                                print(f"    Adding XML file: {xml_file}")
                                file_entries.append(xml_file)
                else:
                    print(
                        f"  Skipping file entry '{stripped}' in {version_toc_path} (not found in base TOC)."
                    )
    except Exception as e:
        print(f"Error processing {version_toc_path}: {e}")
        return

    # Determine the addon folder's relative path (relative to the source addons root)
    rel_addon_dir = os.path.relpath(addon_dir, source_addons_root)
    dest_addon_dir = os.path.join(dest_addons_root, rel_addon_dir)
    os.makedirs(dest_addon_dir, exist_ok=True)

    # Do not write out the .toc file; we only copy non-.toc files referenced in the filtered TOC.
    # When copying, adjust the destination path if an extra version folder is detected.
    addon_name = os.path.basename(addon_dir)
    for entry in file_entries:
        if entry.lower().endswith(".toc"):
            print(f"    Skipping .toc file: {entry}")
            continue
        # Adjust the entry if it contains an extra version folder.
        adjusted_entry = adjust_file_entry(entry, version, addon_name)
        src_file = os.path.join(addon_dir, entry)
        dest_file = os.path.join(dest_addon_dir, adjusted_entry)
        if os.path.exists(src_file):
            os.makedirs(os.path.dirname(dest_file), exist_ok=True)
            try:
                shutil.copy2(src_file, dest_file)
                print(f"    Copied: {src_file} -> {dest_file}")
                create_mixin(dest_file, dest_addons_root, branch)
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

    # Create .vscode/settings.json in the output directory
    print("\nCreating .vscode/settings.json in output directory")
    vscode_dir = os.path.join(dest_version, ".vscode")
    os.makedirs(vscode_dir, exist_ok=True)

    settings_content = """{
  "Lua.diagnostics.disable": [
    "undefined-global",
    "redundant-parameter",
    "unbalanced-assignments",
    "missing-parameter",
    "lowercase-global",
    "ambiguity-1",
    "deprecated",
    "duplicate-doc-field",
    "duplicate-doc-alias",
    "return-type-mismatch",
  ]
}"""

    settings_path = os.path.join(vscode_dir, "settings.json")
    with open(settings_path, "w", encoding="utf-8") as f:
        f.write(settings_content)
    print(f"Created VS Code settings file: {settings_path}")


if __name__ == "__main__":
    main()
