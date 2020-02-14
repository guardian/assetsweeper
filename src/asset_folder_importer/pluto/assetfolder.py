import http.client
import urllib.request, urllib.parse, urllib.error
import logging
import base64
import json

logger = logging.getLogger(__name__)

class SweeperHTTPError(Exception):
    pass


class ProjectNotFound(Exception):
    pass


class AssetFolderLocator(object):
    def __init__(self, scheme="http", host='localhost', port=80, user='admin', passwd=None, http_client=None,logger=None):
        self._scheme=scheme
        self._host=host
        self._port=port
        self._user=user
        self._passwd=passwd
        self._http = http_client if http_client is not None else self.new_connection(scheme=scheme)
        self._logger=logger if logger is not None else logging.getLogger(__name__)

    def new_connection(self,scheme="http"):
        if scheme=="http":
            return http.client.HTTPConnection(self._host, self._port)
        else:
            return http.client.HTTPSConnection(self._host, self._port)

    def find_assetfolder(self, path):
        authstring = "{0}:{1}".format(self._user, self._passwd)
        auth = base64.b64encode(authstring.encode("UTF-8")).decode("UTF-8")

        headers = {
            'Authorization': "Basic %s" % auth,
            'Accept': 'application/json',
        }
        
        url = "{s}://{h}:{p}/gnm_asset_folder/lookup?path={path}".format(
            s=self._scheme,
            h=self._host,
            p=self._port,
            path=urllib.parse.quote(path,'')
        )
        self._logger.debug("retrieving info from {0}".format(url))
        self._http.connect()
        self._http.request("GET",url,headers=headers)
        response = self._http.getresponse()
        raw_content = response.read() #must always read or you get ResponseNotReady when re-using
        
        self._logger.debug("server returned {0}".format(response.status))
        if response.status==404:
            raise ProjectNotFound(path)
        
        if response.status<200 or response.status>299:
            logger.warning("Could not find asset folder: server returned {0} with body {1}".format(response.status, raw_content))
            raise SweeperHTTPError
        
        content = json.loads(raw_content)
        
        self._logger.debug("json returned: {0}".format(content))
        if content['status'] == "ok":
            return content['project']
        else:
            raise ProjectNotFound(path)