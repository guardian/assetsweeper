from . import BaseProvider,LookupError
import httplib2
import json
import re
import os
from pprint import pprint, pformat
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://api.gettyimages.com:443/v3/videos/"
interesting_fields = [
    'artist',
    'caption',
    'clip_length',
    'collection_name',
    'title',
    'license_model',
    'id',
    'source',
    'copyright',
    'era',
    'keywords',
    'product_types',
    'date_created'
]


class Provider(BaseProvider):
    retry_time = 10
    max_retries = 50

    api_key = "INSERT_HERE"

    def lookup(self,filepath,filename,match_data):
        import time
        h = httplib2.Http()

        parts = re.match(r'^([^\.]+)', filename)
        if parts is not None:
            getty_id = parts.group(1)
        else:
            raise ValueError("Could not get an ID from filename {0}".format(filename))

        retries = 0
        while True:
            getty_id = re.sub(r'_[^_]*$','',getty_id)
            url_string = BASE_URL + "{0}?fields={1}".format(getty_id, "%2C".join(interesting_fields))
            resp, content = h.request(url_string,headers={'Api-Key': self.api_key, 'Accept': 'application/json'})
            #print resp

            code = int(resp['status'])

            data = json.loads(content)
            #pprint(data)

            if code == 403:
                if 'message' in data and data['message'] == 'Account Over Queries Per Second Limit':
                    if retries>=self.max_retries:
                        raise LookupError("Still can't get data after {0} attempts, giving up.".format(retries))

                    logger.warning("Getty responded Account Over Rate Limit, waiting and trying again")
                    retries+=1
                    time.sleep(self.retry_time)
                    continue

            if code < 200 or code > 299:
                raise LookupError("Unable to request data from Getty: {0} - {1}".format(code, content))
            break

        #rtn = { 'grouped': {}, 'ungrouped': {}}
        rtn = {}

        rtn['title'] = data['title']
        rtn['gnm_asset_category'] = "Getty Stock"
        rtn['gnm_asset_description'] = data['caption']
        rtn['gnm_mm_provider'] = data['artist']
        rtn['created'] = data['date_created']
        rtn['gnm_asset_user_keywords'] = []
        #No idea WHY we need to do it like this - but we do because x['text'] raises an error
        for x in data['keywords']:
            for k, v in x.items():
                if k!='text':
                    continue
                print "\t{0}=>{1}".format(k,v)
                if re.match(r'^\s*$',v):
                    break
                rtn['gnm_asset_user_keywords'].append(v)

        rtn['CopyrightandLegalInformation'] = {
            'gnm_copyright_legal_original_provider': data['artist'],
            'gnm_copyright_legal_usage_status': data['license_model'],
            'gnm_copyright_legal_original_source': data['source']
        }
        rtn['RightsProfileInformation'] = {
            'ContributorType': {
                'gnm_contributor_type_id': 48,
                'gnm_contributor_type_name': 'Footage Provider'
            },
            'Contributor': {
                'gnm_contributor_name': 'Getty Images International',
                'gnm_contributor_id': 'GNL000565'
            }
        }
        return rtn