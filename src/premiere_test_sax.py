#!/usr/bin/python3
import xml.etree.ElementTree as ET
import xml.sax as sax
import sys
from pprint import pprint
import gzip
import logging
from asset_folder_importer.database import *
from asset_folder_importer.config import *
from asset_folder_importer.logginghandler import AssetImporterLoggingHandler
from optparse import OptionParser
from vidispine.vs_collection import VSCollection
from vidispine.vs_item import VSItem
from vidispine.vidispine_api import *
from vidispine.vs_storage import VSStoragePathMap, VSStorage
import time
import shutil
import tempfile
import re
import datetime


# Configurable parameters
LOGFORMAT = '%(asctime)-15s - %(name)s - %(levelname)s - %(message)s'
main_log_level = logging.DEBUG
#logfile = "/var/log/plutoscripts/premiere_get_referenced_media.log"
logfile = None

if logfile is not None:
    logging.basicConfig(filename=logfile, format=LOGFORMAT, level=main_log_level)
else:
    logging.basicConfig(format=LOGFORMAT, level=main_log_level)

#End configurable parameters

lg = logging.getLogger('PremiereProject')
global vs_pathmap
vs_pathmap = {}


class InvalidDataError(Exception):
    pass


class NoMediaError(Exception):
    pass


class PremiereSAXHandler(sax.ContentHandler):
    def startDocument(self):
        self.media_references = []
        self.render_files = []
        self.uuid = ""
        self.version = ""
        self.logger = logging.getLogger('PremiereSAXHandler')
        self.tag_tree = []
        self._buffer = ""
        self._in_media_ref = False
        pass

    def startElement(self, name, attrs):
        #self.logger.debug("startElement got {0} with {1}".format(name,attrs))
        self.tag_tree.append(name)
        try:
            if name == "PremiereData":
                try:
                    self.version = int(attrs['Version'])
                except ValueError:
                    self.version = attrs['Version']
            elif name == "RootProjectItem":
                try:
                    self.uuid = attrs['ObjectUID']
                except KeyError:
                    pass
            elif name == "ActualMediaFilePath":
                #pprint(self.tag_tree)
                if self.tag_tree[-2] == 'Media':
                    self._in_media_ref = True
        except KeyError:
            #pprint((name, attrs.__dict__))
            #print self.tag_tree[-1]
            pass
        pass

    def endElement(self, name):
        #self.logger.debug("endElement for {0}".format(name))
        self.tag_tree.pop()
        if name == 'ActualMediaFilePath':
            self.media_references.append(self._buffer)
            self._buffer = ""
            self._in_media_ref = False
        pass

    def characters(self, content):
        if self._in_media_ref:
            #self.logger.debug(content)
            self._buffer += content
        pass

    def endDocument(self):
        is_preview = re.compile(r'\.PRV/')
        n=0
        for ref in self.media_references:
            if is_preview.search(ref):
                self.render_files.append(ref)
                del self.media_references[n]
            else:
                n+=1


class PremiereProject:
    def __init__(self):
        self._parser = sax.make_parser()

        self.xmltree = None
        self.filename = None
        self.isCompressed = False
        self._sax_handler = PremiereSAXHandler()
        self._parser.setContentHandler(self._sax_handler)

    def load(self, filename, useTempFile=True):

        tf = None
        if useTempFile:
            lg.info("PremiereProject::load - requested to use temporary file")
            tf = tempfile.NamedTemporaryFile(suffix="prproj",delete=False)
            tempname = tf.name
            lg.info("PremiereProject::load - temporary file is %s" % tempname)
            shutil.copy2(filename,tempname)
            filename = tempname

        lg.debug("PremiereProject::load - loading %s" % filename)
        try:
            self.isCompressed = True
            f = gzip.open(filename, "rb")
            self._parser.parse(f)
            f.close()
        except IOError:  #if gzip doesn't want to read it, then try as a plain file...
            lg.debug("Open with gzip failed, trying standard file")
            self.isCompressed = False
            f = open(filename, "rb")
            self._parser.parse(f)
            f.close()
        if tf is not None:
            lg.debug("PremiereProject::load - removing temporary file %s" % tf.name)
            os.unlink(tf.name)

    def getParticulars(self):
        # rtn = {}

        # rootProjectItem = self.xmltree.find('RootProjectItem')
        # #pprint(rootProjectItem)
        # if rootProjectItem is None:
        #     raise ValueError("No RootProjectItem element in project")
        #
        # rtn['uuid'] = rootProjectItem.attrib['ObjectUID']
        # rtn['version'] = self.xmltree.attrib['Version']

        #return rtn
        return {'uuid': self._sax_handler.uuid, 'version': self._sax_handler.version}

    def getReferencedMedia(self, fullData=False):
        # count = 0
        # for mediaNode in self.xmltree.findall('Media'):
        #     if not fullData:
        #         n = mediaNode.find('ActualMediaFilePath')
        #         if n is not None:
        #             count += 1
        #             yield n.text
        #             #pprint(mediaNode)
        #             #print "Got media node: {fpath}".format(fpath=mediaNode.find('ActualMediaFilePath').text)
        # if count == 0:
        #     raise NoMediaError("Premiere project does not have any media file references")
        if len(self._sax_handler.media_references) == 0:
            raise NoMediaError("Premiere project does not have any media file references")
        return self._sax_handler.media_references


#START MAIN
from sys import argv

parser = sax.make_parser()
h = PremiereSAXHandler()
parser.setContentHandler(h)

logging.info("Opening {0}".format(argv[1]))
try:
    f = gzip.open(argv[1])
    parser.parse(f)
except IOError as e:
    f = open(argv[1],"r")
    parser.parse(f)

f.close()

pprint(h.__dict__)