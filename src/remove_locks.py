import psycopg2
import sys
import datetime

print "Usage: remove_locks.py user password host port"

conn = psycopg2.connect(database="asset_folder_importer",user=sys.argv[1],password=sys.argv[2],host=sys.argv[3],port=sys.argv[4])

cursor=conn.cursor()

cursor.execute("select pid,timestamp from system where key='script_version' and value like 'asset_folder_vsingester%' order by timestamp desc limit 1")
if cursor.rowcount==0:
    print "No runs found for asset_folder_ingester!"
    exit(1)

row=cursor.fetchone()
pid = int(row[0])

print "Last run PID was {0} at {1}".format(pid,row[1])

cursor.execute("select id,key,value,timestamp,pid from system where key='run_end' and pid=?", (pid,))

if cursor.rowcount==0:
    print "Locked"
    print datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f+01")

    #2016-06-30 15:00:01.908556+01

    cursor.execute("insert into system (key,value,pid) values ('run_end',?,?)", (datetime.datetime.now(),str(pid),)
                   )
    conn.commit()

else:
    print "Not locked"