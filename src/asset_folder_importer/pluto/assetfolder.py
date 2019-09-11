import requests
import urllib
import logging
import base64


logger = logging.getLogger(__name__)

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

        response = requests.get(url,headers=headers)
        
        self._logger.debug("server returned {0}".format(response.status_code))
        if response.status_code==404:
            raise ProjectNotFound(path)
        
        if response.status_code<200 or response.status_code>299:
            logger.warning(u"Could not find asset folder: server returned {0} with body {1}".format(response.status_code, response.text))
            raise HTTPError(url, response)
        
        content = response.json()
        
        self._logger.debug("json returned: {0}".format(content))
        if content['status'] == "ok":
            return content['project']
        else:
            raise ProjectNotFound(path)