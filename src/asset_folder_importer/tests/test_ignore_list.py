from __future__ import absolute_import
import unittest


class TestIgnoreList(unittest.TestCase):
    def test_should_match(self):
        from asset_folder_importer.asset_folder_sweeper.ignore_list import IgnoreList

        test_list = IgnoreList()

        self.assertTrue(test_list.should_ignore("/path/to/some/Adobe Premiere Pro Preview Files/subpath","yadayadayada.xxx"))
        self.assertTrue(test_list.should_ignore("/path/to/some/System Volume Information","yadayadayada.xxx"))
        self.assertTrue(test_list.should_ignore("/path/to/some/assets","somethingsomething_synctemp.aif"))
        self.assertTrue(test_list.should_ignore("/path/to/some/assets","Mic_01.pk"))
        self.assertTrue(test_list.should_ignore("/path/to/some/assets","."))
        self.assertTrue(test_list.should_ignore("/path/to/some/assets",".hiddenfile"))
        self.assertTrue(test_list.should_ignore("/path/to/some/assets","Mic01_1.pek"))
        self.assertTrue(test_list.should_ignore("/path/to/some/assets","something.aep 48000.cfa"))
        self.assertTrue(test_list.should_ignore("/path/to/some/Adobe Premiere Pro Video Previews/subpath","yadayadayada.xxx"))

    def test_should_not_match(self):
        from asset_folder_importer.asset_folder_sweeper.ignore_list import IgnoreList

        test_list = IgnoreList()

        self.assertFalse(test_list.should_ignore("/path/to/some/subpath","yadayadayada.xxx"))
        self.assertFalse(test_list.should_ignore("/path/to/some/assets","Mic_01.pk.wav"))
        self.assertFalse(test_list.should_ignore("/path/to/some/assets","something containing PFR.ext"))
        self.assertFalse(test_list.should_ignore("/path/to/some/assets","pkarnia.mxf"))
        self.assertFalse(test_list.should_ignore("/path/to/some/assets","wood.pekker.mxf"))
