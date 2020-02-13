#!/usr/bin/python3
__author__ = 'Andy Gallagher <andy.gallagher@theguardian.com>'
__version__ = 'asset_folder_verify_files $Rev$ $LastChangedDate$'
__scriptname__ = 'asset_folder_verify_files'

from asset_folder_importer.database import *
from asset_folder_importer.config import *
from asset_folder_importer.threadpool import ThreadPool
from asset_folder_importer.asset_folder_verify_files.update_vs_thread import UpdateVsThread
from time import sleep
from optparse import OptionParser
import traceback
from pprint import pprint
import os.path
import re

#START MAIN
LOGFORMAT = '%(asctime)-15s - %(levelname)s - %(message)s'
main_log_level = logging.ERROR
logfile = "/var/log/plutoscripts/verify_files.log"
#logfile = None

if logfile is not None:
    logging.basicConfig(filename=logfile, format=LOGFORMAT, level=main_log_level)
else:
    logging.basicConfig(format=LOGFORMAT, level=main_log_level)

logger = logging.getLogger(__name__)
logger.level = logging.INFO

#Step one. Commandline args.
parser = OptionParser()
parser.add_option("-c","--config", dest="configfile", help="import configuration from this file")

(options, args) = parser.parse_args()

#Step two. Read config
pprint(args)
pprint(options)

if options.configfile:
    cfg=configfile(options.configfile)
else:
    cfg=configfile("/etc/asset_folder_importer.cfg")

#Now connect to db
logging.info("Connecting to database on %s" % cfg.value('database_host',noraise=True))
db = importer_db(__version__,hostname=cfg.value('database_host'),
                 port=cfg.value('database_port'),
                 username=cfg.value('database_user'),
                 password=cfg.value('database_password'))
logging.info("Checking schema version...")
db.check_schema_20()
db.check_schema_21()
db.check_schema_22()
logging.info("done.")

db.start_run(__scriptname__)

update_vs_pool = None
try:
    pathreplacematch = re.compile(r'^/srv')

    files_existing = 0
    files_nonexisting = 0

    logging.info("Starting up VS update thread")
    update_vs_pool = ThreadPool(UpdateVsThread, config=cfg)

    c=0
    for fileref in db.files():
        print("Found %d files existing, %d files missing\r" % (files_existing,files_nonexisting)),
        c+=1
        if c>=100:
            logger.info("Found %d files existing, %d files missing\r" % (files_existing,files_nonexisting))
            c=0

        filepath = os.path.join(fileref['filepath'],fileref['filename']).encode('utf8')
        if os.path.exists(filepath):
            files_existing += 1
            continue

        altpath = pathreplacematch.sub("/Volumes",filepath.decode('utf8'))
        if os.path.exists(altpath):
            files_existing += 1
            continue

        logging.info("File {0} does not exist".format(filepath))
        files_nonexisting += 1
        db.mark_id_as_deleted(fileref['id'])
        update_vs_pool.put_queue(fileref)
        while update_vs_pool.pending() > 2000:
            logging.info("{0} items on queue already, waiting 5min for more to process".format(update_vs_pool.pending()))
            sleep(240)

    logging.info("Waiting for queued VS updates to complete....")
    while update_vs_pool.pending() > 0:
        logging.info("{0} updates to go".format(update_vs_pool.pending()))
        sleep(60)

    update_vs_pool.safe_terminate()

    logging.info("Found {0} files existing and {1} files missing".format(files_existing,files_nonexisting))
    db.insert_sysparam("existing_files",files_existing)
    db.insert_sysparam("missing_files",files_nonexisting)
    db.insert_sysparam("exit", "success")
    db.end_run(status=None)

except Exception as e:
    logging.error(str(e))
    if update_vs_pool is not None:
        update_vs_pool.safe_terminate()
    db.insert_sysparam("exit","error")
    db.insert_sysparam("error",e)
    db.insert_sysparam("traceback",traceback.format_exc())
    db.end_run(status="error")