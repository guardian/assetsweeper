class PortalItemNotFound(Exception):
    """
    Raised if the item does not exist within the Portal index
    """
    pass


class InvalidLocation(Exception):
    pass


class NoCollectionFound(Exception):
    """
    Raised if no collection could be found for the given asset folder
    """
    pass


class InvalidProjectError(Exception):
    """
    Raised if the path given does not appear to identify a pluto asset folder
    """
    pass
