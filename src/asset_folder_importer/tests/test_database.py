__author__ = 'dave'

import unittest
import logging
import os
from asset_folder_importer.database import importer_db

class TestDatabase(unittest.TestCase):
    dbhost = os.environ['DB_HOST'] if 'DB_HOST' in os.environ else 'localhost'
    dbport = os.environ['DB_PORT'] if 'DB_PORT' in os.environ else "5432"
    dbuser = os.environ['DB_USER'] if 'DB_USER' in os.environ else 'assetimporter'
    dbpass = os.environ['DB_PASS'] if 'DB_PASS' in os.environ else 'assetimporter'
    dbname = os.environ['DB_NAME'] if 'DB_NAME' in os.environ else 'assetimporter'
    
    def __init__(self,*args,**kwargs):
        super(TestDatabase,self).__init__(*args,**kwargs)
        self._cached_id = None

    def test__has_column(self):
        __version__ = 'database_test'

        db = importer_db(__version__,hostname=self.dbhost,port=self.dbport,username=self.dbuser,
                         password=self.dbpass,dbname=self.dbname)

        self.assertEqual(db._has_column('system','id'),True)
        self.assertEqual(db._has_column('files','filepath'),True)
        self.assertEqual(db._has_column('files','hamster'),False)

    def test__has_table(self):
        __version__ = 'database_test'

        db = importer_db(__version__, hostname=self.dbhost, port=self.dbport, username=self.dbuser,
                         password=self.dbpass, dbname=self.dbname)

        self.assertEqual(db._has_table('system'),True)
        self.assertEqual(db._has_table('files'),True)
        self.assertEqual(db._has_table('hamster'),False)
        
    def test_mark_as_deleted(self):
        __version__ = 'database_test'
        from uuid import uuid4
        db = importer_db(__version__,hostname=self.dbhost,port=self.dbport,username=self.dbuser,
                         password=self.dbpass,dbname=self.dbname)
        statinfo = os.stat(__file__)    #fake stat info by statting THIS file
        
        db.check_schema_20()
        db.check_schema_21()
        db.check_schema_22()
        
        fileid = db.upsert_file_record("/path/to/test/assets/folder/media","filename.mxf",statinfo,"video/x-mxf")
        projid = db.upsert_edit_project("/path/to/projects","testproject.prproj",uuid4().get_hex(),"1.0")
        db.link_file_to_edit_project(fileid,projid)
        
        self.assertEqual(db.fileId("/path/to/test/assets/folder/media/filename.mxf"),fileid)
        
        db.mark_id_as_deleted(fileid)
        
        self.assertEqual(db.fileId("/path/to/test/assets/folder/media/filename.mxf"),None)