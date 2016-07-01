import psycopg2
import datetime
from asset_folder_importer.config import configfile

cfg=configfile("/etc/asset_folder_importer.cfg")

conn = psycopg2.connect(database="asset_folder_importer",user=cfg.value('database_user'),password=cfg.value('database_password'),host=cfg.value('database_host'),port=cfg.value('database_port'))

cursor=conn.cursor()

cursor.execute("select pid,timestamp from system where key='script_version' and value like 'asset_folder_vsingester%' order by timestamp desc limit 1")
if cursor.rowcount==0:
    print "No runs found for asset_folder_ingester!"
    exit(1)

row=cursor.fetchone()
pid = int(row[0])

print "Last run PID was {0} at {1}".format(pid,row[1])

cursor.execute("select id,key,value,timestamp,pid from system where key='run_end' and pid=%s", (pid,))

if cursor.rowcount==0:
    print "Locked"

    cursor.execute("insert into system (key,value,pid) values ('run_end',%s,%s)", (datetime.datetime.now(),str(pid),)
                   )
    conn.commit()

else:
    print "Not locked"