import psycopg2
import sys

print "Usage: remove_locks.py user password host port"

conn = psycopg2.connect(database="asset_folder_importer",user=sys.argv[1],password=sys.argv[2],host=sys.argv[3],port=sys.argv[4])