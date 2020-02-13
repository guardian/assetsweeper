class NotFoundError(Exception):
    pass


class XMLBuildError(Exception):
    pass


class FileOnIgnoreList(Exception):
    pass


class FileDoesNotExist(Exception):
    pass


class VSFileInconsistencyError(Exception):
    """
    Raised if we get a 503 error from trying to create a file entity in Vidispine.
    """
    pass
