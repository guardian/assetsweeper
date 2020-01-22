#!/usr/bin/python3
__author__ = 'Andy Gallagher <andy.gallagher@theguardian.com>'
__version__ = 'premiere_get_referenced_media $Rev$ $LastChangedDate$'
__scriptname__ = 'premiere_get_referenced_media'

from asset_folder_importer.database import *
from asset_folder_importer.config import *
from asset_folder_importer.logginghandler import AssetImporterLoggingHandler
from asset_folder_importer.premiere_get_referenced_media.Exceptions import NoMediaError, InvalidDataError
from asset_folder_importer.premiere_get_referenced_media.processor import process_premiere_project
from optparse import OptionParser
from gnmvidispine.vidispine_api import *
from gnmvidispine.vs_storage import VSStoragePathMap, VSStorage
import time
import datetime
import raven

# Configurable parameters
LOGFORMAT = '%(asctime)-15s - %(name)s - %(levelname)s - %(message)s'
main_log_level = logging.INFO
logfile = "/var/log/plutoscripts/premiere_get_referenced_media.log"
#End configurable parameters

global vs_pathmap
vs_pathmap = {}


#START MAIN

#Step one. Commandline args.
parser = OptionParser()
parser.add_option("-c", "--config", dest="configfile", help="import configuration from this file")
parser.add_option("-f", "--force", dest="force", default=False,
                  help="run even if it appears that another get_referenced_media process is running, over-riding locks")
parser.add_option("-n", "--not-incremental", dest="fullrun", default=False,
                  help="do not do an incremental run (default behaviour) but re-inspect every available project in the system")
(options, args) = parser.parse_args()

#Step two. Read config

if options.configfile:
    cfg = configfile(options.configfile)
else:
    cfg = configfile("/etc/asset_folder_importer.cfg")

raven_client = raven.Client(dsn=cfg.value('sentry_dsn'))

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
    #load up a mapping table from server system path to Vidispine storages. This is used by process_premiere_project to work out where to look for files in Vidispine
    vs_pathmap = VSStoragePathMap(uriType="file://", stripType=True, host=cfg.value('vs_host'),
                                  port=cfg.value('vs_port'), user=cfg.value('vs_user'), passwd=cfg.value('vs_password'))

    if not os.path.exists(start_dir):
        msg = "The given start path %s does not exist." % start_dir
        raise Exception(msg)

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
                (project_refs, no_vsitem, not_in_db) = process_premiere_project(filepath, raven_client=raven_client, vs_pathmap=vs_pathmap, db=db, cfg=cfg)
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
                    "Got error of type %s when processing premiere project %s (%s)" % (e.__class__, filepath, e))

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
    lg.error(traceback.format_exc())

    msgstring = "{0}: {1}".format(str(e.__class__), e)
    db.cleanuperror()
    db.insert_sysparam("exit", "error")
    db.insert_sysparam("errormsg", msgstring)
    db.insert_sysparam("stacktrace", traceback.format_exc())
    db.end_run("error")
    db.commit()
