from __future__ import absolute_import
import unittest2
from elasticsearch import Elasticsearch
from urllib3.exceptions import ReadTimeoutError
from elasticsearch.exceptions import ConnectionTimeout
from mock import MagicMock, patch
from time import time


class TestProjectSizeEstimatorFunctions(unittest2.TestCase):
    def test_do_search(self):
        """
        do_search function should call Elasticsearch and return the results
        :return:
        """
        from asset_folder_importer.config import configfile
        from asset_folder_importer.project_size_estimator.functions import do_search

        mock_config = MagicMock(target=configfile)
        mock_elastic_client = MagicMock(target=Elasticsearch)

        mock_result = {'hits': {'hits': [{'_source':{'field_one': 'value', 'filed_two': 'value2'}}]}}
        mock_elastic_client.search = MagicMock(return_value={'hits': {'hits': [{'_source':{'field_one': 'value', 'filed_two': 'value2'}}]}})

        result = do_search(esclient=mock_elastic_client,cfg=mock_config,query={'mock_query': {}})

        self.assertEqual(mock_result, result)
        mock_elastic_client.search.assert_called_once_with(index=mock_config.value('portal_elastic_index'), doc_type='item', body={'mock_query': {}})

    def test_do_search_readtimeout(self):
        """
        do_search should exponentially backoff it it receives read timeouts
        :return:
        """
        from asset_folder_importer.config import configfile
        from asset_folder_importer.project_size_estimator.functions import do_search

        mock_config = MagicMock(target=configfile)
        mock_elastic_client = MagicMock(target=Elasticsearch)
        pool = MagicMock()
        mock_elastic_client.search = MagicMock(side_effect=ReadTimeoutError(pool,"http://test","fake message"))

        start_time = time()
        with self.assertRaises(ReadTimeoutError):
            result = do_search(esclient=mock_elastic_client,cfg=mock_config,query={'mock_query': {}},wait_time=1,retries=3)
        end_time = time()
        self.assertGreater(end_time-start_time,7)

        self.assertEqual(mock_elastic_client.search.call_count,4)
        mock_elastic_client.search.assert_called_with(index=mock_config.value('portal_elastic_index'), doc_type='item', body={'mock_query': {}})

    def test_do_search_connectiontimeout(self):
        """
        do_search should exponentially backoff it it receives connection timeouts
        :return:
        """
        from asset_folder_importer.config import configfile
        from asset_folder_importer.project_size_estimator.functions import do_search

        mock_config = MagicMock(target=configfile)
        mock_elastic_client = MagicMock(target=Elasticsearch)
        pool = MagicMock()
        mock_elastic_client.search = MagicMock(side_effect=ConnectionTimeout("a","b","c"))

        start_time = time()
        with self.assertRaises(ConnectionTimeout):
            result = do_search(esclient=mock_elastic_client,cfg=mock_config,query={'mock_query': {}},wait_time=1,retries=3)
        end_time = time()
        self.assertGreater(end_time-start_time,7)

        self.assertEqual(mock_elastic_client.search.call_count,4)
        mock_elastic_client.search.assert_called_with(index=mock_config.value('portal_elastic_index'), doc_type='item', body={'mock_query': {}})

    def test_lookup_validates_vsid(self):
        """
        lookup_portal_item should raise a ValueError if passed an invalid vidispine ID
        :return:
        """
        from asset_folder_importer.project_size_estimator.functions import lookup_portal_item

        with self.assertRaises(ValueError):
            lookup_portal_item(None, None, "12897423")
        with self.assertRaises(ValueError):
            lookup_portal_item(None, None, "VX-3214D")
        with self.assertRaises(ValueError):
            lookup_portal_item(None, None, "VX-3214; delete from t_item")

    def test_lookup_raises_notfound(self):
        """
        lookup_portal_item should raise a PortalItemNotFound exception if it gets an empty result set from ES
        :return:
        """
        from asset_folder_importer.config import configfile
        from asset_folder_importer.project_size_estimator.functions import lookup_portal_item, PortalItemNotFound

        mock_config = MagicMock(tatget=configfile)
        fake_itemid="VX-12345"
        fake_query={
            'query': {
                'filtered': {
                    'filter': {
                        'term': {
                            'vidispine_id_str_ex': fake_itemid
                        }
                    }
                }
            }
        }
        fake_result = {
            'hits': {
                'hits': []
            }
        }

        with patch('asset_folder_importer.project_size_estimator.functions.do_search', return_value=fake_result) as mock_do_search:
            with self.assertRaises(PortalItemNotFound):
                result = lookup_portal_item(None,mock_config,fake_itemid)
            mock_do_search.assert_called_once_with(None, mock_config, fake_query)

    def test_lookup(self):
        """
        lookup_portal_item should return a list of collection IDs from the index
        :return:
        """
        from asset_folder_importer.config import configfile
        from asset_folder_importer.project_size_estimator.functions import lookup_portal_item, PortalItemNotFound

        mock_config = MagicMock(tatget=configfile)
        fake_itemid="VX-12345"
        fake_query={
            'query': {
                'filtered': {
                    'filter': {
                        'term': {
                            'vidispine_id_str_ex': fake_itemid
                        }
                    }
                }
            }
        }
        fake_result = {
            'hits': {
                'hits': [
                    {
                        '_source': {
                            'f___collection_str': ["VX-1","VX-27","VX-472"]
                        }
                    }
                ]
            }
        }

        with patch('asset_folder_importer.project_size_estimator.functions.do_search', return_value=fake_result) as mock_do_search:
            result = lookup_portal_item(None,mock_config,fake_itemid)
            mock_do_search.assert_called_once_with(None, mock_config, fake_query)
            self.assertEqual(result, ["VX-1","VX-27","VX-472"])

    def test_lookup_nocollections(self):
        """
        lookup_portal_item should return None if there are no collections associated with the item
        :return:
        """
        from asset_folder_importer.config import configfile
        from asset_folder_importer.project_size_estimator.functions import lookup_portal_item, PortalItemNotFound

        mock_config = MagicMock(tatget=configfile)
        fake_itemid="VX-12345"
        fake_query={
            'query': {
                'filtered': {
                    'filter': {
                        'term': {
                            'vidispine_id_str_ex': fake_itemid
                        }
                    }
                }
            }
        }
        fake_result = {
            'hits': {
                'hits': [
                    {
                        '_source': {
                            'some_field': 'some_value'
                        }
                    }
                ]
            }
        }

        with patch('asset_folder_importer.project_size_estimator.functions.do_search', return_value=fake_result) as mock_do_search:
            result = lookup_portal_item(None,mock_config,fake_itemid)
            mock_do_search.assert_called_once_with(None, mock_config, fake_query)
            self.assertIsNone(result)

    def test_process_row_notimported(self):
        """
        if an entry has no item ID then it should be treated as unimported
        :return:
        """
        from asset_folder_importer.project_size_estimator.functions import process_row
        from asset_folder_importer.config import configfile

        totals = {
            'unattached': 0.0,
            'unimported': 0.0
        }

        esclient = MagicMock(target=Elasticsearch)
        cfg = MagicMock(target=configfile)

        fake_row = [
            None,
            1073741824
        ]
        with patch('asset_folder_importer.project_size_estimator.functions.lookup_portal_item', return_value=[]) as mock_lookup:
            result = process_row(esclient, cfg, fake_row, totals)
            self.assertDictEqual(result,{'unattached': 0.0, 'unimported': 1024.0})
            mock_lookup.assert_not_called()

    def test_process_row_notattached(self):
        """
        if the lookup can't find the item then treat it as not attached
        :return:
        """
        from asset_folder_importer.project_size_estimator.functions import process_row, PortalItemNotFound
        from asset_folder_importer.config import configfile

        totals = {
            'unattached': 0.0,
            'unimported': 0.0
        }

        esclient = MagicMock(target=Elasticsearch)
        cfg = MagicMock(target=configfile)

        fake_row = [
            "VX-1234456",
            1073741824
        ]
        with patch('asset_folder_importer.project_size_estimator.functions.lookup_portal_item', side_effect=PortalItemNotFound) as mock_lookup:
            result = process_row(esclient, cfg, fake_row, totals)
            self.assertDictEqual(result,{'unattached': 1024.0, 'unimported': 0.0})
            mock_lookup.assert_called_once_with(esclient, cfg, "VX-1234456")

    def test_process_row_attached(self):
        """
        process_row should add the size of the file to each collection that said file is attached to
        :return:
        """
        from asset_folder_importer.project_size_estimator.functions import process_row, PortalItemNotFound
        from asset_folder_importer.config import configfile

        totals = {
            'unattached': 0.0,
            'unimported': 0.0
        }

        esclient = MagicMock(target=Elasticsearch)
        cfg = MagicMock(target=configfile)

        fake_row = [
            "VX-123456",
            1073741824
        ]
        with patch('asset_folder_importer.project_size_estimator.functions.lookup_portal_item', return_value=["VX-1","VX-7","VX-19"]) as mock_lookup:
            result = process_row(esclient, cfg, fake_row, totals)
            self.assertDictEqual(result,{'unattached': 0.0, 'unimported': 0.0, 'VX-1': 1024.0, 'VX-7': 1024.0, 'VX-19': 1024.0})
            mock_lookup.assert_called_once_with(esclient, cfg, "VX-123456")

    def test_process_row_valueerror(self):
        """
        process_row should be able to handle an invalid item ID
        :return:
        """
        from asset_folder_importer.project_size_estimator.functions import process_row, PortalItemNotFound
        from asset_folder_importer.config import configfile

        totals = {
            'unattached': 0.0,
            'unimported': 0.0
        }

        esclient = MagicMock(target=Elasticsearch)
        cfg = MagicMock(target=configfile)

        fake_row = [
            "456",
            1073741824
        ]
        with patch('asset_folder_importer.project_size_estimator.functions.lookup_portal_item', side_effect=ValueError) as mock_lookup:
            result = process_row(esclient, cfg, fake_row, totals)
            self.assertDictEqual(result,{'unattached': 0.0, 'unimported': 0.0})
            mock_lookup.assert_called_once_with(esclient, cfg, "456")
