# Standard model identifiers
CLAUDE = "anthropic/claude-3-5-sonnet-20240620"
GPT_4O_MINI = "gpt-4o-mini"  # Default model
GPT_4O = "openai/gpt-4o"
GPT_O1 = "openai/gpt-o1"

# LM Studio model identifiers
LMSTUDIO_QWEN = "lmstudio/qwen2.5-7b-instruct-1m"
LMSTUDIO_DEEPSEEK = "lmstudio/deepseek-r1-distill-qwen-7B"

# Default model (used when no model is specified)
DEFAULT_MODEL = GPT_4O_MINI

# Model families
ANTHROPIC_MODELS = {
    "claude-3-5-sonnet": CLAUDE,
}

OPENAI_MODELS = {
    "gpt-4o-mini": GPT_4O_MINI,
    "gpt-4o": GPT_4O,
    "gpt-o1": GPT_O1,
}

LMSTUDIO_MODELS = {
    "qwen2.5": LMSTUDIO_QWEN,
    "deepseek-r1": LMSTUDIO_DEEPSEEK,
}

# Common model categories for reference
CHAT_MODELS = {
    **ANTHROPIC_MODELS,
    **OPENAI_MODELS,
    **LMSTUDIO_MODELS,
}
