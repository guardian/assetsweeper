#!/usr/bin/python3

__version__ = "find_flushable_unimported_media v1"

import logging
from optparse import OptionParser
from asset_folder_importer.config import configfile
from asset_folder_importer.database import importer_db
import urllib.request, urllib.parse, urllib.error
import requests
import os.path
import time
import traceback

# Configurable parameters
LOGFORMAT = '%(asctime)-15s - %(levelname)s - Thread %(thread)s - %(funcName)s: %(message)s'
main_log_level = logging.ERROR
#logfile = None
logfile = "/var/log/plutoscripts/find_flushable_unimported_media.log"
#End configurable parameters


class AssetFolderCache(object):
    def __init__(self, cfg):
        self._cfg = cfg
        self._cache = {}

    def get_pluto_info(self, asset_folder_path):
        url = "http://{0}:{1}/gnm_asset_folder/lookup?path={2}".format(cfg.value('pluto_host'), cfg.value('pluto_port'), urllib.parse.quote(asset_folder_path, safe=''))
        logger.debug(url)

        while True:
            response = requests.get(url, auth=(cfg.value('vs_user'), cfg.value('vs_password')))
            if response.status_code==200:
                return response.json()
            elif response.status_code==404:
                return None
            elif response.status_code>=400 and response.status_code<500:
                logger.error("Error {0} accessing {1}: {2}".format(response.status_code, url, response.text))
                raise Exception("Could not look up")
            else:
                logger.warning("Error {0} accessing {1}. Retrying in 10s".format(response.status_code, url))
                time.sleep(10)

    def get_project_info(self, projectid):
        url = "http://{0}:{1}/project/{2}/api".format(cfg.value('pluto_host'), cfg.value('pluto_port'), projectid)
        logger.debug(url)

        while True:
            response = requests.get(url, auth=(cfg.value('vs_user'), cfg.value('vs_password')), headers={'Accept': 'application/json'})
            if response.status_code==200:
                return response.json()
            elif response.status_code>=400 and response.status_code<500:
                logger.error("Error {0} accessing {1}: {2}".format(response.status_code, url, response.text))
                raise Exception("Could not look up")
            else:
                logger.warning("Error {0} accessing {1}. Retrying in 10s".format(response.status_code, url))
                time.sleep(10)

    def lookup(self, complete_path):
        """
        returns a dict of project information about the attached asset folder, from the local cache if possible
        :param complete_path:
        :return:
        """
        pathparts = complete_path.split("/")
        asset_folder_path = "/".join(pathparts[0:8])

        if asset_folder_path in self._cache:
            return self._cache[asset_folder_path]

        pluto_info = self.get_pluto_info(asset_folder_path)
        if pluto_info is None:
            return None
        logger.debug(pluto_info)
        project_info = self.get_project_info(pluto_info['project'])
        logger.debug(project_info)

        self._cache[asset_folder_path] = project_info
        return project_info

#START MAIN
#Step one. Commandline args.
parser = OptionParser()
parser.add_option("-c","--config", dest="configfile", help="import configuration from this file")
(options, args) = parser.parse_args()

if options.configfile:
    cfg=configfile(options.configfile)
else:
    cfg=configfile("/etc/asset_folder_importer.cfg")

if logfile is not None:
    logging.basicConfig(filename=logfile, format=LOGFORMAT, level=main_log_level)
else:
    logging.basicConfig(format=LOGFORMAT, level=main_log_level)

logger = logging.getLogger("__main__")
logger.level = logging.INFO

logger.info("-----------------------------------------------------------\n\n")
logger.info("Connecting to database on %s" % cfg.value('database_host', noraise=True))

db = importer_db(__version__,hostname=cfg.value('database_host'),port=cfg.value('database_port'),username=cfg.value('database_user'),password=cfg.value('database_password'))

ac = AssetFolderCache(cfg)

total_completed_sizes = 0
total_all_sizes = 0
total_notfound_sizes = 0
assetfolder_not_found = []
counted_files = 0

fp_toflush = open("to_flush.lst","w")
fp_noassetfolder = open("no_asset_folder.lst","w")

try:
    for unimported_file in db.filesForVSID(vsid=None):
        counted_files+=1
        #logger.debug("{0}".format(os.path.join(unimported_file['filepath'],unimported_file['filename'])))

        if unimported_file['size'] is None:
            logger.warning("{0} has no size registered".format(os.path.join(unimported_file['filepath'],unimported_file['filename'])))
            unimported_file['size'] = 0

        total_all_sizes += (unimported_file['size']/1024**3)

        projectinfo = ac.lookup(unimported_file['filepath'])
        if projectinfo is None:
            fullpath = os.path.join(unimported_file['filepath'],unimported_file['filename'])
            logger.debug("{0}: could not find asset folder".format(fullpath))
            assetfolder_not_found.append(fullpath)
            total_notfound_sizes += (unimported_file['size']/1024**3)
            fp_noassetfolder.write("{0}\n".format(fullpath))
            continue

        if projectinfo['gnm_project_status'] == 'Completed':
            fullpath = os.path.join(unimported_file['filepath'],unimported_file['filename'])
            total_completed_sizes += (unimported_file['size']/1024**3)
            fp_toflush.write("{0},{1}\n".format(projectinfo['collection_id'], fullpath))

        logger.info("{0} files: total completed: {1}Gb, total asset folder not found: {2}Gb, total of everything: {3}Gb".format(counted_files, total_completed_sizes, total_notfound_sizes, total_all_sizes))

    if len(assetfolder_not_found)>0:
        logger.warning("{0} files had unrecognized asset folders:".format(len(assetfolder_not_found)))
        for path in assetfolder_not_found:
            logger.warning("\t{0}".format(path))

    logger.info("All done")
except Exception as e:
    logger.error(traceback.format_exc())

fp_toflush.close()
fp_noassetfolder.close()
