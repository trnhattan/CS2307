class ExamError(ValueError):
    pass


class ExamNotFoundError(ExamError):
    pass


class ExamStateError(ExamError):
    pass
