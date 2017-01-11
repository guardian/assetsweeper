#!/usr/bin/python

import psycopg2
import elasticsearch
import logging
from optparse import OptionParser
from pprint import pprint
import raven
from asset_folder_importer.fix_unattached_media.exceptions import *
from asset_folder_importer.fix_unattached_media.collection_lookup import CollectionLookup
from asset_folder_importer.fix_unattached_media.reattach_thread import ReattachThread
from asset_folder_importer.fix_unattached_media import *
from asset_folder_importer.threadpool import ThreadPool

raven_client = raven.Client('https://bd4329a849e2434c9fde4b5c392b386d:64f6281adc75446d9d19d674c565cb51@sentry.multimedia.theguardian.com/18')

path_map = None

logging.basicConfig(format='%(asctime)-15s - %(levelname)s - Thread %(thread)s - %(funcName)s: %(message)s',level=logging.ERROR)

logger = logging.getLogger(__name__)
logger.level = logging.DEBUG

THREADS = 3

#START MAIN
invalid_paths = []
not_found = []
totals = {
    'unimported': 0.0,
    'unattached': 0.0,
    'reattached': 0.0,
}

try:
    parser = OptionParser()
    parser.add_option("--host", dest="dbhost", help="host to access database on", default="localhost")
    parser.add_option("-u", "--user", dest="dbuser", help="user to access database as", default="assetimporter")
    parser.add_option("-w","--passwd", dest="dbpasswd", help="password for database user")
    parser.add_option("-c","--credentials", dest="configfile", help="credentials file. Over-rides commandline options for host, port etc. if you want to use it.")
    parser.add_option("-e", "--elasticsearch", dest="eshost", help="host to contact Elastic Search")
    parser.add_option("--vidispine", dest="vshost", help="host to access vidispine on", default="localhost")
    parser.add_option("--vport", dest="vsport", help="port to access vidispine on", default=8080)
    parser.add_option("--vuser", dest="vsuser", help="user to access vidispine with", default="admin")
    parser.add_option("--vpass", dest="vspass", help="password to access vidispine with")
    parser.add_option("--limit", dest="limit", help="stop after this number of items have been processed")
    (options, args) = parser.parse_args()

    pool = ThreadPool(ReattachThread, initial_size=THREADS, min_size=0, max_size=10, options=options,
                      raven_client=raven_client)
    
    esclient = elasticsearch.Elasticsearch(options.eshost, timeout=120)

    conn = psycopg2.connect(database="asset_folder_importer", user=options.dbuser, password=options.dbpasswd, host=options.dbhost,
                            port=5432)

    cursor = conn.cursor()
    try:
        limit = int(options.limit)
    except TypeError:   #if it's None, or similar
        limit = None
    except ValueError:  #if it's not numeric
        limit = None
        
    cursor.execute("select imported_id,size,filepath from files where imported_id is not NULL")
    
    # for n in range(0,THREADS):
    #     t = ReattachThread(reattach_queue,options=options,raven_client=raven_client)
    #     t.start()
    #     reattach_threads.append(t)

    counter = 0
    processed = 0
    for row in cursor:
        counter +=1
        if processed>=limit:
            logger.info("Finishing after processing limit of {0} items".format(processed))
            break
            
        if row[0] is None:
            totals['unimported'] += float(row[1])/(1024.0**2)
            continue #the item has not yet been imported
        logger.info("Got {0} with size {1} [item {2} of {3}]".format(row[0],row[1],counter,cursor.rowcount))
        try:
            collections = lookup_portal_item(esclient,row[0])
        except PortalItemNotFound:
            logger.warning("Portal item {0} was not found in the index".format(row[0]))
            continue
        if collections is None:
            try:
                attempt_reattach(pool,row[0],row[2])
                totals['reattached'] += float(row[1])/(1024.0**2)
                processed +=1
            except InvalidProjectError as e:
                logger.error(str(e))
                logger.error("Attempting reattach of {0}".format(row[2]))
                if not row[2] in invalid_paths:
                    invalid_paths.append(row[2])
                    
                totals['unattached'] += float(row[1])/(1024.0**2)
            except NoCollectionFound as e:
                logger.error("Unable to find a collection for {0}".format(row[2]))
                if not row[2] in not_found:
                    not_found.append(row[2])
                
            continue
        for c in collections:
            if not c in totals:
                totals[c] = float(row[1])/(1024.0**2)
            else:
                totals[c] += float(row[1])/(1024.0**2)
        
    logger.info("Waiting for threads to terminate")
    pool.safe_terminate()
    
    print "------------------------------------------------\n\n"
    
    pprint(totals)
    print "Invalid paths found:"
    pprint(invalid_paths)

    print "Asset folders which could not be resolved to projects:"
    pprint(not_found)
    
except Exception:
    #capture the exception immediately
    raven_client.captureException()
    
    #ensure that all enqueud actions have completed before terminating
    pool.safe_terminate()

    print "------------------------------------------------\n\n"

    pprint(totals)
    print "Invalid paths found:"
    pprint(invalid_paths)

    print "Asset folders which could not be resolved to projects:"
    pprint(not_found)
    
    raise
