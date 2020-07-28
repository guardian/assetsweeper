__author__ = 'Andy Gallagher <andy.gallagher@theguardian.com>'

import re
import logging

logger = logging.getLogger(__name__)

class configfile:
    def __init__(self,configpath):
        self.content={}

        f = open(configpath)

        splitter=re.compile(u'^\s*([^=]+)\s*=\s*(.*)\s*$')

        for line in f:
            if line.startswith('#'):
                continue

            m=splitter.match(line)
            if m:
                self.content[m.group(1)]=m.group(2)
    def value(self,key,default=None,noraise=True):
        try:
            return self.content[key]
        except KeyError as e:
            if default is None:
                logger.error("No configuration key exists for %s" %key)
                if noraise:
                    return None
                raise e
            else:
                return default

    def setValue(self,key,value):
        self.content[key] = value
