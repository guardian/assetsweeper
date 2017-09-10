class NotFoundError(StandardError):
    pass


class XMLBuildError(StandardError):
    pass


class FileOnIgnoreList(StandardError):
    pass


class VSFileInconsistencyError(StandardError):
    """
    Raised if we get a 503 error from trying to create a file entity in Vidispine.
    """
    pass