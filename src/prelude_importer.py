#!/usr/bin/python3
#Requires: python-psycopg2.x86_64

__author__ = 'Andy Gallagher <andy.gallagher@theguardian.com>'
__version__ = 'prelude_importer $Rev$ $LastChangedDate$'
__scriptname__ = 'prelude_importer'

from optparse import OptionParser
import os
from pprint import pprint
from asset_folder_importer.config import *
from asset_folder_importer.database import *
from asset_folder_importer.prelude_importer import *
import traceback
import logging

# Configurable parameters
LOGFORMAT = '%(asctime)-15s - %(levelname)s - %(message)s'
main_log_level = logging.DEBUG
logfile = "/var/log/plutoscripts/prelude_importer.log"
#End configurable parameters

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

if logfile is not None:
    logging.basicConfig(filename=logfile, format=LOGFORMAT, level=main_log_level)
else:
    logging.basicConfig(format=LOGFORMAT, level=main_log_level)

#Now connect to db
print("Connecting to database on %s" % cfg.value('database_host',noraise=True))
logging.info("Connecting to database on %s" % cfg.value('database_host',noraise=True))
db = importer_db(__version__,hostname=cfg.value('database_host'),port=cfg.value('database_port'),username=cfg.value('database_user'),password=cfg.value('database_password'))
db.check_schema_22()
db.start_run(__scriptname__)

#Step three. Find some prelude files
startpath=cfg.value('prelude_home')
print("Running from '%s'" % startpath)
db.insert_sysparam("startpath",startpath)

st='success'
try:
    n=0
    nclips=0
    if not os.path.exists(startpath):
        msg = "Provided Prelude project path %s does not exist on this server" % startpath
        raise Exception(msg)

    for dirpath,dirnames,filenames in os.walk(startpath):
        #print dirpath
        #pprint(filenames)
        for name in filenames:
            try:
                if name.startswith('.'):
                    continue

                if name.endswith('.plproj'):
                    logging.debug("Data going into preludeimporter: dirpath = {0} name = {1}".format(dirpath,name))
                    preludeproject = preludeimporter(db,os.path.join(dirpath,name))
                    preludeproject.dump()
                    #for c in preludeproject.clips():
                        #c.dump()
                    n+=1
                    nclips+=preludeproject.nclips()

            except NotPreludeProjectException as e:
                msg = "WARNING: {name} is not a Prelude project: {error}".format(
                    name=os.path.join(dirpath,name),
                    error=e.message
                )
                db.insert_sysparam("warning",msg)
                db.commit()
                print(msg)

            except InvalidXMLException as e:
                msg = "WARNING: {name} is corrupted or not a Prelude project: {error}".format(
                    name=os.path.join(dirpath,name),
                    error=e
                )
                db.insert_sysparam("warning",msg)
                db.commit()
                print(msg)
except Exception as e:
    msg = "ERROR: {0}: {1}".format(
        e.__repr__(),
        e
    )
    st='error'
    db.insert_sysparam("error",msg)
    db.insert_sysparam("traceback",traceback.format_exc())
    db.commit()

print("Run finished: {0}. Found {1} prelude projects containing {2} clips".format(st,n,nclips))

db.insert_sysparam("found_prelude_projects",n)
db.insert_sysparam("found_prelude_clips",nclips)
db.end_run(status=st)
db.commit()
