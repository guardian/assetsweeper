from __future__ import absolute_import
import unittest
import os
import threading
import mock
import logging
import httplib
import json


class TestImporterThread(unittest.TestCase):
    def test_potential_sidecar_filenames(self):
        from asset_folder_importer.asset_folder_vsingester.importer_thread import ImporterThread
        
        i = ImporterThread(None,"",{})
        
        result = map(lambda x: x, i.potentialSidecarFilenames("/path/to/myfile", isxdcam=False))
        self.assertEqual(result,[])
        
        result = map(lambda x: x, i.potentialSidecarFilenames("/path/to/myfile", isxdcam=True))
        self.assertEqual(result,[])
        
    def test_import_tags(self):
        from asset_folder_importer.asset_folder_vsingester.importer_thread import ImporterThread
    
        i = ImporterThread(None, "", {})
        
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'video/mp4'}),['lowres'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'video/quicktime'}), ['lowres'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'application/mxf'}), ['lowres'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'model/vnd.mts'}),['lowres'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'image/jpeg'}), ['lowimage'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'image/tiff'}), ['lowimage'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'audio/aiff'}), ['lowaudio'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'image/wav'}), ['lowaudio'])
