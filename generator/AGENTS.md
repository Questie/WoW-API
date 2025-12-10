# Agent Handover: WoW API Generator

This document serves as a context dump for AI agents working on the WoW API Generator project. It outlines the architecture, design decisions, and specific behaviors of the tooling.

## Project Purpose
To create a high-quality Lua Language Server (LuaLS) workspace for World of Warcraft UI addon development.
We combine:
1.  **Blizzard's Actual Source Code**: (sourced from `BigWigsMods/WoWUI`) - Provides the *implementation* and truth.
2.  **Community Annotations**: (sourced from `Ketho/vscode-wow-api`) - Provides the *types* and documentation (`---@param`, `---@return`).

The goal is to merge these into a single "API" folder where the real code is annotated with the docs, eliminating "duplicate definition" errors while maximizing Intellisense.

## Directory Structure & Terminology

### Root Layout
- `generator/`: Contains all tooling scripts.
- `generator/API-<version>/`: The output folder (e.g., `API-Vanilla`, `API-Wrath`).

### Key Concepts for `inject_annotations.py`

*   **"Source" (Definitions)**:
    *   **Path**: `API-<version>/FrameXML` (and subfolders).
    *   **Origin**: Copied from `vscode-wow-api`.
    *   **Content**: `.lua` files containing `---@class`, `---@param` tags, usually describing global functions or Mixins. The function bodies are often empty stubs (`function Foo() end`).
    *   **Role**: The *donor* of documentation.

*   **"Target" (Implementation)**:
    *   **Path**: `API-<version>/_UI` (and subfolders).
    *   **Origin**: Extracted from `WoWUI/Interface`.
    *   **Content**: Real `.lua` files (`Blizzard_ActionBar`, `Blizzard_UnitFrame`, etc.). Function signatures often use `self` instead of explicit names.
    *   **Role**: The *recipient* of documentation. This is the code we want to preserve.

## Core Workflows

### 1. Generation (`WoWUI-generator.py`)
This script initializes the workspace. It parses `.toc` files to understand which Blizzard source files belong to the current version and copies them into the `_UI` structure.

### 2. Injection & Cleanup (`inject_annotations.py`)
This script performs post-processing to merge the documentation.

**Design Philosophy: "Inject then Delete"**
We chose to inject annotations into the Target (Implementation) and then **delete the matching definitions from the Source**.
*   *Why?* If we keep `FrameXML/Foo.lua` (stub) and `_UI/Foo.lua` (implementation), LuaLS reports "Duplicate Definition". Removing the stub forces the IDE to rely on the single, now-annotated implementation file.

**Key Logic:**

1.  **Parsing**: Scans "Source" for contiguous annotation blocks preceding `function` definitions or `Mixin = {}` tables.
2.  **Function Injection**:
    *   Finds the matching function in "Target".
    *   **Smart Parameter Matching**:
        *   *Problem*: Source doc has `@param button`, Target code has `function(self)`.
        *   *Solution*: The script compares param counts. If they match but names differ, it rewrites the annotation to `@param self` and appends `-- button` as a comment. This solves "undefined param" diagnostics.
    *   **Prefix Cleaning**: Handles and strips Blizzard-specific prefixes like `--[[static]]` to ensure clean Lua syntax.
3.  **Mixin Injection**:
    *   Finds matching Global Tables / Mixins.
    *   **Filtering**: Explicitly strips `---@meta` and `---@class` tags during injection. We assume class definitions are handled by `ManualTypes` or global generation; we only want the field/method docs injected.
    *   **Skip Patterns**: Checks `inject_mixin_skip.py` to skip specific lines (e.g., fields that collide with implementation details).
4.  **Source Cleanup**:
    *   If a function/mixin is successfully matched in Target, it is removed from Source.
    *   **Multi-line Removal**: The script is smart enough to remove `function ... end` blocks, not just single lines.
    *   **Whitespace**: It collapses multiple blank lines left behind by deletions.
    *   **Empty Files**: If a Source file is left with only whitespace or `---@meta` tags, the file is deleted entirely.

## Configuration

*   **`inject_mixin_skip.py`**:
    *   Contains `MIXIN_SKIP_PATTERNS`: Regex patterns to exclude specific lines when injecting into Mixins.
    *   Contains `FUNCTION_SKIP_PATTERNS`: Regex patterns to exclude specific lines when injecting into Functions.

## Future Agent Instructions

If you need to modify this process:
1.  **New Skip Rules**: Add regexes to `inject_mixin_skip.py`. Do not hardcode them in the main script.
2.  **Debugging Injection**: Use the `--dry-run` flag. It provides detailed output including "Param mismatch fixing" and "Stripping prefix" events.
    ```bash
    python3 inject_annotations.py --dry-run
    ```
3.  **Parsing Edge Cases**: If Blizzard adds new prefixes (e.g., `--[[private]]`), update the `prefix_regex` in `inject_annotations.py`.
