import xml.sax as sax
import logging
import re


class PremiereSAXHandler(sax.ContentHandler):
    """
    A SAX handler class that stores media references from a premiere project XML
    """
    def startDocument(self):
        self.media_references = []
        self.render_files = []
        self.uuid = ""
        self.version = ""
        self.logger = logging.getLogger('PremiereSAXHandler')
        self.logger.setLevel(logging.WARNING)
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

    def endElement(self, name):
        #self.logger.debug("endElement for {0}".format(name))
        self.tag_tree.pop()
        if name == 'ActualMediaFilePath':
            self.media_references.append(self._buffer)
            self._buffer = ""
            self._in_media_ref = False

    def characters(self, content):
        if self._in_media_ref:
            #self.logger.debug(content)
            self._buffer += content

    def endDocument(self):
        is_preview = re.compile(r'\.PRV/')
        n=0
        for ref in self.media_references:
            if is_preview.search(ref):
                self.render_files.append(ref)
                del self.media_references[n]
            else:
                n+=1
