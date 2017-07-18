#!/usr/bin python
__author__ = 'Andy Gallagher <andy.gallagher@theguardian.com>'
__version__ = 'asset_folder_verify_files $Rev$ $LastChangedDate$'
__scriptname__ = 'asset_folder_verify_files'

from asset_folder_importer.database import *
from asset_folder_importer.config import *
from optparse import OptionParser
import traceback
from pprint import pprint
import os.path
import re

#START MAIN
LOGFORMAT = '%(asctime)-15s - %(levelname)s - %(message)s'
main_log_level = logging.DEBUG
logfile = "/var/log/plutoscripts/verify_files.log"
#logfile = None

if logfile is not None:
    logging.basicConfig(filename=logfile, format=LOGFORMAT, level=main_log_level)
else:
    logging.basicConfig(format=LOGFORMAT, level=main_log_level)

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
print "Connecting to database on %s" % cfg.value('database_host',noraise=True)
db = importer_db(__version__,hostname=cfg.value('database_host'),
                 port=cfg.value('database_port'),
                 username=cfg.value('database_user'),
                 password=cfg.value('database_password'))
print "Checking schema version...",
db.check_schema_20()
db.check_schema_21()
db.check_schema_22()
print "done."

db.start_run(__scriptname__)

pathreplacematch = re.compile(r'^/srv')

files_existing = 0
files_nonexisting = 0

try:
    for fileref in db.files():
        print("Found %d files existing, %d files missing\r" % (files_existing,files_nonexisting)),
        filepath = os.path.join(fileref['filepath'],fileref['filename'])
        if os.path.exists(filepath):
    #        logging.debug("{0} exists".format(filepath))
            files_existing += 1
            continue

        altpath = pathreplacematch.sub("/Volumes",filepath)
        if os.path.exists(altpath):
            #logging.debug("{0} exists".format(filepath))
            files_existing += 1
            continue

        logging.info("File {0} does not exist".format(filepath))
        files_nonexisting += 1
        db.mark_id_as_deleted(fileref['id'])
        #pprint(fileref)

    logging.info("Found {0} files existing and {1} files missing".format(files_existing,files_nonexisting))
    db.insert_sysparam("existing_files",files_existing)
    db.insert_sysparam("missing_files",files_nonexisting)
    db.insert_sysparam("exit", "success")
    db.end_run(status=None)

except Exception as e:
    db.insert_sysparam("exit","error")
    db.insert_sysparam("error",e.message)
    db.insert_sysparam("traceback",traceback.format_exc())
    db.end_run(status="error")