#!/usr/bin/python

from asset_folder_importer.database import importer_db
from datetime import datetime, timedelta
import logging
from pprint import pprint

#START MAIN
LOGFORMAT = '%(asctime)-15s - [%(name)s] - %(levelname)s - %(message)s'

main_log_level = logging.DEBUG
#logfile = "/var/log/plutoscripts/verify_files.log"
logfile = None

if logfile is not None:
    logging.basicConfig(filename=logfile, format=LOGFORMAT, level=main_log_level)
else:
    logging.basicConfig(format=LOGFORMAT, level=main_log_level)

d = importer_db("1.0.0",elastichosts='192.168.0.4:9200')

#d._escommitter.set_library_loglevel(logging.DEBUG)

delta = datetime.now() - timedelta(minutes=7)

for f in d.files(namespec="theo"):#pathspec="/Users/localhome/Downloads"):#since=delta):
    pprint(f)