import httplib
import urllib
import logging
import base64
import json


class HTTPError(StandardError):
    def __init__(self, url, responseobject):
        self.response = responseobject
        self.url = url

class ProjectNotFound(StandardError):
    pass


class AssetFolderLocator(object):
    def __init__(self, scheme="http", host='localhost', port=80, user='admin', passwd=None, http_client=None,logger=None):
        self._scheme=scheme
        self._host=host
        self._port=port
        self._user=user
        self._passwd=passwd
        self._http = http_client if http_client is not None else httplib.HTTPConnection(self._host, self._port)
        self._logger=logger if logger is not None else logging.getLogger(__name__)
        
    def find_assetfolder(self, path):
        auth = base64.encodestring('%s:%s' % (self._user, self._passwd)).replace('\n', '')

        headers = {
            'Authorization': "Basic %s" % auth,
            'Accept': 'application/json',
        }
        
        url = "{s}://{h}:{p}/gnm_asset_folder/lookup?path={path}".format(
            s=self._scheme,
            h=self._host,
            p=self._port,
            path=urllib.quote(path,'')
        )
        self._logger.debug("retrieving info from {0}".format(url))
        
        self._http.request("GET",url,headers=headers)
        response = self._http.getresponse()
        
        self._logger.debug("server returned {0}".format(response.status))
        if response.status==404:
            raise ProjectNotFound(path)
        
        if response.status<200 or response.status>299:
            raise HTTPError(url, response)
        
        content = json.loads(response.read())
        
        self._logger.debug("json returned: {0}".format(content))
        if content['status'] == "ok":
            return content['project']
        else:
            raise ProjectNotFound(path)