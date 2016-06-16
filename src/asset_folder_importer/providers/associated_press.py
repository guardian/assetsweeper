from . import BaseProvider,LookupError


class Provider(BaseProvider):
    def lookup(self,filepath,filename,match_data):
        # return {'status': 'ok','message': 'it worked!', 'site_id': match_data.group('site_id'),
        #         'format': match_data.group('format')
        # }
        raise LookupError("AP ingest not yet implemented")