__author__ = 'Andy Gallagher <andy.gallagher@theguardian.com>'

import re
#from pprint import pprint

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
                #print "debug: got %s for %s" % (m.group(2), m.group(1))
                self.content[m.group(1)]=m.group(2)
        #pprint(self.content)

    def value(self,key,noraise=True):
        try:
            return self.content[key]
        except KeyError as e:
            print "error: No configuration key exists for %s" %key
            if noraise:
                return None
            raise e

    def setValue(self,key,value):
        self.content[key] = value
