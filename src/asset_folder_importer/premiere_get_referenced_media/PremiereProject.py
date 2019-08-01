import xml.sax as sax
from xml.sax import SAXParseException
import logging
import shutil
import tempfile
import gzip
from PremiereSAXHandler import PremiereSAXHandler
from Exceptions import InvalidDataError, NoMediaError
import os

lg = logging.getLogger(__name__)


class PremiereProject(object):
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
            lg.debug("PremiereProject::load - requested to use temporary file")
            tf = tempfile.NamedTemporaryFile(suffix="prproj",delete=False)
            tempname = tf.name
            lg.debug("PremiereProject::load - temporary file is %s" % tempname)
            shutil.copy2(filename,tempname)
            filename = tempname

        lg.debug("PremiereProject::load - loading %s" % filename)
        try:
            self.isCompressed = True
            f = gzip.open(filename, "rb")
            self._parser.parse(f)
            f.close()
        except IOError:  #if gzip doesn't want to read it, then try as a plain file...
            lg.warning("Open with gzip failed, trying standard file")
            self.isCompressed = False
            f = open(filename, "rb")
            try:
                self._parser.parse(f)
            except SAXParseException:
                lg.warning("Attempt at parsing XML for {0} failed.".format(filename))
                if tf is not None:
                    lg.debug("PremiereProject::load - removing temporary file %s" % tf.name)
                    os.unlink(tf.name)
            f.close()
        except SAXParseException:
            lg.warning("Attempt at parsing XML for {0} failed.".format(filename))
            f.close()
            if tf is not None:
                lg.debug("PremiereProject::load - removing temporary file %s" % tf.name)
                os.unlink(tf.name)
        if tf is not None:
            lg.debug("PremiereProject::load - removing temporary file %s" % tf.name)
            os.unlink(tf.name)

    def getParticulars(self):
        if self._sax_handler.uuid == "" or self._sax_handler.version == "":

            raise InvalidDataError("no uuid or version in premiere project")
        return {'uuid': self._sax_handler.uuid, 'version': self._sax_handler.version}

    def getReferencedMedia(self, fullData=False):
        if len(self._sax_handler.media_references) == 0:
            raise NoMediaError("Premiere project does not have any media file references")
        return self._sax_handler.media_references

