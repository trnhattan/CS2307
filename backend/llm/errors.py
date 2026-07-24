class LLMError(RuntimeError):
    pass


class LLMConfigurationError(LLMError):
    pass


class LLMProviderError(LLMError):
    pass


class LLMResponseError(LLMError):
    pass
