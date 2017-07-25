#!/usr/bin/python

import psycopg2
import elasticsearch
import logging
from optparse import OptionParser
from pprint import pprint
import re
from datetime import datetime
import raven
from urllib3.exceptions import ReadTimeoutError
from elasticsearch.exceptions import ConnectionTimeout
from time import sleep
from asset_folder_importer.config import *

# Configurable parameters
LOGFORMAT = '%(asctime)-15s - %(levelname)s - %(message)s'
main_log_level = logging.INFO
logfile = "/var/log/plutoscripts/project_size_estimator.log"
#End configurable parameters

id_xplodr = re.compile(r'^(?P<site>\w{2})-(?P<numeric>\d+)')


class PortalItemNotFound(StandardError):
    pass


def lookup_portal_item(esclient, cfg, item_id):
    """
    Returns an array of the collections that this item belongs to, according to Portal's ES index.
    :param esclient: Elastic search client
    :param cfg: Asset Sweeper configuration object
    :param item_id: Item ID to look up
    :return: List
    """
    parts = id_xplodr.match(item_id)
    query = {
        'query': {
            'filtered': {
                'filter': {
                    'term': {
                        'vidispine_id_str_ex': item_id
                    }
                }
            }
        }
    }

    wait_time = 2
    while True:
        try:
            result = esclient.search(index=cfg.value('portal_elastic_index'),doc_type='item',body=query)
            break
        except ReadTimeoutError as e:
            logging.warning(str(e))
            sleep(wait_time)
            wait_time *= 2
        except ConnectionTimeout as e:
            logging.warning(str(e))
            sleep(wait_time)
            wait_time *= 2
    hits = result['hits']['hits']
    if len(hits)==0: raise PortalItemNotFound(item_id)

    #pprint(hits[0]['_source'])
    if not 'f___collection_str' in hits[0]['_source']:
        return None

    #use this to determine if it is online or nearline
    #on_storages = hits[0]['_source']['storage_original']
    #storage_count = hits[0]['_source']['storage_original_size']
    return hits[0]['_source']['f___collection_str'] #this is an array

#START MAIN
try:
    parser = OptionParser()
    parser.add_option("--host", dest="dbhost", help="host to access database on", default="localhost")
    parser.add_option("-u", "--user", dest="dbuser", help="user to access database as", default="assetimporter")
    parser.add_option("-w","--passwd", dest="dbpasswd", help="password for database user")
    parser.add_option("-c","--config", dest="configfile", help="import configuration from this file")
    parser.add_option("--elastic", dest="eshost", help="host(s) to access elasticsearch on", default="localhost:9200")
    (options, args) = parser.parse_args()

    if options.configfile:
        cfg=configfile(options.configfile)
    else:
        cfg=configfile("/etc/asset_folder_importer.cfg")

    if logfile is not None:
        logging.basicConfig(filename=logfile, format=LOGFORMAT, level=main_log_level)
    else:
        logging.basicConfig(format=LOGFORMAT, level=main_log_level)

    try:
        raven_client = raven.Client(cfg.value("raven_dsn"))
    except Exception as e:
        logging.error("Unable to set up Sentry logging: {0}".format(e))

    esclient = elasticsearch.Elasticsearch(options.eshost)

    conn = psycopg2.connect(database="asset_folder_importer", user=options.dbuser, password=options.dbpasswd, host=options.dbhost,
                            port=5432)

    cursor = conn.cursor()
    cursor.execute("select imported_id,size from files")

    totals = {
        'unimported': 0.0,
        'unattached': 0.0,
    }

    for row in cursor:
        if row[0] is None:
            totals['unimported'] += float(row[1])/(1024.0**2)
            continue #the item has not yet been imported
        print "Got {0} with size {1}".format(row[0],row[1])
        try:
            collections = lookup_portal_item(esclient,cfg,row[0])
        except PortalItemNotFound:
            logging.warning("Portal item {0} was not found in the index".format(row[0]))
            collections = None
        if collections is None:
            totals['unattached'] += float(row[1])/(1024.0**2)
            continue
        for c in collections:
            if not c in totals:
                totals[c] = float(row[1])/(1024.0**2)
            else:
                totals[c] += float(row[1])/(1024.0**2)

    totals['@timestamp'] = datetime.now()
    pprint(totals)
    esclient.index(index='project_sizes',doc_type='summary',body=totals)
except Exception:
    raven_client.captureException()
    raise