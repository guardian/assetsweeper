from threading import Thread
from gnmvidispine.vs_collection import VSCollection
from gnmvidispine.vs_item import VSItem
from asset_folder_importer.fix_unattached_media.collection_lookup import CollectionLookup
from asset_folder_importer.fix_unattached_media.direct_pluto_lookup import DirectPlutoLookup
import logging
import re
from exceptions import *


class PreReattachThread(Thread):
    def __init__(self, input_queue, output_queue=None, options=None, config=None, raven_client=None, timeout=500,
                 logger=None, pluto_lookup=None, should_raise=False,
                 *args, **kwargs):
        super(PreReattachThread, self).__init__(*args, **kwargs)
        self._inq = input_queue
        self._outq = output_queue
        self.logger = logging.getLogger("PreReattachThread") if logger == None else logger
        self.logger.level = logging.DEBUG
        self.options = options
        self.config = config
        self.raven_client = raven_client
        self.timeout = timeout
        self.should_raise = should_raise
        self.local_cache = {}
        self.invalid_paths = []
        self.not_found = []
        self.pluto_lookup = DirectPlutoLookup(host=self.config.value('pluto_host'), port=self.config.value('pluto_port'),
                            user=self.config.value('vs_user'), password=self.config.value('vs_password')) if pluto_lookup is None else pluto_lookup
        self.totals = {
            'unattached': 0
        }
        
    def find_collection_id(self, workgroup, commission, user_project):
        cache_key = ":".join((workgroup, commission, user_project,))
        if cache_key in self.local_cache:
            return self.local_cache[cache_key]
    
        l = CollectionLookup("x", self.config.value('vs_host'), self.config.value('vs_port'),
                            self.config.value('vs_user'), self.config.value('vs_password'))
        result = l.find_in_vs({'project': user_project})
        self.local_cache[cache_key] = result
        return result
    
    def bruteforce_lookup(self, item_id, filepath):
        logger = logging.getLogger("attempt_reattach")
        logger.level = logging.DEBUG
    
        logger.info("attempt_reattach - {0} -> {1}".format(item_id, filepath))
    
        if not filepath.startswith('/srv/Multimedia2/Media Production/Assets'):
            raise InvalidLocation("{0} is not an asset folder".format(filepath))
    
        pathparts = filepath.split('/')
        try:
            workgroup = pathparts[5]
            commission = pathparts[6]
            user_project = pathparts[7]
        except IndexError:
            raise InvalidProjectError(filepath)
    
        logger.info("workgroup: {0} commission: {1} user_project: {2}".format(workgroup, commission, user_project))
    
        collection_id = self.find_collection_id(workgroup, commission, user_project)
        add_apostrophe = re.compile(r'_s')
    
        if collection_id is None:
            collection_id = self.find_collection_id(workgroup, commission, add_apostrophe.sub("'s", user_project))
            if collection_id is None:
                raise NoCollectionFound(filepath)
    
        return collection_id
    
    def process(self, item_id, filepath):
        self.logger.info("attempt_reattach - {0} -> {1}".format(item_id, filepath))
    
        if not filepath.startswith('/srv/Multimedia2/Media Production/Assets'):
            raise InvalidLocation("{0} is not an asset folder".format(filepath))
    
        pathparts = filepath.split('/')
        
        collection_id = self.pluto_lookup.lookup("/".join(pathparts[0:8]))
        
        if collection_id is None:
            self.logger.warning("No record found for {0} in Pluto".format("/".join(pathparts[0:8])))
            collection_id = self.bruteforce_lookup(item_id, filepath)
            
        self.logger.info("Got collection id {0}".format(collection_id))
        self._outq.put({'itemid': item_id, 'collectionid': collection_id}, priority=10)
    
    def run(self):
        from Queue import Empty
        while True:
            try:
                (prio, item) = self._inq.get(block=True, timeout=self.timeout)
                if item is None: break
                self.process(item['item_id'], item['filepath'])
            except InvalidProjectError as e:
                self.logger.error(str(e))
                self.logger.error("Attempting reattach of {0}".format(item['filepath']))
                if not item['filepath'] in self.invalid_paths:
                    self.invalid_paths.append(item['filepath'])
    
                self.totals['unattached'] += float(item['size']) / (1024.0 ** 2)
            except NoCollectionFound as e:
                self.logger.error("Unable to find a collection for {0}".format(item['filepath']))
                if not item['filepath'] in self.not_found:
                    self.not_found.append(item['filepath'])
            except Empty:
                self.logger.error("Input queue timed out, exiting.")
                break
            except Exception:
                if self.raven_client is not None: self.raven_client.captureException()
                if self.should_raise: raise
        self.logger.info("Pre-reattach thread terminating")
