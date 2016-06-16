#!/usr/bin/python
#REquires: python-psycopg2.x86_64

__author__ = 'Andy Gallagher <andy.gallagher@theguardian.com>'
__version__ = 'asset_folder_sweeper $Rev$ $LastChangedDate$'
__scriptname__ = 'asset_folder_sweeper'

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
logfile = "/var/log/plutoscripts/asset_folder_sweeper.log"
#End configurable parameters

def posix_get_mime(filepath):
    try:
        (out, err) = subprocess.Popen(['/usr/bin/file','-b','--mime-type',filepath],stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()
        if out:
            return out.rstrip('\n')
        return None
    except Exception as e:
        print "Error using /usr/bin/file to get MIME type: %s" % e.message
        db.insert_sysparam("warning","Error using /usr/bin/file to get MIME type: %s" % e.message)
        return None

def find_files(cfg):
    #Step three. Find all relevant files and bung 'em in the database
    startpath = cfg.value('start_path',noraise=False)

    print "Running from '%s'" % startpath

    #mark a file as to be ignored, if any of these regexes match. This will prevent vsingester from importing it.
    pathShouldIgnore = [
        'Adobe Premiere Pro Preview Files',
        '\/\.',  #should ignore a literal dot, but only if it follows a /
        '\.pk$',
        '\.PFL$',
        '\.PFR$',   #Cubase creates these filetypes
        '\.peak$',
        '_synctemp', #this is created by PluralEyes
    ]

    reShouldIgnore = []
    for expr in pathShouldIgnore:
        reShouldIgnore.append(re.compile(expr))

    #try:
    n=0
    for dirpath,dirnames,filenames in os.walk(startpath):
        #print dirpath
        #pprint(filenames)
        for name in filenames:
            if name.startswith('.'):
                continue
            shouldIgnore = False

            for regex in reShouldIgnore:
                if regex.search(dirpath) is not None:
                    shouldIgnore = True

            fullpath = os.path.join(dirpath,name)
            print fullpath
            try:
                statinfo = os.stat(fullpath)
                pprint(statinfo)
                mt = None
                try:
                    (mt, encoding) = mimetypes.guess_type(fullpath, strict=False)
                except Exception as e:
                    db.insert_sysparam("warning",e.message)

                if mt is None or mt == 'None':
                    mt = posix_get_mime(fullpath)

                db.upsert_file_record(dirpath,name,statinfo,mt,ignore=shouldIgnore)
            except OSError as e:
                db.insert_sysparam("warning",str(e))
                if e.errno == 2: #No Such File Or Directory
                    db.update_file_record_gone(dirpath,name)
            n+=1
            print "%d files...\r" %n

    return n

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

#Now connect to db
logging.info("Connecting to database on %s" % cfg.value('database_host',noraise=True))

db = importer_db(__version__,hostname=cfg.value('database_host'),port=cfg.value('database_port'),username=cfg.value('database_user'),password=cfg.value('database_password'))
db.check_schema_22()
lastruntime = db.lastrun_endtime()
lastruntimestamp = 0

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

db.start_run(__scriptname__)

try:
    db.purge_system_messages(since=timedelta(days=int(cfg.value('system_message_purge_time',noraise=False))))
except KeyError as e:
    logging.warning("Unable to purge old system messages as system_message_purge_time is not present in config file")
except StandardError as e:
    logging.error("Unable to purge old system messages because of problem: {0}".format(traceback.format_exc()))

try:
    n=find_files(cfg)
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

db.end_run(status=None)
