import requests
import urllib.parse
import logging
import json

logger = logging.getLogger(__name__)


class HTTPError(Exception):
    def __init__(self, url, responseobject):
        self.response = responseobject
        self.url = url


class ProjectNotFound(Exception):
    pass


class AssetFolderLocator(object):
    def __init__(self, scheme="http", host='localhost', port=80, user='admin', passwd=None, logger=None):
        self._scheme=scheme
        self._host=host
        self._port=port
        self._user=user
        self._passwd=passwd
        self._logger=logger if logger is not None else logging.getLogger(__name__)
    #
    # def new_connection(self,scheme="http"):
    #     if scheme=="http":
    #         return httplib.HTTPConnection(self._host, self._port)
    #     else:
    #         return httplib.HTTPSConnection(self._host, self._port)

    def find_assetfolder(self, path):
        headers = {
            'Accept': 'application/json',
        }
        
        url = "{s}://{h}:{p}/gnm_asset_folder/lookup?path={path}".format(
            s=self._scheme,
            h=self._host,
            p=self._port,
            path=urllib.parse.quote(path,'')
        )
        self._logger.debug("retrieving info from {0}".format(url))

        response = requests.get(url,headers=headers,auth=(self._user, self._passwd))
        raw_content = response.text
        
        self._logger.debug("server returned {0}".format(response.status_code))
        if response.status_code==404:
            raise ProjectNotFound(path)
        
        if response.status_code<200 or response.status_code>299:
            logger.warning(u"Could not find asset folder: server returned {0} with body {1}".format(response.status_code, response.text))
            raise HTTPError(url, response)
        
        content = json.loads(raw_content)
        
        self._logger.debug("json returned: {0}".format(content))
        if content['status'] == "ok":
            return content['project']
        else:
            raise ProjectNotFound(path)