class AdminError(ValueError):
    pass


class AccountConflictError(AdminError):
    pass


class AccountNotFoundError(AdminError):
    pass


class QuestionNotFoundError(AdminError):
    pass


class QuestionValidationError(AdminError):
    pass
