#!/usr/bin/python
#Requires: python-psycopg2.x86_64

__author__ = 'Andy Gallagher <andy.gallagher@theguardian.com>'
__version__ = 'prelude_importer $Rev$ $LastChangedDate$'


from optparse import OptionParser
import os
from pprint import pprint
from asset_folder_importer.config import *
from asset_folder_importer.database import *
from asset_folder_importer.prelude_importer import *
import traceback

#Step one. Commandline args.
parser = OptionParser()
parser.add_option("-c","--config", dest="configfile", help="import configuration from this file")

(options, args) = parser.parse_args()

#Step two. Read config
if options.configfile:
    cfg=configfile(options.configfile)
else:
    cfg=configfile("/etc/asset_folder_importer.cfg")

#Now connect to db
print "Connecting to database on %s" % cfg.value('database_host',noraise=True)
db = importer_db(__version__,hostname=cfg.value('database_host'),port=cfg.value('database_port'),
                 username=cfg.value('database_user'),password=cfg.value('database_password'),
                 elastichosts=cfg.value('elasticsearch'))
db.start_run()

#Step three. Find some prelude files
startpath=cfg.value('prelude_home')
print "Running from '%s'" % startpath
db.insert_sysparam("startpath",startpath)

n=0
nclips=0
st='success'
try:
    if not os.path.exists(startpath):
        msg = "Provided Prelude project path %s does not exist on this server" % startpath
        raise StandardError(msg)

    for dirpath,dirnames,filenames in os.walk(startpath):
        #print dirpath
        #pprint(filenames)
        for name in filenames:
            try:
                if name.startswith('.'):
                    continue

                if name.endswith('.plproj'):
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
                print msg

            except InvalidXMLException as e:
                msg = "WARNING: {name} is corrupted or not a Prelude project: {error}".format(
                    name=os.path.join(dirpath,name),
                    error=e.message
                )
                db.insert_sysparam("warning",msg)
                print msg
except Exception as e:
    print unicode(e)
    print traceback.format_exc()
    st='error'
    db.insert_sysparam("error",unicode(e))
    db.insert_sysparam("traceback",traceback.format_exc())
    db.commit()

print "Run finished: {0}. Found {1} prelude projects containing {2} clips".format(st,n,nclips)

db.insert_sysparam("found_prelude_projects",n)
db.insert_sysparam("found_prelude_clips",nclips)
db.end_run(status=st)
db.commit()
