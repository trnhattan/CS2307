class AdminError(ValueError):
    pass


class AccountConflictError(AdminError):
    pass


class AccountNotFoundError(AdminError):
    pass
