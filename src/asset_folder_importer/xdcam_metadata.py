__author__ = 'Andy Gallagher <andy.gallagher@theguardian.com>'
__version__ = '$Rev$ $LastChangedDate$'

import xml.etree.ElementTree as ET
import os
import datetime
import logging

logger = logging.getLogger(__name__)

class PathNotFoundError(Exception):
    pass

class InvalidDataError(Exception):
    pass

class XDCAMImporter:
    def __init__(self,filepath):
        self.references = {}
        self.streams = []
        self.loadedSMI=False

        self.ubit=""
        self.videoRecPort=""
        self.videoCodec=""
        self.videoCaptureFPS=""
        self.videoFormatFPS=""
        self.videoWidth=-1
        self.videoHeight=-1
        self.videoAspect=""
        self.packageName=""
        self.packageType=""

        if not os.path.exists(filepath):
            raise PathNotFoundError("The path %s does not exist" % filepath)

        if os.path.isdir(filepath):
            self.clipRoot=filepath
        else:
            self.clipRoot=os.path.dirname(filepath)

        self.load()

    def mediaFiles(self):
        for ref in self.streams:
            if 'source' in ref:
                mediapath=ref['source']
                if not os.path.isabs(mediapath):
                    mediapath=os.path.join(self.clipRoot,mediapath)
                yield mediapath

    def load(self,specificFile=None):
        if specificFile:
            if specificFile.upper().endswith(".XML"):
                self.references['NonRealTimeMeta']=specificFile
                self._loadReferences()
                return

        #Step one: find the SMI file
        for file in os.listdir(self.clipRoot):
            #print "found file %s" % file
            if file.upper().endswith(".SMI"):
                #try:
                self._loadSMI(file)
                #except Exception as e:
                #    raise InvalidDataError(e.message)
                #step two: load any external references found in the SMI file (should be XML and PPN)
                self._loadReferences()
        #PMW-200 does not have SMI files, so this is not an error
        #if not self.loadedSMI:
        #    raise InvalidDataError("Unable to find SMI file in %s" % self.clipRoot)

    def _loadSMI(self,filepath):

        xmldoc = ET.parse(os.path.join(self.clipRoot,filepath))

        ns="{urn:schemas-professionalDisc:edl:ver.1.30:clipInfo}"
        rootEl=xmldoc.getroot()

        refsNodes=rootEl.findall("./{0}head/{0}metadata/{0}ref".format(ns))

        if refsNodes is None:
            raise InvalidDataError("No nodes found in SMI at /head/metadata/ref")

        for n in refsNodes:
            refName=n.attrib['type']
            refLink=n.attrib['src']
            self.references[refName] = refLink

        streamNodes=rootEl.findall("./{0}body/{0}par/*".format(ns))

        if streamNodes is None:
            raise InvalidDataError("No nodes found in SMI at /body/par")

        for n in streamNodes:
            streamDict = {}

            streamDict['type']=n.tag
            #pprint(n)
            streamDict['source']=n.attrib['src']
            streamDict['format']=n.attrib['type']
            streamDict['clipBegin']=n.attrib['clipBegin']
            streamDict['clipEnd']=n.attrib['clipEnd']
            try:
                streamDict['trackDst']=n.attrib['trackDst']
            except Exception:
                pass
            self.streams.append(streamDict)
        self.loadedSMI=True

    def _loadReferences(self):
        for k,v in self.references.items():
            #print "got reference %s at %s" % (k,v)
            if k=="NonRealTimeMeta":
                self._loadSonyNRTMeta(v)

    def _loadSonyNRTMeta(self,filename):
        if not os.path.exists(filename):
            filename=os.path.join(self.clipRoot,filename)

        if not os.path.exists(filename):
            raise PathNotFoundError("No XML metadata file can be found at %s",filename)

        #print "Loading NRT metadata from %s" % filename
        ns="{urn:schemas-professionalDisc:nonRealTimeMeta:ver.1.30}"
        xmldoc = ET.parse(filename)

        rootEl=xmldoc.getroot()

        #pprint(rootEl)
        durationEl=rootEl.find('./{0}Duration'.format(ns))
        if durationEl is None: #try for alternate schema
            ns="{urn:schemas-professionalDisc:nonRealTimeMeta:ver.1.40}"
            durationEl=rootEl.find('./{0}Duration'.format(ns))

        #pprint(durationEl)
        self.duration=None
        if durationEl is not None:
            self.duration = int(durationEl.attrib['value'])

        creationEl=rootEl.find('{0}CreationDate'.format(ns))
        self.created=None
        if creationEl is not None:
            self.created = datetime.datetime.strptime(creationEl.attrib['value'],"%Y-%m-%dT%H:%M:%SZ")

        ubitEl=rootEl.find('{0}TypicalUbit'.format(ns))
        self.ubit=""
        if ubitEl is not None:
            self.ubit = ubitEl.attrib['value']

        self.videoRecPort=""
        self.videoCodec=""
        self.videoCaptureFPS=""
        self.videoFormatFPS=""
        self.videoWidth=-1
        self.videoHeight=-1
        self.videoAspect=""

        portEl=rootEl.find('./{0}VideoFormat/{0}VideoRecPort'.format(ns))
        if portEl is not None:
            self.videoRecPort=portEl.attrib['port']

        videoFrameEl=rootEl.find('./{0}VideoFormat/{0}VideoFrame'.format(ns))
        if videoFrameEl is not None:
            self.videoCodec=videoFrameEl.attrib['videoCodec']
            self.videoCaptureFPS=videoFrameEl.attrib['captureFps']
            self.videoFormatFPS=videoFrameEl.attrib['formatFps']

        videoLayoutEl=rootEl.find('./{0}VideoFormat/{0}VideoLayout'.format(ns))
        if videoLayoutEl is not None:
            self.videoWidth=int(videoLayoutEl.attrib['pixel'])
            self.videoHeight=int(videoLayoutEl.attrib['numOfVerticalLine'])
            self.videoAspect=videoLayoutEl.attrib['aspectRatio']

        self.audioChannelCount=0
        self.audioChannels=[]

        audioFormatEl=rootEl.find('{0}AudioFormat'.format(ns))
        if audioFormatEl is not None:
            self.audioChannelCount=audioFormatEl.attrib['numOfChannel']
            for n in audioFormatEl:
                if n.tag == "{0}AudioRecPort".format(ns):
                    audioChannelInfo={'port': n.attrib['port'],
                                      'codec': n.attrib['audioCodec'],
                                      'dest': n.attrib['trackDst'] }
                    self.audioChannels.append(audioChannelInfo)

        self.deviceManufacturer=""
        self.deviceModel=""
        self.deviceSerialNo=""

        deviceEl=rootEl.find('./{0}Device'.format(ns))
        #pprint(deviceEl.__dict__)
        if deviceEl is not None:
            self.deviceManufacturer = deviceEl.attrib['manufacturer']
            self.deviceModel = deviceEl.attrib['modelName']
            self.deviceSerialNo = deviceEl.attrib['serialNo']

        self.lensName=""

        lensEl=rootEl.find('{0}Lens'.format(ns))
        if lensEl is not None:
            self.lensName = lensEl.attrib['modelName']

        self.recordingMode=""
        self.cacheRecord=False

        recModeEl=rootEl.find('{0}RecordingMode'.format(ns))
        if recModeEl is not None:
            self.recordingMode=recModeEl.attrib['type']
            if recModeEl.attrib['cacheRec']!="false":
                self.cacheRecord = True

        packageEl=rootEl.find('{0}AcquisitionRecord/{0}Package'.format(ns))
        if packageEl is not None:
            try:
                self.packageName=packageEl.attrib['name']
                self.packageType=packageEl.attrib['type']
            except KeyError as e:
                logger.warning(e)

