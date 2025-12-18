# WoW UI Generator

This directory contains the tools necessary to generate the `API-<version>` folder, which provides Lua Language Server (LuaLS) annotations and source files for World of Warcraft UI development.

## Overview

The generator combines official Blizzard UI source code, community-maintained annotations, and manual type definitions into a single, structured workspace ready for IDE use. It handles version-specific logic (Classic, Vanilla, TBC, Wrath, etc.) and automatically injects Lua annotations into the Blizzard source code to improve intellisense for Mixins and Frames.

## Files

- **`clone.sh`**: A shell script to initialize the environment.
  - Cleans up old directories (`WoWUI`, `vscode-wow-api`).
  - Clones the full [BigWigsMods/WoWUI](https://github.com/BigWigsMods/WoWUI) repository (contains Blizzard's UI code).
  - Clones a sparse version of [Ketho/vscode-wow-api](https://github.com/Ketho/vscode-wow-api) (contains standard WoW API annotations).
- **`WoWUI-generator.py`**: The main Python script that processes the files and generates the output structure.
- **`inject_annotations.py`**: A dedicated script to inject LuaLS annotations from source definitions (e.g., FrameXML) into the generated implementation files.
- **`inject_mixin_skip.py`**: Configuration file defining regex patterns to skip specific annotations during injection.
- **`inject_replace.py`**: Configuration file defining regex replacement rules for functions and mixins during injection.
- **`ManualTypes/`**: A directory containing manually written Lua annotation files (e.g., for complex types or missing definitions) that are copied directly into the output.

## Usage

1. **Prepare Repositories:**
   Run the clone script to download the necessary source repositories.
   ```bash
   ./clone.sh
   ```

2. **Generate API Structure:**
   Run the main generator with a specific version.
   ```bash
   # Supported versions: classic, vanilla, tbc, wrath, cata, mists
   python3 WoWUI-generator.py --version wrath
   ```
   This creates the `API-wrath` (or corresponding version) folder.

3. **Inject Annotations:**
   Run the annotation injector to merge docs into the source code and clean up duplicates.
   ```bash
   # Run in dry-run mode first to see changes
   python3 inject_annotations.py --dry-run

   # Apply changes (removes source definitions by default)
   python3 inject_annotations.py
   ```

## How `WoWUI-generator.py` Works

The main script executes the following workflow to build the initial file structure:

1.  **Initialization & Version Setup**:
    - Switches the `WoWUI` git repository to the target branch (e.g., `wrath`, `cata`) ensuring correct source code for the requested version.

2.  **Addon Processing**:
    It iterates through all addons found in `WoWUI/Interface/AddOns`:
    - **TOC Selection**: Attempts to find the most relevant `.toc` file (`<Addon>_<Version>.toc` > `<Addon>_Classic.toc` > `<Addon>.toc`).
    - **File Parsing**: Reads the selected `.toc` file to build the file list.
        - **Variable Expansion**: Replaces `[Family]` with "Classic" and `[Game]` with the current version (e.g., "Wrath") in file paths.
        - **Conditional Loading**: Parses `[AllowLoadGameType ...]` directives. If the current version is not in the allowed list, the file is skipped. If allowed, the directive is stripped from the path.
    - **File Copying**: Copies referenced files to `API/_UI/<AddonName>/`.
        - Normalizes paths and handles case-sensitivity.
        - Attempts to "unfold" versioned folders (e.g., removing redundant `Classic/` folder prefixes).

3.  **Mixin Annotation Injection**:
    - As files are copied, it scans for `CreateFromMixins` patterns.
    - Injects basic `---@class Name : Parent` annotations directly into the file headers to support basic Intellisense.

## How `inject_annotations.py` Works

This script performs a multi-step post-processing pass on the generated API folder to merge rich documentation:

1.  **Parse Source Definitions:**
    - Scans the `FrameXML` folder (derived from `vscode-wow-api`).
    - Identifies all **Functions** (e.g., `function Table.Name()`) and **Mixins** (e.g., `MixinName = {}`).
    - Captures contiguous blocks of LuaLS annotations (`---@tag`) preceding them.

2.  **Inject into Target:**
    - Scans the generated `_UI` folder (Blizzard source code).
    - Matches functions and mixins by name.
    - **Smart Injection**:
        - Matches parameter names between documentation (`@param button`) and code (`function(self)`). Automatically renames doc parameters to match the code to prevent "undefined param" warnings.
        - Appends old parameter names as comments.
        - Respects indentation of the target code.
        - Supports cleaning prefixes like `--[[static]]`.
        - **Filtering/Skipping**:
            - Filters out `---@meta` and `---@class` tags during mixin injection.
            - Skips lines matching patterns defined in `inject_mixin_skip.py`.
        - **Replacements**:
            - Applies regex replacements defined in `inject_replace.py` to fix specific annotation issues on the fly.

3.  **Cleanup Source:**
    - If a function or mixin from the Source was successfully found in the Target, it is **removed from the Source file**.
    - **Multi-line Removal:** Safely removes entire multi-line function bodies (`function ... end`).
    - **Whitespace Cleanup:** Collapses excess blank lines left after removal.
    - **Empty File Cleanup:** Deletes source files that become empty (or contain only whitespace/meta tags) after the removal process.

This ensures that the final API folder contains the "real" Blizzard implementation code annotated with the rich community documentation, without duplicating definitions in separate meta files.
