import http.client
from urllib.parse import quote, unquote
import logging
import re
import base64
import json
import time


class DirectPlutoLookup(object):
    """
    Calls out to the gnm_asset_folder plugin to see if the asset folder is known
    """
    def __init__(self, host="localhost", port=80, user="admin", password="", logger=None,
                 retry_delay=10,max_retries=100, conn=None):
        self._host = host
        self._port = int(port)
        self._user = user
        self._password = password
        self.logger = logging.getLogger("DirectPlutoLookup") if logger is None else logger
        self.logger.level = logging.DEBUG
        self._http = http.client.HTTPConnection(host,port) if conn is None else conn
        self._path_formatter = re.compile("/+$")
        self.retry_delay=retry_delay
        self.max_retries=max_retries
        
    def lookup(self, fullpath):
        checkpath = self._path_formatter.sub("", fullpath)
        request = "/gnm_asset_folder/lookup?path={0}".format(quote(checkpath,safe=''))
        self.logger.debug("Looking up URL " + request)

        authstring = u"{0}:{1}".format(self._user, self._password)
        auth = base64.b64encode(authstring.encode("UTF-8"))

        headers = {
            'Authorization': "Basic %s" % auth,
            'Accept': 'application/json'
        }
        
        attempts=0
        while True:
            self._http.request("GET",request,headers=headers)
            attempts+=1
            response = self._http.getresponse()
            data = response.read()  #need to do this in case anything else bails leaving us unable to re-use the connection
            self.logger.debug("response was {0}".format(response.status))
            self.logger.debug(data)
            
            if response.status == 200:
                data = json.loads(data)
                if data['status']=='ok':
                    return data['project']
                else:
                    self.logger.error(data)
                    return None
            elif response.status == 403:    #permission denied
                raise RuntimeError("Permission denied to Pluto using {0}:{1}".format(self._user,self._password))
            elif response.status == 404:    #not found
                return None
            elif response.status == 504:    #timeout
                self.logger.error("504 timeout error communicating with Pluto: {0}/{1}".format(attempts,self.max_retries))
                time.sleep(self.retry_delay)
                if attempts>=self.max_retries:
                    return None
            else:
                self.logger.error("Unexpected response {0} from Pluto. Data was: {1}".format(response.status, data))
                return None