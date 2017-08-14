#!/usr/bin/env python

from optparse import OptionParser
from asset_folder_importer.threadpool import ThreadPool
from threading import Thread
from gnmvidispine.vs_storage import VSStorage
from asset_folder_importer.database import importer_db
from asset_folder_importer.config import configfile
from pprint import pprint
from optparse import OptionParser
import traceback
import os
import re
import time
import logging
from Queue import PriorityQueue, Empty

__version__ = "populate_asset_folder v1"

# Configurable parameters
LOGFORMAT = '%(asctime)-15s - %(levelname)s - Thread %(thread)s - %(funcName)s: %(message)s'
main_log_level = logging.DEBUG
logfile = "/var/log/plutoscripts/populate_asset_folder.log"
#End configurable parameters


logger = logging.getLogger(__name__)


class ProcessThread(Thread):
    def __init__(self, work_queue, *args, **kwargs):
        super(ProcessThread,self).__init__(*args,**kwargs)
        self._queue = work_queue
        self._timeout = 10
        self._db = importer_db(__version__,hostname=cfg.value('database_host'),port=cfg.value('database_port'),username=cfg.value('database_user'),password=cfg.value('database_password'))

    def run(self):
        while True:
            try:
                (prio, data) = self._queue.get(True,self._timeout)

                if data is None:
                    break
                self.process(data)
            except Empty:
                break
        self._db.commit()

    def process(self, rowtuple):
        """
        Process the result, by updating the row with the asset folder we got
        :param rowtuple:
        :return:
        """
        from asset_folder_importer.asset_folder_sweeper.assetfolder import get_asset_folder_for

        try:
            result = get_asset_folder_for(rowtuple[1])
            logger.info("Updating file {0} with asset folder {1}".format(rowtuple[0],rowtuple[1]))
            self._db.update_file_assetfolder(rowtuple[0], result, should_commit=False)
        except ValueError as e:
            logger.warning(str(e))
        except IndexError as e:
            logger.warning("Potential asset folder path was not long enough: {0}".format(rowtuple[1]))

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

work_queue = PriorityQueue()

logger.info("Starting up 5 threads...")
pool = ThreadPool(ProcessThread,initial_size=5)

#Now connect to db
logging.info("Connecting to database on %s" % cfg.value('database_host',noraise=True))

db = importer_db(__version__,hostname=cfg.value('database_host'),port=cfg.value('database_port'),username=cfg.value('database_user'),password=cfg.value('database_password'))
db.check_schema_23()

for filerow in db.files_with_no_assetfolder():
    logger.info("Enqueuing {0}".format(filerow))
    pool.put_queue(filerow)

logger.info("Waiting for threads to terminate")
pool.safe_terminate()

logger.info("populate_asset_folder run completed")