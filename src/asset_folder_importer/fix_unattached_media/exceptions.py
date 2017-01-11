class PortalItemNotFound(StandardError):
    """
    Raised if the item does not exist within the Portal index
    """
    pass


class InvalidLocation(StandardError):
    pass


class NoCollectionFound(StandardError):
    """
    Raised if no collection could be found for the given asset folder
    """
    pass


class InvalidProjectError(StandardError):
    """
    Raised if the path given does not appear to identify a pluto asset folder
    """
    pass
