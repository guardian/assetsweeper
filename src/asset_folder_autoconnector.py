#!/usr/bin/env pyton
__author__ = 'Andy Gallagher <andy.gallagher@theguardian.com>'
__version__ = 'asset_folder_autoconnector $Rev$ $LastChangedDate$'

import os
from asset_folder_importer.database import *
from asset_folder_importer.config import *
from pprint import pprint
from optparse import OptionParser
import traceback
import mimetypes
import subprocess
from datetime import timedelta
import datetime
import time
import logging

# Configurable parameters
LOGFORMAT = '%(asctime)-15s - %(levelname)s - %(message)s'
main_log_level = logging.DEBUG
#logfile = None
logfile = "/var/log/plutoscripts/asset_folder_autoconnector.log"
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
parser.add_option("-e","--elasticsearch", dest="elasticsearch", help="IP address(es) to contact Elastic Search on")
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

#Now connect to db
logging.info("Connecting to database on %s" % cfg.value('database_host',noraise=True))

db = importer_db(__version__,hostname=cfg.value('database_host'),port=cfg.value('database_port'),
                 username=cfg.value('database_user'),password=cfg.value('database_password'),
                 elastichosts=cfg.value('elasticsearch'))
lastruntime = db.lastrun_endtime()
lastruntimestamp = 0

lockwarning = None
if lastruntime is None:
    break_lock = False
    if options.force:
        logging.warn("--force has been specified so running anyway")
        #db.insert_sysparam("warning","--force has been specified so running anyway")
        lockwarning = "--force has been specified so running anyway"
        break_lock = True

    logging.error("It appears that another instance of asset_folder_sweeper is already running.")

    laststarttime = db.lastrun_starttime()
    if laststarttime is None:
        logging.error("No start time could be found for existing run. Over-riding lock")
        #db.insert_sysparam("warning","No start time could be found for existing run. Over-riding lock")
        lockwarning = "No start time could be found for existing run. Over-riding lock"
        break_lock = True
        laststarttime=datetime.datetime.now()

    lag = datetime.datetime.now() - laststarttime
    logging.info("Last run started %s ago" % (str(lag)))

    if lag.days > 0:
        logging.error("Last start is more than 1 day ago, so assuming lock is stale.")
        #db.insert_sysparam("warning","Last start is more than 1 day ago, so assuming lock is stale.")
        lockwarning = "Last start is more than 1 day ago, so assuming lock is stale."
        break_lock = True

    if not break_lock:
        logging.error("Not continuing because --force is not specified on the commandline and lock is not stale")
        db.end_run("error")
        exit(1)

    lastruntimestamp = time.mktime(laststarttime.timetuple())
else:
    lastruntimestamp = time.mktime(lastruntime.timetuple())

logging.info("Last run of the script was at %s." % lastruntime)

db.start_run()

for record in db.files_not_connected_to_project():
    pprint(record)