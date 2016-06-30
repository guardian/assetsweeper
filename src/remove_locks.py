import psycopg2
import sys

print "Usage: remove_locks.py user password host port"

conn = psycopg2.connect(database="asset_folder_importer",user=sys.argv[1],password=sys.argv[2],host=sys.argv[3],port=sys.argv[4])

cursor=conn.cursor()

cursor.execute("select * from system where key='run_end' and pid=(select pid from system where key='script_version' and value like 'asset_folder_vsingester%' order by timestamp desc limit 1)")

for record in cursor:
    print record[0]