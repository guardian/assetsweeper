#!/usr/bin/env python
import psycopg2
import datetime
from asset_folder_importer.config import configfile
from optparse import OptionParser
import re

parser = OptionParser()
parser.add_option("-c","--config", dest="configfile", help="import configuration from this file",default="/etc/asset_folder_importer.cfg")
parser.add_option("-s","--scriptname",dest="scriptname", help="break locks for this script", default="asset_folder_vsingester")
(options, args) = parser.parse_args()
cfg=configfile(options.configfile)

conn = psycopg2.connect(database="asset_folder_importer",user=cfg.value('database_user'),password=cfg.value('database_password'),host=cfg.value('database_host'),port=cfg.value('database_port'))

cursor=conn.cursor()

scriptname = re.sub(r'[\'"\\;]',"",options.scriptname) #remove any nasties to prevent sql injection
cursor.execute("select pid,timestamp from system where key='script_version' and value like '{0}%' order by timestamp desc limit 1".format(scriptname))

if cursor.rowcount==0:
    print("No runs found for {0}!".format(scriptname))
    exit(1)

row=cursor.fetchone()
pid = int(row[0])

print("Last run PID was {0} at {1}".format(pid,row[1]))

cursor.execute("select id,key,value,timestamp,pid from system where key='run_end' and pid=%s", (pid,))

if cursor.rowcount==0:
    print("Script is locked. Removing lock.")

    cursor.execute("insert into system (key,value,pid) values ('run_end',%s,%s)", (datetime.datetime.now().isoformat(),str(pid),)
                   )
    conn.commit()
    print("Done.")
else:
    print("Script is not locked.")