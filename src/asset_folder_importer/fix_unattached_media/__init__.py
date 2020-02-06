from urllib3.exceptions import ReadTimeoutError
from elasticsearch.exceptions import ConnectionTimeout
from .collection_lookup import CollectionLookup
from gnmvidispine.vs_item import VSItem,VSNotFound
from .exceptions import *
import logging
import re
from time import sleep

logger = logging.getLogger(__name__)
logger.level=logging.DEBUG

id_xplodr = re.compile(r'^(?P<site>\w{2})-(?P<numeric>\d+)')


def lookup_portal_item(esclient, index_name, item_id):
    """
    Returns an array of the collections that this item belongs to, according to Portal's ES index.
    :param esclient: Elastic search client object to use
    :param index_name: Name of the index to search within
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
            result = esclient.search(index=index_name, doc_type='item', body=query)
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


def lookup_vidispine_item(credentials, item_id):
    """
    Look up the containing collection in Vidispine, if the search in the Portal index fails
    :param credentials: dictionary of Vidipsine credentials
    :param item_id: item ID to look up
    :return: String of the collection ID, or None if no collection was found.
    """
    i = VSItem(host=credentials['host'],port=int(credentials['port']),user=credentials['user'],
               passwd=credentials['password'])
    
    try:
        i.populate(item_id, specificFields=['title'])
    except VSNotFound:
        logger.error("Item {0} was not found in Vidispine".format(item_id))
        return None
    containers = i.get('__collection',allowArray=True)
    if not isinstance(containers,list):
        return [containers]
    else:
        return containers