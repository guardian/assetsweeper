class ProviderError(Exception):
    pass


class LookupError(ProviderError):
    pass


class BaseProvider(object):
    def __init__(self,*args,**kwargs):
        pass

    def lookup(self,filepath,filename,match_data):
        """
        Perform a lookup for the given filename and filepath.  The default implementation does nothing; over-ride this
        in your subclass to perform a lookup
        :param filepath: path to the file in question
        :param filename: name of the file in question
        :param match_data: the regex result object that matched the pattern calling. this means that you can get id numbers
        etc. extracted out of it; for example, if the pattern in footage_providers.yml is (?P<id>\d+)_MYPROVIDER then
        you can do match_data.group('id') to get the first part
        :return: A dictionary of metadata, an empty dictionary if the file is valid but there is no information to
        return, or None if this media is not relevant to this type of media
        """
        return None