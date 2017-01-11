from urllib3.exceptions import ReadTimeoutError
from elasticsearch.exceptions import ConnectionTimeout
from collection_lookup import CollectionLookup
from exceptions import *
import logging
import re

id_xplodr = re.compile(r'^(?P<site>\w{2})-(?P<numeric>\d+)')
local_cache = {}

def find_collection_id(workgroup, commission, user_project, options):
    cache_key = ":".join((workgroup, commission, user_project,))
    if cache_key in local_cache:
        return local_cache[cache_key]
    
    l = CollectionLookup("x", options.vshost, int(options.vsport), options.vsuser, options.vspass)
    result = l.find_in_vs({'project': user_project})
    local_cache[cache_key] = result
    return result


def attempt_reattach(pool, item_id, filepath):
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
    
    collection_id = find_collection_id(workgroup, commission, user_project)
    add_apostrophe = re.compile(r'_s')
    
    if collection_id is None:
        collection_id = find_collection_id(workgroup, commission, add_apostrophe.sub("'s", user_project))
        if collection_id is None:
            raise NoCollectionFound(filepath)
    
    logger.info("Got collection id {0}".format(collection_id))
    
    pool.put_queue({'itemid': item_id, 'collectionid': collection_id}, priority=10)


def lookup_portal_item(esclient, item_id):
    """
    Returns an array of the collections that this item belongs to, according to Portal's ES index.
    :param esclient: Elastic search client object to use
    :param item_id: item ID to look for
    :return: array of collection names that this belongs to. Blank array if it does not belong.
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
            result = esclient.search(index='portal_1', doc_type='item', body=query)
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
    if len(hits) == 0: raise PortalItemNotFound(item_id)

    # pprint(hits[0]['_source'])
    if not 'f___collection_str' in hits[0]['_source']:
        return None
    return hits[0]['_source']['f___collection_str']  # this is an array