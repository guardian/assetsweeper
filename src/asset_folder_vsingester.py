#!/usr/bin/python

__author__ = 'Andy Gallagher <andy.gallagher@theguardian.com>'
__version__ = 'asset_folder_vsingester $Rev: 273 $ $LastChangedDate: 2015-07-28 22:00:39 +0100 (Tue, 28 Jul 2015) $'
__scriptname__ = 'asset_folder_vsingester'

#this also requires python-setuptools to be installed
from jinja2 import Environment,PackageLoader
from gnmvidispine.vs_collection import VSCollection
from gnmvidispine.vs_job import VSJob,VSJobFailed
from gnmvidispine.vs_storage import VSStorage
from gnmvidispine.vidispine_api import VSBadRequest,VSNotFound, VSException, HTTPError, VSConflict
from gnmvidispine.vs_metadata import VSMetadata
from asset_folder_importer.database import importer_db
from asset_folder_importer.config import configfile
from asset_folder_importer.xdcam_metadata import XDCAMImporter,InvalidDataError
from pprint import pprint
from optparse import OptionParser
from time import sleep
from glob import glob
import traceback
import os
import re
import time
import logging
import threading
from Queue import Queue, Empty
from copy import deepcopy
import asset_folder_importer.externalprovider as externalprovider
from subprocess import Popen,PIPE

MAXTHREADS = 4
#suid perl script so we don't need to run the whole shebang as root
PERMISSIONSCRIPT = "/usr/local/scripts/asset_folder_importer/asset_permissions.pl"
#set default encoding to utf-8 to prevent template errors
XML_CHECK_TIMEOUT = 60  #wait up to 60s for XML validation
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

# Configurable parameters
LOGFORMAT = '%(asctime)-15s - %(levelname)s - Thread %(thread)s - %(funcName)s: %(message)s'
main_log_level = logging.DEBUG
logfile = "/var/log/plutoscripts/asset_folder_vsingester.log"
graveyard_folder = "/var/log/plutoscripts/asset_folder_ingester_failed_xml"
#End configurable parameters

potentialSidecarExtensions = ['.xml','.xmp','.meta','.XML','.XMP']
class NotFoundError(StandardError):
    pass


class XMLBuildError(StandardError):
    pass


class FileOnIgnoreList(StandardError):
    pass


class ImporterThread(threading.Thread):
    def __init__(self,q,storageid,cfg):
        super(ImporterThread,self).__init__()
        self.templateEnv = Environment(loader=PackageLoader('asset_folder_importer','metadata_templates'))
        self.mdTemplate = self.templateEnv.get_template('vsasset.xml')
        self.queue = q
        self.st=VSStorage(host=cfg.value('vs_host'),port=cfg.value('vs_port'),user=cfg.value('vs_user'),passwd=cfg.value('vs_password'))
        self.st.populate(storageid)
        #nor is the database interface
        self.db = importer_db(__version__,hostname=cfg.value('database_host'),port=cfg.value('database_port'),username=cfg.value('database_user'),password=cfg.value('database_password'))
        self.found = 0
        self.withItems = 0
        self.imported = 0
        self.cfg = cfg
        self.ignored = 0

    def run(self):
        logging.info("In importer_thread::run...")
        while True:
            try:
                (fileref, filepath, rootpath) = self.queue.get(True,timeout=60)  #wait until a queue item is available or time out after 60s, raising Empty

                if fileref is None:
                    logging.info("Received null fileref, so teminating")
                    break

                result = self.attempt_file_import(fileref,filepath,rootpath)
                logging.debug("Data going into attempt_file_import: fileref = {0} filepath = {1} rootpath = {2}".format(fileref,filepath,rootpath))
                if isinstance(result,tuple) or isinstance(result,list):
                    (a,b,c) = result
                    self.found += a
                    self.withItems += b
                    self.imported += c
            except Empty:
                msgstring = "WARNING: importer_thread timed out waiting for more items"
                logging.warning(msgstring)
                logging.warning(traceback.format_exc())
                db.insert_sysparam("warning",msgstring)
            except VSNotFound as e:
                msgstring = "WARNING: File %s was not found: %s" % (filepath,e.message)
                logging.warning(msgstring)
                logging.warning(traceback.format_exc())
                db.insert_sysparam("warning",msgstring)
                #exit(1)
            except HTTPError as e:
                msgstring = "WARNING: HTTP error communicating with Vidispine attempting to import %s: %s" % (filepath,e.message)
                logging.warning(msgstring)
                logging.warning(traceback.format_exc())
                db.insert_sysparam("warning",msgstring)
            except FileOnIgnoreList:
                self.ignored+=1
            except StandardError as e:
                msgstring = "WARNING: error {0} occurred: {1}".format(e.__class__,e)
                logging.warning(msgstring)
                logging.warning(traceback.format_exc())
                db.insert_sysparam("warning",msgstring)
        logging.info("importer_thread completed")

    def setPermissions(self,fileref):
        file = os.path.join(fileref['filepath'],fileref['filename'])
        from subprocess import call
        try:
            call([PERMISSIONSCRIPT, file])
        except StandardError as e:
            logging.error(e)

    #this function does the actual import
    def attempt_file_import(self,fileref,filepath,rootpath):
        from asset_folder_importer.providers import LookupError
        withItems = 0
        imported = 0
        found = 0
        attempts = 0
        max_attempts = 3

        vsfile = None
        while True:
            try:
                vsfile=self.st.fileForPath(filepath)
                break
            except VSNotFound as e:
                if attempts>max_attempts:
                    logging.error("Unable to add file %s to Vidispine." % filepath)
                    raise
                logging.warning("File %s not found in Vidispine.  Attempting to update..." % filepath)
                try:
                    self.st.create_file_entity(filepath,createOnly=True)
                    time.sleep(1) #sleep 1s to allow the file to be added
                except VSConflict: #if the file was created in the meantime, don't worry about it, just retry the add
                    pass
                attempts +=1
                
        if vsfile.memberOfItem is not None:
            logging.info("Found file %s in Vidispine at file id %s, item id %s" % (filepath,vsfile.name,vsfile.memberOfItem.name))
            db.update_file_vidispine_id(fileref['id'],vsfile.memberOfItem.name)
            withItems+=1
        else:
            logging.info("Found file %s in Vidispine at file id %s, without an item membership" % (filepath,vsfile.name))
            if filepath.upper().endswith(".XMP"):
                logging.info("File is an XMP sidecar, will not attempt to import as an item")
                db.update_file_ignore(fileref['id'], True)
                raise FileOnIgnoreList(filepath)

            try:
                logging.info("Attempting to import...")
                try:
                    fileref['likely_project']=fileref['filepath'].split(os.sep)[7]
                except Exception:
                    fileref['likely_project']="unknown project"

                xdImporter=None
                xdcamref = None
                fileref['xdcam_card']=False
                if re.search(u'/BPAV/CLPR',fileref['filepath']):
                    logging.info("Got XDCAM file, probably")

                    try:
                        xdImporter = XDCAMImporter(fileref['filepath'])
                        pprint(xdImporter.__dict__)
                        xdcamref=xdImporter.__dict__
                        fileref['xdcam_card']=True
                    except Exception as e:
                        msgstring="Unable to import XDCAM metadata from path defined by %s" % fileref['filepath']
                        db.insert_sysparam("warning",msgstring)
                        db.insert_sysparam("warning",str(e))
                        db.commit()
                    #exit(1)
                else:
                    potentialXML = re.sub(u'\.[^\.]+','M01.XML',os.path.join(fileref['filepath'],fileref['filename']))
                    logging.info("Checking for potential XML at %s" % potentialXML)
                    if os.path.exists(potentialXML):
                        try:
                            xdImporter = XDCAMImporter(fileref['filepath'])
                        except InvalidDataError: #this exception will get thrown as there is no SMI file
                            pass
                        logging.info("Trying to load xdcam sidecar %s" % potentialXML)
                        xdImporter.load(specificFile=potentialXML)
                        xdcamref=xdImporter.__dict__
                        pprint(xdcamref)
                        fileref['xdcam_card']=True
                    else:
                        fileref['xdcam_card']=False

                preludeclip = None
                preludeproject = None

                preludeclip=db.get_prelude_data(fileref['prelude_ref'])

                if preludeclip is None and xdImporter is not None: #if this is a supplementary XDCAM file then try to get prelude metadata for corresponding media
                    for mediaFile in xdImporter.mediaFiles():
                        mediaFile=os.path.abspath(mediaFile)
                        #print "Looking for %s" % mediaFile
                        mediaFileRef=db.fileRecord(mediaFile)
                        #pprint(mediaFileRef)
                        if mediaFile is None:
                            break

                        preludeclip=db.get_prelude_data(mediaFileRef['prelude_ref'])
                        #pprint(preludeclip)
                        if preludeclip is not None:
                            break

                #pprint(preludeclip)
                if preludeclip is not None and preludeclip!={}:
                    preludeproject = db.get_prelude_project(preludeclip['parent_id'])

                cubaseref=get_cubase_data(fileref['filepath'],fileref['filename'])

                try:
                    try:
                        providers_config_file = self.cfg.value('footage_providers_config', noraise=False)
                    except KeyError:
                        providers_config_file = '/etc/asset_folder_importer/footage_providers.yml'

                    l = externalprovider.ExternalProviderList(providers_config_file)
                    provider_result = l.try_file(os.path.dirname(filepath),os.path.basename(filepath))
                    if provider_result is not None:
                        externaldata = provider_result.to_vs_xml()
                    else:
                        externaldata = ""
                except LookupError as e:
                    logging.error(unicode(e))
                    externaldata = ""

                try:
                    mdXML = self.mdTemplate.render({'fileref': fileref,
                                               'preluderef': preludeclip,
                                               'preludeproject': preludeproject,
                                               'xdcamref': xdcamref,
                                               'cubaseref': cubaseref,
                                               'externalmeta': externaldata})
                except AttributeError as e:
                    if 'to_vs_xml' in str(e): #catch the case where we got no external metadata
                        mdXML = self.mdTemplate.render({'fileref': fileref,
                                               'preluderef': preludeclip,
                                               'preludeproject': preludeproject,
                                               'xdcamref': xdcamref,
                                               'cubaseref': cubaseref,
                                               'externalmeta': ""})
                    else:
                        raise

                #run the compiled data through xmllint.  This should ensure that the XML is OK before we send, and also that
                #any pesky extender UTF-8 chars get escaped.
                proc = Popen(['xmllint', '--format', '-'],stdin=PIPE,stdout=PIPE,stderr=PIPE)

                #look at http://stackoverflow.com/questions/1191374/using-module-subprocess-with-timeout
                kill_proc = lambda p: p.kill()
                t = threading.Timer(XML_CHECK_TIMEOUT,kill_proc,[proc])
                t.start()
                try:
                    (stdout,stderr) = proc.communicate(mdXML)
                finally:
                    t.cancel()

                if proc.returncode!=0:
                    logging.error("xmllint failed with code {1}: {0}".format(stderr,proc.returncode))
                    fn = os.path.join(graveyard_folder,os.path.basename(filepath))
                    logging.error("outputting failed XML to {0}".format(fn))
                    with open(fn) as f:
                        f.write(mdXML)
                    raise XMLBuildError("xmllint on {0} failed: {1}".format(fn,stderr))

                mdXML=stdout

                import_tags = []
                if fileref['mime_type'] and fileref['mime_type'].startswith("video/"):
                    import_tags = ['lowres']
                elif fileref['mime_type'] and fileref['mime_type'].startswith("audio/"):
                    import_tags = ['lowaudio']
                elif fileref['mime_type'] and fileref['mime_type'].startswith("image/"):
                    import_tags = ['lowimage']
                elif fileref['mime_type'] and fileref['mime_type'] == "application/mxf":
                    import_tags = ['lowres']
                elif fileref['mime_type'] and fileref['mime_type'] == "model/vnd.mts":  #mpeg transport streams are detected as this
                    import_tags = ['lowres']

                self.st.debug=False
                self.setPermissions(fileref)
                import_job = vsfile.importToItem(mdXML, tags=import_tags, priority="LOW")

                while import_job.finished() is False:
                    logging.info("\tJob status is %s" % import_job.status())
                    sleep(5)
                    import_job.update(noraise=False)

                imported+=1

                #re-get the file information. Have some retries in case Vidispine hasn't caught up yet.
                for attempt in range(1,10):
                    try:
                        vsfile = self.st.fileForPath(filepath)
                        if vsfile.memberOfItem is None:
                            raise NotFoundError("No item information found on imported file!")

                        logging.warning("Updating file record with vidispine id %s" % vsfile.memberOfItem.name)
                        db.update_file_vidispine_id(fileref['id'],vsfile.memberOfItem.name)
                        #print "Found prelude clip info for %s" % mediaFile
                        break
                    except NotFoundError as e:
                        db.insert_sysparam("warning",e.message)
                        logging.warning("Warning: %s" %e.message)
                        db.commit()
                        return (found,withItems,imported) #no point in doing the below, since it relies on having a project reference available

                if preludeproject:
                    projectId = re.sub(u'\.[^\.]+$','',preludeproject['filename'])
                    VSprojectRef = VSCollection(host=cfg.value('vs_host'),port=cfg.value('vs_port'),user=cfg.value('vs_user'),passwd=cfg.value('vs_password'))
                    #VSprojectRef.populate(projectId)
                    VSprojectRef.name=projectId

                    VSprojectRef.addToCollection(vsfile.memberOfItem,type="item")
                elif cubaseref:
                    try:
                        projectId = cubaseref['project_id']
                        VSprojectRef = VSCollection(host=cfg.value('vs_host'),port=cfg.value('vs_port'),user=cfg.value('vs_user'),passwd=cfg.value('vs_password'))
                        VSprojectRef.populate(projectId)
                        VSprojectRef.addToCollection(vsfile.memberOfItem,type="item")
                    except Exception as e:
                        db.insert_sysparam("warning","Unable to add %s to collection %s: %s" % (vsfile.memberOfItem, projectId, e.message))
                        logging.warning("Warning: %s" % e.message)
                        db.commit()
                        return (found,withItems,imported)

                gotSidecar = False
                #Now see if there are any sidecar files that we should import against it
                for metafile in potentialSidecarFilenames(os.path.join(rootpath,filepath),isxdcam=fileref['xdcam_card']):
                    logging.info("Checking for potential sidecar at %s" %metafile)
                    if os.path.exists(metafile):
                        db.add_sidecar_ref(fileref['id'],metafile)
                        logging.debug("Data going into add_sidecar_ref: fileref['id'] = {0} metafile = {1}".format(fileref['id'],metafile))
                        logging.info("Attempting to import %s" %metafile)
                        try:
                            vsfile.memberOfItem.debug=True
                            vsfile.memberOfItem.importSidecar(metafile)
                        except VSNotFound as e:
                            logging.warning("Unable to find sidecar '%s': %s" %(metafile, e.message))
                            #raise StandardError("Exiting for debug")
                        gotSidecar = True

            except VSJobFailed as e:
                msgstring = "WARNING: Vidispine import job failed: %s" % str(e)
                print msgstring
                db.insert_sysparam("warning",msgstring)
            except VSBadRequest as e:
                msgstring = "WARNING: Vidispine import got a bad request: %s" % str(e)
                print msgstring
                db.insert_sysparam("warning",msgstring)
                db.insert_sysparam("warning","method: {0}, url: {1}, body: {2}".format(e.request_method,e.request_url,e.request_body))
            except VSException as e:
                msgstring = "WARNING: Vidispine error when importing: %s" % str(e)
                print msgstring
                db.insert_sysparam("warning",msgstring)

        db.commit()
        found+=1

        return (found,withItems,imported)


def potentialSidecarFilenames(filename,isxdcam=False):
    for x in potentialSidecarExtensions:
        potentialFile = re.sub(u'\.[^\.]+',x,filename)
        yield potentialFile
    for x in potentialSidecarExtensions:
        potentialFile = filename + x
        yield potentialFile
    if isxdcam:
        for x in potentialSidecarExtensions:
            fileAppend = "M01{0}".format(x)
            potentialFile = re.sub(u'\.[^\.]+',fileAppend,filename)
            yield potentialFile

#Look to see if we think this media file comes from Cubase
def get_cubase_data(filepath,filename):
    print "get_cubase_data: working on path %s" % filepath
    pathsegments = filepath.split(os.path.sep)
    n=len(pathsegments)
    pluto_form = re.compile(r'^\w{2}-\d+')

    for s in reversed(pathsegments):
        if s == 'Audio': #if there is an Audio folder, then the Cubase project should sit at that level
            logging.info("Found Audio at path level %d" %n)
            n-=1
            cubasepath=os.path.sep.join(pathsegments[0:n])
            print "Suspect cubase path is at %s" % cubasepath
            projects = glob("%s/*.cpr" % cubasepath)
            for p in projects:
                logging.info("\tfound project %s" % p)
                project_filename=os.path.basename(p)
                if pluto_form.match(project_filename):
                    logging.info("\tHave PLUTO form! %s" % project_filename)
                    (filebase, ext) = os.path.splitext(project_filename)

                    return { 'is_cubase': True, 'cubase_filename': project_filename, 'cubase_filepath': os.path.dirname(cubasepath),
                             'project_id': filebase}
        n=-1
    logging.info("Could not find anything resembling a Cubase path")
    return None

#This function is the main program, but is contained here to make it easier to catch exceptions
def innerMainFunc(cfg,db,limit):
    storageid=cfg.value('vs_masters_storage')
    logging.info("Connecting to storage with ID %s" % storageid)
    st=VSStorage(host=cfg.value('vs_host'),port=cfg.value('vs_port'),user=cfg.value('vs_user'),passwd=cfg.value('vs_password'))
    #st.debug=True
    st.populate(storageid)
    #logging.info("Storage path is at {0}".format(st.dataContent['uri']))
    #st.dump()

    possible_roots = []
    for uri in st.urisOfType('file',pathOnly=True,decode=True):
        logging.info("\tFile access at: %s" % uri)
        possible_roots.append(uri)

    #raise StandardError("test")

    #Step three. Now set up the template engine
    #now done in class init for ImporterThread

    #Step four. Find un-imported files and check to see if they are imported
    n=0
    found=0
    withItems=0
    imported=0

    threads = []
    input_queue = Queue()
    for i in range(0,MAXTHREADS):
        t = ImporterThread(input_queue,storageid,cfg)
        t.start()
        threads.append(t)

    for fileref in db.filesForVSID(None):
        if fileref['filename'].endswith('.cpr'): #don't import Cubase project files as items, they're already counted at the NAS
            db.update_file_ignore(fileref['id'],True)
            logging.info("Ignoring Cubase project %s/%s" % (fileref['filepath'],fileref['filename']))
            continue

        filepath = os.path.join(fileref['filepath'],fileref['filename'])
        # we need to remove the part of the filepath that corresponds to the storage path on the server
        for rootpath in possible_roots:
            filepath = re.sub(u'^{0}'.format(rootpath),'',filepath)

            n += 1

            input_queue.put([fileref,filepath,rootpath])
            #found += a
            #withItems += b
            #imported += c
        if isinstance(limit, int):
            if n > limit:
                logging.warning("Reached requested limit of {0} items, stopping for now.".format(limit))
                break

    #tell the threads to terminate now
    for t in threads:
        input_queue.put((None,None,None))

    for t in threads:
        t.join()
        if t.isAlive():
            logging.warning("Thread {0} did not terminate properly".format(t.get_ident()))

        found += t.found
        withItems += t.withItems
        imported += t.imported

    db.insert_sysparam("without_vsid",n)
    db.insert_sysparam("found_in_vidispine",found)
    db.insert_sysparam("already_attached",withItems)
    logging.info("Info: Out of %d files in the database, %d were found in Vidispine and %d were attached to items" % (n,found,withItems))
    return (found,withItems,imported)

#START MAIN
#Step one. Commandline args.
parser = OptionParser()
parser.add_option("-c","--config", dest="configfile", help="import configuration from this file")
parser.add_option("-f","--force", dest="force", help="run even if it appears that another instance is already running")
parser.add_option("-l","--limit", dest="limit", help="stop after attempting to import this many files")
(options, args) = parser.parse_args()

#Step two. Read config
pprint(args)
pprint(options)

if options.configfile:
    cfg=configfile(options.configfile)
else:
    cfg=configfile("/etc/asset_folder_importer.cfg")

if logfile is not None:
    logging.basicConfig(filename=logfile, format=LOGFORMAT, level=main_log_level)
else:
    logging.basicConfig(format=LOGFORMAT, level=main_log_level)

logging.info("-----------------------------------------------------------\n\n")
logging.info("Connecting to database on %s" % cfg.value('database_host', noraise=True))

db = importer_db(__version__,hostname=cfg.value('database_host'),port=cfg.value('database_port'),username=cfg.value('database_user'),password=cfg.value('database_password'))

lastruntime = db.lastrun_endtime()
lastruntimestamp = 0

if lastruntime is None:
    logging.error("It appears that another instance of premiere_get_referenced_media is already running.")
    if not options.force:
        logging.error("Not continuing because --force is not specified on the commandline")
        db.end_run("already_running")
        exit(1)
    logging.warning("--force has been specified so running anyway")
else:
    lastruntimestamp = time.mktime(lastruntime.timetuple())

db.start_run(__scriptname__)

try:
    if options.limit is not None:
        db.insert_sysparam("limit",int(options.limit))
        db.commit()
        innerMainFunc(cfg,db,int(options.limit))
    else:
        innerMainFunc(cfg, db, None)
    db.insert_sysparam("exit","success")
except Exception as e:
    logging.error("An error occurred:")
    logging.error(str(e.__class__) + ": " + e.message)
    logging.error(traceback.format_exc())

    msgstring="{0}: {1}".format(str(e.__class__),e.message)
    db.cleanuperror()
    db.insert_sysparam("exit","error")
    db.insert_sysparam("errormsg",msgstring)
    db.insert_sysparam("stacktrace",traceback.format_exc())
    db.commit()
finally:
    db.end_run(status=None)
