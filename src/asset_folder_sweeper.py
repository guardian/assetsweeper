#!/usr/bin/python3
from asset_folder_importer.database import *
from asset_folder_importer.config import *
from pprint import pprint
from optparse import OptionParser
import traceback
from datetime import timedelta
import datetime
import time
import logging
from asset_folder_importer.asset_folder_sweeper.find_files import find_files
import raven

__author__ = 'Andy Gallagher <andy.gallagher@theguardian.com>'
__version__ = 'asset_folder_sweeper $Rev$ $LastChangedDate$'
__scriptname__ = 'asset_folder_sweeper'
# Configurable parameters
LOGFORMAT = '%(asctime)-15s - %(levelname)s - %(message)s'
#logfile = None
logfile = "/var/log/plutoscripts/asset_folder_sweeper.log"
#End configurable parameters

#START MAIN

#Step one. Commandline args.
parser = OptionParser()
parser.add_option("-s", "--server", dest="hostname", help="connect to Vidispine on this host")
parser.add_option("-p", "--port", dest="port",
                  help="[OPTIONAL] use this port to communicate with Vidispine (default: 8080)")
parser.add_option("-u", "--user", dest="user", help="use this username when communicating with Vidispine")
parser.add_option("-w", "--password", dest="passwd", help="use this password when communicating with Vidispine")
parser.add_option("-c","--config", dest="configfile", help="import configuration from this file")
parser.add_option("-f","--force", dest="force", help="over-ride any existing lock and run anyway, possibly competing with another instance")
parser.add_option("-l","--loglevel", dest="loglevel", help="logging level. 0 for errors only, 1 for warnings, 2 for log and 3 for debug", default=1)
(options, args) = parser.parse_args()

#Step two. Read config
if options.configfile:
    cfg=configfile(options.configfile)
else:
    cfg=configfile("/etc/asset_folder_importer.cfg")

if options.loglevel==0:
    main_log_level=logging.ERROR
elif options.loglevel==1:
    main_log_level=logging.WARNING
elif options.loglevel==2:
    main_log_level=logging.INFO
elif options.loglevel==3:
    main_log_level=logging.DEBUG
else:
    main_log_level=logging.ERROR

raven_client = raven.Client(dsn=cfg.value('sentry_dsn'))

if logfile is not None:
    logging.basicConfig(filename=logfile, format=LOGFORMAT, level=main_log_level)
else:
    logging.basicConfig(format=LOGFORMAT, level=main_log_level)

#Now connect to db
logging.info("Connecting to database on %s" % cfg.value('database_host',noraise=True))

try:
    db = importer_db(__version__,hostname=cfg.value('database_host'),port=cfg.value('database_port'),username=cfg.value('database_user'),password=cfg.value('database_password'))
    db.check_schema_22()
    lastruntime = db.lastrun_endtime()
    lastruntimestamp = 0
except Exception as e:
    raven_client.captureException()
    raise

if lastruntime is None:
    break_lock = False
    if options.force:
        logging.warn("--force has been specified so running anyway")
        db.insert_sysparam("warning","--force has been specified so running anyway")
        break_lock = True

    logging.error("It appears that another instance of asset_folder_sweeper is already running.")

    laststarttime = db.lastrun_starttime()
    if laststarttime is None:
        logging.error("No start time could be found for existing run. Over-riding lock")
        db.insert_sysparam("warning","No start time could be found for existing run. Over-riding lock")
        break_lock = True
        laststarttime=datetime.datetime.now()

    lag = datetime.datetime.now() - laststarttime
    logging.info("Last run started %s ago" % (str(lag)))

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

logging.info("Last run of the script was at %s." % lastruntime)

try:
    db.start_run(__scriptname__)
except Exception as e:
    raven_client.captureException()
    raise

try:
    db.purge_system_messages(since=timedelta(days=int(cfg.value('system_message_purge_time',noraise=False))))
except KeyError as e:
    logging.warning("Unable to purge old system messages as system_message_purge_time is not present in config file")
    raven_client.captureException()
except Exception as e:
    logging.error("Unable to purge old system messages because of problem: {0}".format(traceback.format_exc()))
    raven_client.captureException()

try:
    n=find_files(cfg,db,raven_client=raven_client)
    db.insert_sysparam("file_records",n)
    db.insert_sysparam("exit","success")
    logging.info("Run completed. Found {0} file records.\n".format(n))
    db.commit()
except Exception as e:
    db.insert_sysparam("exit","error")
    db.insert_sysparam("error",e.message)
    db.insert_sysparam("traceback",traceback.format_exc())
    logging.error(traceback.format_exc())
    db.commit()
    raven_client.captureException()

db.end_run(status=None)
