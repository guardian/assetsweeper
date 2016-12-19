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
from gnmvidispine.vs_search import VSCollectionSearch
from gnmvidispine.vs_collection import VSCollection
from gnmvidispine.vs_item import VSItem,VSException
import os
from threading import Thread
from Queue import Queue, Empty

raven_client = raven.Client('https://bd4329a849e2434c9fde4b5c392b386d:64f6281adc75446d9d19d674c565cb51@sentry.multimedia.theguardian.com/18')
id_xplodr = re.compile(r'^(?P<site>\w{2})-(?P<numeric>\d+)')

path_map = None

logging.basicConfig(format='%(asctime)-15s - %(levelname)s - Thread %(thread)s - %(funcName)s: %(message)s',level=logging.ERROR)

logger = logging.getLogger(__name__)
logger.level = logging.DEBUG

THREADS = 3


class PortalItemNotFound(StandardError):
    """
    Raised if the item does not exist within the Portal index
    """
    pass


class InvalidLocation(StandardError):
    pass


class NoCollectionFound(StandardError):
    """
    Raised if no collection could be found for the given asset folder
    """
    pass


class InvalidProjectError(StandardError):
    """
    Raised if the path given does not appear to identify a pluto asset folder
    """
    pass


class ReattachThread(Thread):
    """
    Represents a thread which listens on a queue for item/collection pairs to link together.
    It links them, and also propagates media management flags from parent to child
    """
    def __init__(self,input_queue,*args,**kwargs):
        super(ReattachThread,self).__init__(*args,**kwargs)
        self._inq = input_queue
        self.logger = logging.getLogger("ReattachThread")
        self.logger.level=logging.DEBUG
        
    def reattach(self,itemid,collectionid):
        coll = VSCollection(host=options.vshost,port=options.vsport,user=options.vsuser,passwd=options.vspass)
        coll.name = collectionid
        coll.addToCollection(itemid,type="item")
        self.logger.info("Attached item {0} to {1}".format(itemid,collectionid))
        
        self.logger.info("Updating management metadata for {0}".format(itemid))
        completed = False
        held = False
        deletable = False
        sensitive = False
        deep_archive = False
        
        if coll.get('gnm_project_status') == 'Completed':
            completed = True
        elif coll.get('gnm_project_status') == 'Held':
            held = True
        if coll.get('gnm_storage_rule_deletable') == 'storage_rule_deletable':
            deletable = True
        if coll.get('gnm_storage_rule_sensitive') == 'storage_rule_sensitive':
            sensitive = True
        if coll.get('gnm_storage_ruke_deep_archive') == 'storage_rule_deep_archive':
            deep_archive = True
        item = VSItem(host=options.vshost,port=options.vsport,user=options.vsuser,passwd=options.vspass)
        item.name = itemid
        item.set_metadata({
            'gnm_storage_rule_projects_completed': ['storage_rule_projects_completed' if completed else ''],
            'gnm_storage_rule_projects_held'     : ['storage_rule_projects_held' if held else ''],
            'gnm_storage_rule_deletable'         : ['storage_rule_deletable' if deletable else ''],
            'gnm_storage_rule_sensitive'         : ['storage_rule_sensitive' if sensitive else ''],
            'gnm_storage_rule_deep_archive'      : ['storage_rule_deep_archive' if deep_archive else '']
        })
        logger.info("Updated metadata for item {0}".format(item.name))
        
    def run(self):
        while True:
            try:
                item = self._inq.get(block=True,timeout=500)
                if item is None: break
                self.reattach(item['itemid'],item['collectionid'])
                
            except Empty:
                self.logger.error("Input queue timed out, exiting.")
            except Exception:
                raven_client.captureException()
                raise
        self.logger.info("Reattach thread terminating")


class CollectionLookup(object):
    def __init__(self, startpath, host, port, user, password):
        self._startpath = startpath
        self._logger = logging.getLogger("CollectionLookup")
        self._logger.level = logging.DEBUG
        self._host = host
        self._port = port
        self._user = user
        self._pass = password
        
        self._keyword_splitter = re.compile(r'_')
    
    def listdirs(self):
        for workgroup in os.listdir(self._startpath):
            wgpath = os.path.join(self._startpath, workgroup)
            if workgroup == "." or workgroup == ".." or not os.path.isdir(
                    wgpath) or workgroup == "Branding" or workgroup == "Multimedia_News":
                continue
            self._logger.debug(workgroup)
            for commission in os.listdir(wgpath):
                commpath = os.path.join(wgpath, commission)
                if commission == "." or commission == ".." or not os.path.isdir(commpath):
                    continue
                self._logger.debug(workgroup + " -> " + commission)
                
                for user_project in os.listdir(commpath):
                    project_path = os.path.join(commpath, user_project)
                    if project_path == "." or project_path == ".." or not os.path.isdir(project_path):
                        continue
                    self._logger.debug(workgroup + " -> " + commission)
                    
                    yield {'project': user_project, 'commission': commission, 'workgroup': workgroup,
                           'path'   : project_path}
    
    def find_matching_entry(self, result, wanted_title):
        import re
        title_munger = re.compile(r'[^\w\d]+')
        # titles = map(lambda x: x.get('title'), result.results(shouldPopulate=True))
        
        for item in result.results(shouldPopulate=True):
            to_match = title_munger.sub('_', item.get('title'))
            self._logger.debug("matching {0} against {1}".format(to_match, wanted_title))
            if to_match == wanted_title:
                return item
        
        self._logger.debug("nothing matched")
        return None
    
    def find_in_vs(self, listdata):
        if not isinstance(listdata, dict): raise KeyError
        
        s = VSCollectionSearch(host=self._host, port=self._port, user=self._user, passwd=self._pass)
        
        projectparts = listdata['project'].split('_')
        if projectparts[0] == 'videoproducer1' or projectparts[0] == 'audioproducer1' or projectparts[0] == 'localhome':
            project_index = 1
        else:
            project_index = 2
            
        if(len(projectparts)<2):
            project_index = 1
            
        project_only = "_".join(projectparts[project_index:])
        self._logger.info("searching for {0}".format(project_only))
        
        search_title = self._keyword_splitter.sub(' ', project_only)
        
        if search_title == "":
            raise InvalidProjectError("Nothing to search for")
        
        s.addCriterion({'title': "\"{0}\"".format(search_title)})
        s.addCriterion({'gnm_type': 'Project'})
        try:
            result = s.execute()
        except VSException as e:
            self._logger.error("{0}. Searching for {1}".format(str(e),search_title))
            raise
        
        self._logger.info("Returned {0} hits for {1} on exact".format(result.totalItems, listdata['project']))
        
        if (result.totalItems == 1):
            for r in result.results(shouldPopulate=False):
                return r.name
        
        if result.totalItems == 0:
            s = VSCollectionSearch(host=self._host, port=self._port, user=self._user, passwd=self._pass)
            s.addCriterion({'title': "{0}".format(search_title)})
            s.addCriterion({'gnm_type': 'Project'})
            result = s.execute()
            self._logger.info("Returned {0} hits for {1} on inexact".format(result.totalItems, listdata['project']))
            if (result.totalItems == 1):
                for r in result.results(shouldPopulate=False):
                    return r.name

        # ok so we have more than one entry.
        wanted_title = "_".join(projectparts[project_index:])
        best_guess = self.find_matching_entry(result, wanted_title)
        if best_guess is not None:
            self._logger.debug(
                "Found {0} as best matching between {1} and {2}".format(best_guess.name, best_guess.get('title'),
                                                                        wanted_title))
            return best_guess.name
        
        interesting = ['title', 'gnm_asset_category', 'gnm_type']
        for collection in result.results(shouldPopulate=False):
            collection.populate(collection.name, specificFields=interesting)
            self._logger.info("Got {0}".format(collection.name))
            for f in interesting:
                self._logger.info("\t{0}: {1}".format(f, collection.get(f)))
        
        if result.totalItems < 4:
            for r in result.results(shouldPopulate=False):
                return r.name
        return None

local_cache = {}

def find_collection_id(workgroup, commission, user_project):
    cache_key = ":".join((workgroup, commission, user_project,))
    if cache_key in local_cache:
        return local_cache[cache_key]
    
    l = CollectionLookup("x", options.vshost, int(options.vsport), options.vsuser, options.vspass)
    result = l.find_in_vs({'project': user_project})
    local_cache[cache_key] = result
    return result

def attempt_reattach(reattach_queue,item_id,filepath):
    logger = logging.getLogger("attempt_reattach")
    logger.level = logging.DEBUG
    
    logger.info("attempt_reattach - {0} -> {1}".format(item_id,filepath))
    
    if not filepath.startswith('/srv/Multimedia2/Media Production/Assets'):
        raise InvalidLocation("{0} is not an asset folder".format(filepath))
    
    pathparts = filepath.split('/')
    try:
        workgroup = pathparts[5]
        commission = pathparts[6]
        user_project = pathparts[7]
    except IndexError:
        raise InvalidProjectError(filepath)
    
    logger.info("workgroup: {0} commission: {1} user_project: {2}".format(workgroup,commission,user_project))

    collection_id = find_collection_id(workgroup,commission,user_project)
    add_apostrophe = re.compile(r'_s')
    
    if collection_id is None:
        collection_id = find_collection_id(workgroup,commission,add_apostrophe.sub("'s",user_project))
        if collection_id is None:
            raise NoCollectionFound(filepath)
        
    logger.info("Got collection id {0}".format(collection_id))
    
    reattach_queue.put({'itemid': item_id, 'collectionid': collection_id})

        
def lookup_portal_item(esclient,item_id):
    """
    Returns an array of the collections that this item belongs to, according to Portal's ES index.
    :param esclient:
    :param item_id:
    :return:
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
            result = esclient.search(index='portal_1',doc_type='item',body=query)
            break
        except ReadTimeoutError as e:
            logger.warning(str(e))
            sleep(wait_time)
            wait_time *= 2
        except ConnectionTimeout as e:
            logger.warning(str(e))
            sleep(wait_time)
            wait_time *= 2
    hits = result['hits']['hits']
    if len(hits)==0: raise PortalItemNotFound(item_id)

    #pprint(hits[0]['_source'])
    if not 'f___collection_str' in hits[0]['_source']:
        return None
    return hits[0]['_source']['f___collection_str'] #this is an array

#START MAIN
reattach_threads = []
reattach_queue = Queue()
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

    esclient = elasticsearch.Elasticsearch(options.eshost)

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
    
    for n in range(0,THREADS):
        t = ReattachThread(reattach_queue)
        t.start()
        reattach_threads.append(t)

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
                attempt_reattach(reattach_queue,row[0],row[2])
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

    for t in reattach_threads:
        reattach_queue.put(None)
        
    logger.info("Waiting for threads to terminate")
    for t in reattach_threads:
        t.join()

    print "------------------------------------------------\n\n"
    
    pprint(totals)
    print "Invalid paths found:"
    pprint(invalid_paths)

    print "Asset folders which could not be resolved to projects:"
    pprint(not_found)
    
except Exception:
    raven_client.captureException()
    for t in reattach_threads:
        reattach_queue.put(None)
    
    logger.info("Waiting for threads to terminate")
    for t in reattach_threads:
        t.join()

    print "------------------------------------------------\n\n"

    pprint(totals)
    print "Invalid paths found:"
    pprint(invalid_paths)

    print "Asset folders which could not be resolved to projects:"
    pprint(not_found)
    
    raise
