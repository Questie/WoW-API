# Configuration for matched strings to be skipped when injecting
MIXIN_SKIP_PATTERNS = {
    # For some reason Kethos code have all these fields but they automatically gets resolved.
    "PlayerLocationMixin": [
        r".*field unit.*",
        r".*field chatLineID.*",
        r".*field guid.*",
        r".*field SetGUID.*",
        r".*field IsValid.*",
        r".*field IsGUID.*",
        r".*field IsBattleNetGUID.*",
        r".*field GetGUID.*",
        r".*field SetUnit.*",
        r".*field IsUnit.*",
        r".*field GetUnit.*",
        r".*field SetChatLineID.*",
        r".*field IsChatLineID.*",
        r".*field GetChatLineID.*",
        r".*field SetBattlefieldScoreIndex.*",
        r".*field IsBattlefieldScoreIndex.*",
        r".*field GetBattlefieldScoreIndex.*",
        r".*field SetVoiceID.*",
        r".*field IsVoiceID.*",
        r".*field GetVoiceID.*",
        r".*field SetBattleNetID.*",
        r".*field IsBattleNetID.*",
        r".*field GetBattleNetID.*",
        r".*field SetCommunityData.*",
        r".*field IsCommunityData.*",
        r".*field SetCommunityInvitation.*",
        r".*field IsCommunityInvitation.*",
        r".*field Clear.*",
        r".*field ClearAndSetField.*",
    ]
}

# Configuration for matched strings to be skipped when injecting functions
FUNCTION_SKIP_PATTERNS = {
    # Example:
    # "SomeFunction": [
    #     r".*param self.*",
    # ]
}
