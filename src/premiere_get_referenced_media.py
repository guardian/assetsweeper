#!/usr/bin/python
__author__ = 'Andy Gallagher <andy.gallagher@theguardian.com>'
__version__ = 'premiere_get_referenced_media $Rev$ $LastChangedDate$'
__scriptname__ = 'premiere_get_referenced_media'
import xml.etree.ElementTree as ET
import sys
from pprint import pprint
import gzip
import logging
from asset_folder_importer.database import *
from asset_folder_importer.config import *
from asset_folder_importer.logginghandler import AssetImporterLoggingHandler
from optparse import OptionParser
from gnmvidispine.vs_collection import VSCollection
from gnmvidispine.vs_item import VSItem
from gnmvidispine.vidispine_api import *
from gnmvidispine.vs_storage import VSStoragePathMap, VSStorage
import time
import shutil
import tempfile
import re
import datetime
import xml.sax as sax
import raven

# Configurable parameters
LOGFORMAT = '%(asctime)-15s - %(name)s - %(levelname)s - %(message)s'
main_log_level = logging.INFO
logfile = "/var/log/plutoscripts/premiere_get_referenced_media.log"
RAVEN_DSN = 'https://12f1b44035ff41769d830b3b7a74de74:782294aa890245c4b4685cd20bd2af64@sentry.multimedia.theguardian.com/15'
#End configurable parameters

global vs_pathmap
vs_pathmap = {}


class InvalidDataError(StandardError):
    pass

class NoMediaError(StandardError):
    pass

class PremiereSAXHandler(sax.ContentHandler):
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
            self._parser.parse(f)
            f.close()
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


def id_from_filepath(filepath):
    filename = os.path.basename(filepath)
    matches = re.search(u'^(.*)\.[^\.]+$', filename)
    if matches is not None:
        return matches.group(1)
    else:
        return None


def partial_path_match(source_path, target_path, limit_len):
    source_segments = source_path.split(os.path.sep)
    target_segments = target_path.split(os.path.sep)
    return do_partial_match(source_segments, target_segments, limit_len)


def do_partial_match(source_segments, target_segments, limit_len, start=0):
    if len(target_segments) > len(source_segments):
        n = len(source_segments)
        target_segments = target_segments[0:n]
        
    for n in range(start, limit_len):
        target_path = os.path.sep.join(target_segments[n:])
        source_path = os.path.sep.join(source_segments[n:])
        if source_path.endswith('/') and not target_path.endswith('/'):
            target_path += '/'
        lg.debug("comparing %s to %s" % (source_path, target_path))
        if source_path == target_path:
            return True


def find_vsstorage_for(filepath, vs_pathmap, limit_len):
    pathsegments = filter(None, filepath.split(os.path.sep))  #filter out null values

    for key, value in vs_pathmap.items():
        source_segments = filter(None, key.split(os.path.sep))
        #must start matching at 1, as the first part is /srv on the server and /Volumes on the client
        if do_partial_match(source_segments, pathsegments, limit_len, start=1):
            return value


def find_item_id_for_path(path):
    storage = find_vsstorage_for(path, vs_pathmap,50)
    fileref = storage.fileForPath(path)
    return fileref.memberOfItem


def remove_path_chunks(filepath, to_remove):
    pathsegments = filepath.split(os.path.sep)
    return os.path.sep.join(pathsegments[to_remove:])


def process_premiere_project(filepath, db=None, cfg=None):
    global vs_pathmap
    lg.debug("---------------------------------")
    lg.info("Premiere project: %s" % filepath)

    collection_vsid = id_from_filepath(filepath)
    lg.info("Project's Vidispine ID: %s" % collection_vsid)
    vsproject = VSCollection(host=cfg.value('vs_host'), port=cfg.value('vs_port'), user=cfg.value('vs_user'),
                             passwd=cfg.value('vs_password'))
    vsproject.setName(collection_vsid)  #we don't need the actual metadata so don't bother getting it.

    #pprint(vs_pathmap)

    pp = PremiereProject()
    try:
        pp.load(filepath)
    except Exception as e:
        lg.error("Unable to read '%s': %s" % (filepath,e.message))
        lg.error(traceback.format_exc())
        print "Unable to read '%s': %s" % (filepath,e.message)
        traceback.print_exc()
        raven_client.captureException()
        return (0,0,0)

    lg.debug("determining project details and updating database...")
    try:
        projectDetails = pp.getParticulars()

        project_id = db.upsert_edit_project(os.path.dirname(filepath), os.path.basename(filepath),
                                        projectDetails['uuid'], projectDetails['version'],
                                        desc="Adobe Premiere Project",
                                        opens_with="/Applications/Adobe Premiere Pro CC 2014/Adobe Premiere Pro CC 2014.app/Contents/MacOS/Adobe Premiere Pro CC 2014")
    except ValueError as e:
        project_id = db.log_project_issue(os.path.dirname(filepath), os.path.basename(filepath), problem="Invalid project file", detail="{0}: {1} {2}".format(e.__class__,str(e),traceback.format_exc()))
        lg.error("Unable to read project file '{0}' - {1}".format(filepath,str(e)))
        lg.error(traceback.format_exc())
        raven_client.captureException()
        return (0,0,0)
    except KeyError as e:
        project_id = db.log_project_issue(os.path.dirname(filepath), os.path.basename(filepath), problem="Invalid project file", detail="{0}: {1} {2}".format(e.__class__,str(e),traceback.format_exc()))
        db.insert_sysparam("warning","Unable to read project file '{0}' - {1}".format(filepath, str(e)))
        lg.error("Unable to read project file '{0}' - {1}".format(filepath,str(e)))
        lg.error(traceback.format_exc())
        raven_client.captureException()
        return (0,0,0)

    except InvalidDataError as e:
        db.insert_sysparam("warning","Corrupted project file: {0} {1}".format(filepath,unicode(e)))
        raven_client.captureException()
        return (0,0,0)

    total_files = 0
    no_vsitem = 0
    not_in_db = 0

    lg.debug("looking for referenced media....")
    for filepath in pp.getReferencedMedia():
        total_files += 1
        server_path = re.sub(u'^/Volumes', '/srv', filepath).encode('utf-8')

        vsid = db.get_vidispine_id(server_path)
        # this call will return None if the file is not from an asset folder, e.g. newswire
        if vsid is None:
            try:
                vsid = find_item_id_for_path(server_path)
                if vsid is None:
                    lg.error("File {0} is found by Vidispine but has not been imported yet".format(server_path))
                    continue
            except VSNotFound:
                lg.error("File {0} could not be found in either Vidispine or the asset importer database".format(server_path))
                if "Internet Downloads" in server_path:
                    vsproject2 = VSCollection(host=cfg.value('vs_host'), port=cfg.value('vs_port'), user=cfg.value('vs_user'), passwd=cfg.value('vs_password'))
                    vsproject2.setName(collection_vsid)
                    vsproject2.populate
                    #vsproject2.add_mdgroup("Project")
                    vsproject2.set_metadata({'portal_mf358749': server_path}, group="Project", entitytype="item")

                continue
            
        item = VSItem(host=cfg.value('vs_host'),port=cfg.value('vs_port'),user=cfg.value('vs_user'),passwd=cfg.value('vs_password'))
        item.populate(vsid,specificFields=['gnm_asset_category'])
        if item.get('gnm_asset_category').lower() == 'branding':
            lg.info("File %s is branding, not adding to project" % (filepath, ))
            continue
            
        lg.debug("Got filepath %s" % filepath)
        fileid = db.fileId(server_path)
        if fileid:
            try:
                db.link_file_to_edit_project(fileid, project_id)
                lg.debug("Linked file %s with id %s to project %s" % (filepath, fileid, project_id))
            except AlreadyLinkedError:
                lg.info("File %s with id %s is already linked to project %s" % (filepath, fileid, project_id))
                continue
        else:
            not_in_db += 1
            lg.warning("File %s could not be found in the database" % filepath)
            continue
        n = 0
        found = False
        
        #using this construct to avoid loading more data from VS than necessary.  We simply check whether the ID exists
        #in the parent collections list (cached on the item record) without lifting any more info out of VS
        if vsproject.name in map(lambda x: x.name,item.parent_collections(shouldPopulate=False)):
            lg.info("File %s is already in project %s" % (filepath,vsproject.name))
            continue
        
        vsproject.addToCollection(item=item)    #this call will apparently succeed if the item is already added to said collection, but it won't be added twice.

    lg.info(
        "Run complete. Out of a total of %d referenced files, %d did not have a Vidispine item and %d were not in the Asset Importer database" % (
        total_files, no_vsitem, not_in_db))
    return (total_files, no_vsitem, not_in_db)

#START MAIN

#Step one. Commandline args.
parser = OptionParser()
parser.add_option("-c", "--config", dest="configfile", help="import configuration from this file")
parser.add_option("-f", "--force", dest="force", default=False,
                  help="run even if it appears that another get_referenced_media process is running, over-riding locks")
parser.add_option("-n", "--not-incremental", dest="fullrun", default=False,
                  help="do not do an incremental run (default behaviour) but re-inspect every available project in the system")
(options, args) = parser.parse_args()

raven_client = raven.Client(dsn=RAVEN_DSN)

#Step two. Read config

if options.configfile:
    cfg = configfile(options.configfile)
else:
    cfg = configfile("/etc/asset_folder_importer.cfg")

if logfile is not None:
    logging.basicConfig(filename=logfile, format=LOGFORMAT, level=main_log_level)
else:
    logging.basicConfig(format=LOGFORMAT, level=main_log_level)

logging.info("-----------------------------------------------------------\n\n")
logging.info("Connecting to database on %s" % cfg.value('database_host', noraise=True))
db = importer_db(__version__, hostname=cfg.value('database_host'), port=cfg.value('database_port'),
                 username=cfg.value('database_user'), password=cfg.value('database_password'))
logging.info("Checking schema is up-to-date...")
db.check_schema_20()
db.check_schema_21()
db.check_schema_22()
logging.info("done")

lastruntime = db.lastrun_endtime()
lastruntimestamp = 0

if lastruntime is None:
    break_lock = False
    if options.force:
        logging.warn("--force has been specified so running anyway")
        db.insert_sysparam("warning","--force has been specified so running anyway")
        break_lock = True

    logging.error("It appears that another instance of premiere_get_referenced_media is already running.")

    laststarttime = db.lastrun_starttime()
    if laststarttime is None:
        logging.error("No start time could be found for existing run. Over-riding lock")
        db.insert_sysparam("warning","No start time could be found for existing run. Over-riding lock")
        break_lock = True
        laststarttime=datetime.datetime.now()

    lag = datetime.datetime.now() - laststarttime
    logging.info("time lag is %s" % (str(lag)))

    if lag.days > 0:
        logging.error("Last start is more than 1 day ago, so assuming lock is stale.")
        db.insert_sysparam("warning","Last start is more than 1 day ago, so assuming lock is stale.")
        break_lock = True

    if not break_lock:
        logging.error("Not continuing because --force is not specified on the commandline and lock is not stale")
        db.end_run("error")
        exit(1)

    lastruntimestamp = time.mktime(laststarttime.timetuple())
else:
    lastruntimestamp = time.mktime(lastruntime.timetuple())

logging.info("Last run of the script was at %s. Only searching for files modified since." % lastruntime)

dbhandler = AssetImporterLoggingHandler(db)
dbhandler.setLevel(logging.WARNING)
lg = logging.getLogger('premiere_get_referenced_media')
lg.addHandler(dbhandler)

db.start_run(__scriptname__)

start_dir = cfg.value("premiere_home")
lg.info("Starting at %s" % start_dir)
total_projects = 0
total_references = 0
total_no_vsitem = 0
total_not_in_db = 0

try:
    global vs_pathmap
    #load up a mapping table from server system path to Vidispine storages. This is used by process_premiere_project to work out where to look for files in Vidispine
    vs_pathmap = VSStoragePathMap(uriType="file://", stripType=True, host=cfg.value('vs_host'),
                                  port=cfg.value('vs_port'), user=cfg.value('vs_user'), passwd=cfg.value('vs_password'))

    if not os.path.exists(start_dir):
        msg = "The given start path %s does not exist." % start_dir
        raise StandardError(msg)

    for (dirpath, dirname, filenames) in os.walk(start_dir):
        for f in filenames:
            if not f.endswith('.prproj'):
                continue
            lg.debug("found Premiere project at %s in %s" % (f, dirpath))
            filepath = "(unknown)"
            try:
                filepath = os.path.join(dirpath, f)
                statinfo = os.stat(filepath)
            except OSError as e:
                lg.warning("Unable to stat premiere project at {0}: {1}",filepath,e)
                continue

            file_mtime = dt.datetime.fromtimestamp(statinfo.st_mtime)
            raven_client.user_context({
                'filepath': filepath,
                'statinfo': statinfo,
                'mtime': file_mtime,
            })

            if not options.fullrun:
                if statinfo.st_mtime < lastruntimestamp:
                    lg.debug("project last modified time was %s which is earlier than the last script run" % file_mtime)
                    continue

            lg.debug("last modified time: %s" % file_mtime)
            total_projects += 1
            try:
                (project_refs, no_vsitem, not_in_db) = process_premiere_project(filepath, db=db, cfg=cfg)
                lg.info(
                    "Processed Premiere project %s which had %d references, of which %d were not in Vidispine yet and %d were not in the Asset Importer database" %
                    (filepath, project_refs, no_vsitem, not_in_db))

                total_references += project_refs
                total_no_vsitem += no_vsitem
                total_not_in_db += not_in_db
            except NoMediaError:
                lg.warning("Premiere project %s has no media references" % filepath)
            except VSException as e:
                raven_client.captureException()
                lg.warning(
                    "Got error of type %s when processing premiere project %s (%s)" % (e.__class__, filepath, e.message))

    db.insert_sysparam("total_projects", total_projects)
    db.insert_sysparam("total_referenced_media", total_references)
    db.insert_sysparam("total_linked_to_vidispine", total_no_vsitem)
    db.insert_sysparam("total_unknown_to_assetimporter", total_not_in_db)
    db.insert_sysparam("exit", "success")
    lg.info(
        "Run completed at {time} with a total of {projects} projects processed and a total of {refs} references".format(
            time=dt.datetime.now(),
            projects=total_projects,
            refs=total_references
        ))
    db.end_run("success")
    db.commit()

except Exception as e:
    raven_client.captureException()
    #lg.error(str(e.__class__) + ": " + e.message, exc_info=True)
    #print str(e.__class__) + ": " + e.message
    lg.error(traceback.format_exc())

    msgstring = "{0}: {1}".format(str(e.__class__), e.message)
    db.cleanuperror()
    db.insert_sysparam("exit", "error")
    db.insert_sysparam("errormsg", msgstring)
    db.insert_sysparam("stacktrace", traceback.format_exc())
    db.end_run("error")
    db.commit()
