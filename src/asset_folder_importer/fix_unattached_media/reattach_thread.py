from threading import Thread
from gnmvidispine.vs_collection import VSCollection
from gnmvidispine.vs_item import VSItem
import logging


class ReattachThread(Thread):
    """
    Represents a thread which listens on a queue for item/collection pairs to link together.
    It links them, and also propagates media management flags from parent to child
    """
    
    def __init__(self, input_queue, options=None, config=None, timeout=500, logger=None, should_raise=False, *args, **kwargs):
        super(ReattachThread, self).__init__(*args, **kwargs)
        self._inq = input_queue
        self.logger = logging.getLogger("ReattachThread") if logger==None else logger
        self.logger.level = logging.DEBUG
        self.options = options
        self.config = config
        self.timeout=timeout
        self.should_raise = should_raise
        
    def reattach(self, itemid, collectionid):
        coll = VSCollection(host=self.config.value('vs_host'), port=self.config.value('vs_port'),
                            user=self.config.value('vs_user'), passwd=self.config.value('vs_password'))
        coll.name = collectionid
        coll.addToCollection(itemid, type="item")
        self.logger.info("Attached item {0} to {1}".format(itemid, collectionid))
        
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
            
        item = VSItem(host=self.options.vshost, port=self.options.vsport, user=self.options.vsuser, passwd=self.options.vspass)
        item.name = itemid
        item.set_metadata({
            'gnm_storage_rule_projects_completed': ['storage_rule_projects_completed' if completed else ''],
            'gnm_storage_rule_projects_held'     : ['storage_rule_projects_held' if held else ''],
            'gnm_storage_rule_deletable'         : ['storage_rule_deletable' if deletable else ''],
            'gnm_storage_rule_sensitive'         : ['storage_rule_sensitive' if sensitive else ''],
            'gnm_storage_rule_deep_archive'      : ['storage_rule_deep_archive' if deep_archive else '']
        })
        self.logger.info("Updated metadata for item {0}".format(item.name))
    
    def run(self):
        from queue import Empty
        while True:
            try:
                (prio,item) = self._inq.get(block=True, timeout=self.timeout)
                if item is None: break
                self.reattach(item['itemid'], item['collectionid'])
            
            except Empty:
                self.logger.error("Input queue timed out, exiting.")
                break
            except Exception:
                if self.should_raise: raise
        self.logger.info("Reattach thread terminating")
