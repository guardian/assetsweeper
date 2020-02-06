import unittest
import os
import mock
import logging
import json
import gnmvidispine.vs_storage
from mock import MagicMock, patch

class TestImporterThread(unittest.TestCase):
    def __init__(self, *args,**kwargs):
        super(TestImporterThread, self).__init__(*args,**kwargs)
        self.mydir = os.path.dirname(__file__)
    
    class FakeConfig(object):
        def __init__(self, content):
            self._content = content
            
        def value(self, key, default=None, noraise=True):
            if not key in self._content:
                return ""
            return self._content[key]
        
    def test_potential_sidecar_filenames(self):
        from asset_folder_importer.asset_folder_vsingester.importer_thread import ImporterThread
        from asset_folder_importer.database import importer_db

        with mock.patch('psycopg2.connect') as mock_connect:
            db = importer_db("_test_Version_",username="circletest",password="testpass")

        i = ImporterThread(None,None,
                           self.FakeConfig({
                               'footage_providers_config': '{0}/../../footage_providers.yml'.format(self.mydir)
                           }),dbconn=db)
        
        result = [x for x in i.potentialSidecarFilenames("/path/to/myfile.mp4", isxdcam=False)]
        self.assertEqual(result,['/path/to/myfile.xml', '/path/to/myfile.xmp', '/path/to/myfile.meta', '/path/to/myfile.XML',
                                '/path/to/myfile.XMP','/path/to/myfile.mp4.xml','/path/to/myfile.mp4.xmp','/path/to/myfile.mp4.meta',
                                '/path/to/myfile.mp4.XML','/path/to/myfile.mp4.XMP'])
        
        result = [x for x in i.potentialSidecarFilenames("/path/to/myfile.mp4", isxdcam=True)]
        self.assertEqual(result,['/path/to/myfile.xml', '/path/to/myfile.xmp', '/path/to/myfile.meta',
                                '/path/to/myfile.XML', '/path/to/myfile.XMP', '/path/to/myfile.mp4.xml',
                                '/path/to/myfile.mp4.xmp', '/path/to/myfile.mp4.meta', '/path/to/myfile.mp4.XML',
                                '/path/to/myfile.mp4.XMP', '/path/to/myfileM01.xml', '/path/to/myfileM01.xmp',
                                '/path/to/myfileM01.meta', '/path/to/myfileM01.XML', '/path/to/myfileM01.XMP'])
        
    def test_import_tags(self):
        from asset_folder_importer.asset_folder_vsingester.importer_thread import ImporterThread
        from asset_folder_importer.database import importer_db
        
        with mock.patch('psycopg2.connect') as mock_connect:
            db = importer_db("_test_Version_",username="circletest",password="testpass")
            
        i = ImporterThread(None,None,
                           self.FakeConfig({
                               'footage_providers_config': '{0}/../../footage_providers.yml'.format(self.mydir)
                           }),dbconn=db)
        
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'video/mp4'}),['lowres'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'video/quicktime'}), ['lowres'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'application/mxf'}), ['lowres'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'model/vnd.mts'}),['lowres'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'image/jpeg'}), ['lowimage'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'image/tiff'}), ['lowimage'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'audio/aiff'}), ['lowaudio'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'audio/wav'}), ['lowaudio'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'application/xml'}),None)
    class FakeResponse(object):
        def __init__(self, content, status):
            self.content = content
            self.status = status
    
        def read(self):
            return self.content
        
    class FakeConnection(object):
        def __init__(self, content, status):
            self._content = content
            self._status = status
            self.jackpot = False
            
        def getresponse(self):
            if self.jackpot:
                return TestImporterThread.FakeResponse(json.dumps({'status': 'ok', 'project': 'KP-1234'}),200)
            else:
                return TestImporterThread.FakeResponse(json.dumps({'status': 'notfound'}), 404)
            
        def request(self, method, url, headers=None):
            import urllib.request, urllib.parse, urllib.error
            url = urllib.parse.unquote(url)
            if url.endswith('/path/to/my/assetfolder'):
                self.jackpot=True

        def connect(self):
            return mock.MagicMock()
        
    def test_find_invalid_projectid(self):
        from asset_folder_importer.asset_folder_vsingester.importer_thread import ImporterThread
        from asset_folder_importer.database import importer_db

        with mock.patch('psycopg2.connect') as mock_connect:
            db = importer_db("_test_Version_",username="circletest",password="testpass")

        with mock.patch('http.client.HTTPConnection') as mock_connection:
            logging.basicConfig(level=logging.ERROR)
            logger = logging.getLogger("tester")
            logger.setLevel(logging.ERROR)
            i = ImporterThread(None, None,
                               self.FakeConfig({
                                   'footage_providers_config': '{0}/../../footage_providers.yml'.format(self.mydir),
                                   'pluto_scheme': 'http'
                               }), dbconn=db)
            
            mock_connection.side_effect = lambda h,c: self.FakeConnection(json.dumps({'status': 'notfound'}),404)
            result = i.ask_pluto_for_projectid("/path/to/something/invalid/media.mxf")
            self.assertEqual(result,None)

    def test_find_valid_projectid(self):
        from asset_folder_importer.asset_folder_vsingester.importer_thread import ImporterThread
        from asset_folder_importer.database import importer_db
        
        with mock.patch('psycopg2.connect') as mock_connect:
            db = importer_db("_test_Version_", username="circletest", password="testpass")
        
        with mock.patch('http.client.HTTPConnection') as mock_connection:
            logging.basicConfig(level=logging.ERROR)
            logger = logging.getLogger("tester")
            logger.setLevel(logging.ERROR)
            i = ImporterThread(None, None,
                               self.FakeConfig({
                                   'footage_providers_config': '{0}/../../footage_providers.yml'.format(self.mydir),
                                   'pluto_scheme': 'http'
                               }), dbconn=db)
            
            mock_connection.side_effect = lambda h, c: self.FakeConnection(json.dumps({'status': 'notfound'}), 404)
            result = i.ask_pluto_for_projectid("/path/to/my/assetfolder/with/subdirectories/media.mxf")
            self.assertEqual(result,'KP-1234')

            result = i.ask_pluto_for_projectid("/path/to/my/assetfolder/media.mxf")
            self.assertEqual(result, 'KP-1234')

    def test_vs_inconsistency_error(self):
        from gnmvidispine.vs_storage import VSStorage, VSFile
        from gnmvidispine.vidispine_api import VSNotFound, HTTPError
        from asset_folder_importer.asset_folder_vsingester.importer_thread import ImporterThread
        from asset_folder_importer.asset_folder_vsingester.exceptions import VSFileInconsistencyError
        from asset_folder_importer.database import importer_db

        with mock.patch('psycopg2.connect') as mock_connect:
            db = importer_db("_test_Version_", username="circletest", password="testpass")

        mockstorage = mock.MagicMock(target=VSStorage)
        mockstorage.fileForPath = mock.MagicMock(side_effect=VSNotFound)
        mockstorage.create_file_entity = mock.MagicMock(side_effect=HTTPError(503,"GET","http://fake-url","Failed","I didn't expect the Spanish Inqusition",""))
        mockfile = mock.MagicMock(target=VSFile)

        with mock.patch('http.client.HTTPConnection') as mock_connection:
            logging.basicConfig(level=logging.ERROR)
            logger = logging.getLogger("tester")
            logger.setLevel(logging.ERROR)
            i = ImporterThread(None, None,
                               self.FakeConfig({
                                   'footage_providers_config': '{0}/../../footage_providers.yml'.format(self.mydir)
                               }), dbconn=db)

            i.st = mockstorage
            with self.assertRaises(VSFileInconsistencyError) as raised_error:
                i.attempt_file_import(mockfile,"path/to/testfile","/rootpath")
            self.assertEqual(str(raised_error.exception),"path/to/testfile")

    class StalledJob(object):
        """
        Simulate a job that stalls, i.e. always returns that it is "started" and progressing
        """
        def __init__(self):
            self.abort = mock.MagicMock()

        def finished(self):
            return False

        def status(self):
            return "STARTED"

        def update(self,noraise=True):
            pass

    def test_timeout_retries(self):
        from asset_folder_importer.asset_folder_vsingester.importer_thread import ImporterThread, ImportStalled
        from asset_folder_importer.database import importer_db
        from time import time

        with mock.patch('psycopg2.connect') as mock_connect:
            db = importer_db("_test_Version_", username="circletest", password="testpass")
            
        with mock.patch('http.client.HTTPConnection') as mock_connection:
            fake_job = self.StalledJob()

            mock_vsfile = mock.MagicMock(target=gnmvidispine.vs_storage.VSFile)
            mock_vsfile.importToItem = mock.MagicMock(return_value=fake_job)

            i=ImporterThread(None,None,self.FakeConfig({
                'footage_providers_config': '{0}/../../footage_providers.yml'.format(self.mydir)
            }),dbconn=db,import_timeout=4)  #set importer timeout to 4s
            start_time = time()
            with self.assertRaises(ImportStalled):
                i.do_real_import(mock_vsfile,"/path/to/filename","fake_xml",['tagone'])
            self.assertGreaterEqual(time()-start_time,4)    #should have taken at least 4 seconds
            mock_vsfile.importToItem.assert_called_once_with("fake_xml",tags=['tagone'],priority="LOW",jobMetadata={'gnm_app': 'vsingester'})
            fake_job.abort.assert_called_once_with()

    xmlns = "{http://xml.vidispine.com/schema/vidispine}"

    def _safe_get_xmlnode(self, fieldnode):
        node = fieldnode.find('{0}name'.format(self.xmlns))
        return node.text

    def _find_xml_field(self, parsed_xml, fieldname):
        node_list = [node for node in parsed_xml.findall("{0}timespan/{0}field".format(self.xmlns)) if self._safe_get_xmlnode(node)==fieldname]
        return node_list

    def _field_node_values(self, fieldnode):
        return [valuenode.text for valuenode in fieldnode.findall("{0}value".format(self.xmlns))]

    def test_md_render(self):
        """
        render_xml should provide an XML MetadataDocument for Vidispine
        :return:
        """
        from asset_folder_importer.asset_folder_vsingester.importer_thread import ImporterThread
        from gnmvidispine.vs_storage import VSFile
        from datetime import datetime
        from asset_folder_importer.database import importer_db
        import xml.etree.cElementTree as ET

        mock_db = MagicMock(target=importer_db)
        mock_fileref = MagicMock(target=VSFile)
        mock_fileref.mtime = datetime(2018,1,4,15,32,00)
        mock_fileref.ctime = datetime(2018,1,4,15,30,00)

        i=ImporterThread(None,None,self.FakeConfig({
            'footage_providers_config': '{0}/../../footage_providers.yml'.format(self.mydir)
        }),dbconn=mock_db)

        result = i.render_xml(mock_fileref,None,None,None,None,None,"/path/to/my/test/file")

        parsed_xml = ET.fromstring(result)
        category_node = self._find_xml_field(parsed_xml,"gnm_asset_category")
        self.assertEqual(self._field_node_values(category_node[0]),["Rushes"])

    def test_md_render_altcat(self):
        """
        render_xml should honour requests for alternative categories
        :return:
        """
        from asset_folder_importer.asset_folder_vsingester.importer_thread import ImporterThread
        from gnmvidispine.vs_storage import VSFile
        from datetime import datetime
        from asset_folder_importer.database import importer_db
        import xml.etree.cElementTree as ET

        mock_db = MagicMock(target=importer_db)
        mock_fileref = MagicMock(target=VSFile)
        mock_fileref.mtime = datetime(2018,0o1,0o4,15,32,00)
        mock_fileref.ctime = datetime(2018,0o1,0o4,15,30,00)

        i=ImporterThread(None,None,self.FakeConfig({
            'footage_providers_config': '{0}/../../footage_providers.yml'.format(self.mydir)
        }),dbconn=mock_db)

        result = i.render_xml(mock_fileref,None,None,None,None,None,"/path/to/my/test/file",media_category="Branding")

        parsed_xml = ET.fromstring(result)
        category_node = self._find_xml_field(parsed_xml,"gnm_asset_category")
        self.assertEqual(self._field_node_values(category_node[0]),["Branding"])

    def test_attempt_file_import_brandingcat(self):
        """
        When importing something from a branding folder, attempt_file_import should ensure that the file is, in fact, tagged as branding
        :return:
        """
        from asset_folder_importer.asset_folder_vsingester.importer_thread import ImporterThread
        from asset_folder_importer.database import importer_db
        from gnmvidispine.vs_storage import VSStorage, VSFile
        from datetime import datetime
        from os import makedirs
        import dateutil.parser

        mock_db = MagicMock(target=importer_db)
        mock_db.get_prelude_data = MagicMock(return_value=None)

        mock_file = MagicMock(target=VSFile)
        mock_file.importToItem = MagicMock()
        mock_file.memberOfItem = None

        mock_storage = MagicMock(target=VSStorage)
        mock_storage.fileForPath = MagicMock(return_value=mock_file)

        if not os.path.exists("/tmp/Multimedia2/Media Production/Assets/Branding/Some Branding Kit/yadayada/"):
            makedirs("/tmp/Multimedia2/Media Production/Assets/Branding/Some Branding Kit/yadayada/")
        with open("/tmp/Multimedia2/Media Production/Assets/Branding/Some Branding Kit/yadayada/fancy title.aep","w") as f:
            f.write("test file\n")

        mock_fileref = {
            'id': 376423,
            'filepath': "/tmp/Multimedia2/Media Production/Assets/Branding/Some Branding Kit/yadayada",
            'filename': "fancy title.aep",
            'mtime': dateutil.parser.parse("2017-04-28 09:18:53+01"),
            'ctime': dateutil.parser.parse("2017-09-06 20:56:29.96+01"),
            'atime': dateutil.parser.parse("2017-07-20 11:56:38.12+01"),
            'imported_id': None,
            'imported_at': None,
            'last_seen': datetime.now(),
            'size': 12344567789,
            'owner': 803,
            'gid': 3476423,
            'prelude_ref': None,
            'ignore': False,
            'mime_type': 'application/x-aftereffects-project',
            'asset_folder': None
        }

        i=ImporterThread(None,None,self.FakeConfig({
            'footage_providers_config': '{0}/../../footage_providers.yml'.format(self.mydir)
        }),dbconn=mock_db)
        i.st = mock_storage
        i.ask_pluto_for_projectid = MagicMock(return_value=None) #there will be no record of this as an asset folder

        i.attempt_file_import(mock_fileref, mock_fileref['filepath'], "/srv/Multimedia2/Media Production/Assets")
        mock_db.get_prelude_data.assert_called_once_with(None) #not ingested through prelude
        mock_file.importToItem.assert_called_with(b'<?xml version="1.0" encoding="UTF-8"?>\n<!-- need Created By, Original Filename, File Last Modified, Deep Archive (if applicable from project),\nOriginal Owner -->\n<MetadataDocument xmlns="http://xml.vidispine.com/schema/vidispine">\n  <group>Asset</group>\n  <timespan start="-INF" end="+INF">\n    <field>\n      <name>title</name>\n      <value>fancy title.aep (yadayada)</value>\n    </field>\n    <field>\n      <name>gnm_asset_category</name>\n      <value>Branding</value>\n    </field>\n    <field>\n      <name>gnm_asset_status</name>\n      <value>Ready for Editing</value>\n    </field>\n    <field>\n      <name>gnm_asset_owner</name>\n      <value>803</value>\n    </field>\n    <field>\n      <name>gnm_asset_filename</name>\n      <value>/tmp/Multimedia2/Media Production/Assets/Branding/Some Branding Kit/yadayada/fancy title.aep</value>\n    </field>\n    <field>\n      <name>gnm_asset_file_last_modified</name>\n      <value>2017-04-28T09:18:53Z</value>\n    </field>\n    <field>\n      <name>gnm_rushes_general_original_owner</name>\n      <value>803</value>\n    </field>\n    <field>\n      <name>gnm_asset_createdby</name>\n      <value>803</value>\n    </field>\n    <!--date from fileref-->\n    <field>\n      <name>gnm_asset_file_created</name>\n      <value>2017-09-06T20:56:29Z</value>\n    </field>\n  </timespan>\n</MetadataDocument>\n', jobMetadata={'gnm_app': 'vsingester'}, priority='LOW', tags=None)
