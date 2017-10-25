#!/usr/bin/python

import psycopg2
import elasticsearch
import logging
from optparse import OptionParser
from pprint import pprint
import raven
from asset_folder_importer.fix_unattached_media.exceptions import *
from asset_folder_importer.fix_unattached_media.collection_lookup import CollectionLookup
from asset_folder_importer.config import configfile
from asset_folder_importer.fix_unattached_media.reattach_thread import ReattachThread
from asset_folder_importer.fix_unattached_media.pre_reattach_thread import PreReattachThread
from asset_folder_importer.fix_unattached_media import *
from asset_folder_importer.threadpool import ThreadPool

raven_client = raven.Client('***YOUR DSN HERE***')

path_map = None

logging.basicConfig(format='%(asctime)-15s - %(levelname)s - Thread %(threadName)s - %(funcName)s: %(message)s',
                    level=logging.ERROR,
                    filename='/var/log/plutoscripts/fix_unattached_media.log')

logger = logging.getLogger(__name__)
logger.level = logging.DEBUG

THREADS = 5

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
    parser.add_option("-c","--credentials", dest="configfile",
                      help="path to assetimporter config", default="/etc/asset_folder_importer.cfg")
    parser.add_option("--limit", dest="limit", help="stop after this number of items have been processed")
    (options, args) = parser.parse_args()

    cfg = configfile(options.configfile)
     
    reattach_pool = ThreadPool(ReattachThread, initial_size=THREADS, min_size=0, max_size=10, options=options,config=cfg,
                               raven_client=raven_client)

    pre_pool = ThreadPool(PreReattachThread, initial_size=THREADS, min_size=0, max_size=10, options=options, config=cfg,
                          output_queue=reattach_pool.queue)
    
    esclient = elasticsearch.Elasticsearch(cfg.value('portal_elastic_host'), timeout=120)

    conn = psycopg2.connect(database="asset_folder_importer", user=cfg.value('database_user'),
                            password=cfg.value('database_password'), host=cfg.value('database_host'),
                            port=5432)

    vscredentials = {
        'host': cfg.value('vs_host'),
        'port': cfg.value('vs_port'),
        'user': cfg.value('vs_user'),
        'password': cfg.value('vs_password')
    }
    
    cursor = conn.cursor()
    try:
        limit = int(options.limit)
    except TypeError:   #if it's None, or similar
        limit = None
    except ValueError:  #if it's not numeric
        limit = None
        
    cursor.execute("select imported_id,size,filepath from files where imported_id is not NULL")

    counter = 0
    processed = 0
    for row in cursor:
        counter +=1
        if limit is not None and processed>=limit:
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
            collections = lookup_vidispine_item(vscredentials, row[0])
        if collections is None:
            #attempt_reattach(reattach_pool, row[0], row[2], vscredentials)
            pre_pool.put_queue({
                'item_id': row[0],
                'size': row[1],
                'filepath': row[2]
            })
            totals['reattached'] += float(row[1])/(1024.0**2)
            processed +=1
                
            continue
        for c in collections:
            if not c in totals:
                totals[c] = float(row[1])/(1024.0**2)
            else:
                totals[c] += float(row[1])/(1024.0**2)
        
    logger.info("Waiting for threads to terminate")
    pre_pool.safe_terminate()
    reattach_pool.safe_terminate()
    
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
    pre_pool.safe_terminate()
    reattach_pool.safe_terminate()

    print "------------------------------------------------\n\n"

    pprint(totals)
    print "Invalid paths found:"
    pprint(invalid_paths)

    print "Asset folders which could not be resolved to projects:"
    pprint(not_found)
    
    raise
