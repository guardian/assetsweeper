from urllib.parse import quote,unquote
import logging
import re
import base64
import json
import time
import requests

class DirectPlutoLookup(object):
    """
    Calls out to the gnm_asset_folder plugin to see if the asset folder is known
    """
    def __init__(self, host="localhost", port=80, user="admin", password="", logger=None,
                 retry_delay=10,max_retries=100):
        self._host = host
        self._port = int(port)
        self._user = user
        self._password = password
        self.logger = logging.getLogger("DirectPlutoLookup") if logger is None else logger
        self.logger.level = logging.DEBUG
        self._path_formatter = re.compile("/+$")
        self.retry_delay=retry_delay
        self.max_retries=max_retries
        
    def lookup(self, fullpath):
        checkpath = self._path_formatter.sub("", fullpath)
        request = "/gnm_asset_folder/lookup?path={0}".format(quote(checkpath,safe=''))
        self.logger.debug("Looking up URL " + request)
        
        headers = {
            'Accept': 'application/json'
        }
        
        attempts=0
        while True:
            response = requests.get(request,headers=headers, auth=(self._user, self._password))
            attempts+=1
            data = response.text
            
            if response.status_code == 200:
                data = json.loads(data)
                if data['status']=='ok':
                    return data['project']
                else:
                    self.logger.error(data)
                    return None
            elif response.status_code == 403:    #permission denied
                raise RuntimeError("Permission denied to Pluto using {0}:{1}".format(self._user,self._password))
            elif response.status_code == 404:    #not found
                return None
            elif response.status_code == 504:    #timeout
                self.logger.error("504 timeout error communicating with Pluto: {0}/{1}".format(attempts,self.max_retries))
                time.sleep(self.retry_delay)
                if attempts>=self.max_retries:
                    return None
            else:
                self.logger.error("Unexpected response {0} from Pluto. Data was: {1}".format(response.status_code, data))
                return None