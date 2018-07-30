#!/usr/bin/env python

### This script is intended to tell Vidispine about _every_ file in the deleted_items table.
### It is not intended to be run on a regular basis; asset_folder_verify_files will do that. The intention is to run as a
### one-off hit to update Vidispine with the _entire_ contents of the deleted_items table
__version__  = "vs_resync_deleted"

from asset_folder_importer.asset_folder_verify_files.update_vs_thread import UpdateVsThread
from asset_folder_importer.threadpool import ThreadPool
from asset_folder_importer.config import configfile
from asset_folder_importer.database import importer_db
import raven
from optparse import OptionParser
import logging
import sys

# Configurable parameters
LOGFORMAT = '%(asctime)-15s - %(levelname)s - %(message)s'
#logfile = None
logfile = "/var/log/plutoscripts/vs_resync_deleted.log"
#End configurable parameters

#START MAIN
logging.basicConfig(level=logging.INFO, format=LOGFORMAT, filename=logfile)
logger = logging.getLogger(__name__)
logger.level = logging.DEBUG

#Step one. Commandline args.
parser = OptionParser()
parser.add_option("-s", "--server", dest="hostname", help="connect to Vidispine on this host")
parser.add_option("-p", "--port", dest="port",
                  help="[OPTIONAL] use this port to communicate with Vidispine (default: 8080)")
parser.add_option("-u", "--user", dest="user", help="use this username when communicating with Vidispine")
parser.add_option("-w", "--password", dest="passwd", help="use this password when communicating with Vidispine")
parser.add_option("-c","--config", dest="configfile", help="import configuration from this file")
parser.add_option("-t", "--threads", dest="threads", help="number of threads to communicate with Vidispine", default=4)
(options, args) = parser.parse_args()

#Step two. Read config
if options.configfile:
    cfg=configfile(options.configfile)
else:
    cfg=configfile("/etc/asset_folder_importer.cfg")

#Step three. Set up pools.
pool = ThreadPool(UpdateVsThread,initial_size=int(options.threads), config=cfg)

raven_client = raven.Client(dsn=cfg.value("sentry_dsn"))

#Step four. Scan the database table and update VS
#Now connect to db
logger.info("Connecting to database on %s" % cfg.value('database_host',noraise=True))

try:
    db = importer_db(__version__,hostname=cfg.value('database_host'),port=cfg.value('database_port'),username=cfg.value('database_user'),password=cfg.value('database_password'))
    db.check_schema_22()
    lastruntime = db.lastrun_endtime()
    lastruntimestamp = 0
except Exception as e:
    raven_client.captureException()
    raise

n=0
c=0
for fileref in db.deleted_files():
    n+=1
    c+=1
    if c>100:
        c=0
        sys.stdout.write("{0}\r".format(n))
    pool.put_queue(fileref)

logger.info("Sent all deleted media references to queue")