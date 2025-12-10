# Configuration for replacing matched annotation lines when injecting
# Key: Function Name or Mixin Name
# Value: List of (regex_pattern, replacement_string) tuples
FUNCTION_REPLACEMENT_PATTERNS = {
    # Spellbook functions with isPet parameter should have it as optional
    "IsSpellKnownOrOverridesKnown": [
        (r".*param\s*isPet\s*boolean", "---@param isPet boolean?"),
    ],
    "IsSpellKnown": [
        (r".*param\s*isPet\s*boolean", "---@param isPet boolean?"),
    ],
}


# Configuration for replacing matched annotation lines when injecting
# Key: Mixin Name or Mixin Name
# Value: List of (regex_pattern, replacement_string) tuples
MIXIN_REPLACEMENT_PATTERNS = {
    # "PlayerLocationMixin": [
    #     (r".*field\s*IsGUID", "---@field IsGUID boolean?"),
    # ],
}
