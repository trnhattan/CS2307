class ExplanationError(RuntimeError):
    pass


class ExplanationNotFoundError(ExplanationError):
    pass


class ExplanationUnavailableError(ExplanationError):
    pass
