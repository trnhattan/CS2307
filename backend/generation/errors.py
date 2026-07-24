class GenerationError(RuntimeError):
    pass


class GenerationCatalogError(GenerationError):
    pass


class GenerationUnavailableError(GenerationError):
    pass
