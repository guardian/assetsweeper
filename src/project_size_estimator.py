#!/usr/bin/python

import psycopg2
import elasticsearch
import logging
from optparse import OptionParser
from pprint import pprint
from datetime import datetime
import raven
from asset_folder_importer.config import *
from asset_folder_importer.project_size_estimator.functions import *

# Configurable parameters
LOGFORMAT = '%(asctime)-15s - %(levelname)s - %(message)s'
main_log_level = logging.INFO
logfile = "/var/log/plutoscripts/project_size_estimator.log"
#End configurable parameters

raven_client = None

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
        totals = process_row(esclient, cfg, row, totals)

    totals['@timestamp'] = datetime.now()
    pprint(totals)
    esclient.index(index='project_sizes',doc_type='summary',body=totals)
except Exception:
    if raven_client:
        raven_client.captureException()
    raise