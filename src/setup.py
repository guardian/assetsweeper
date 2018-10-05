#!/usr/bin python

from distutils.core import setup

setup(name='gnm-assetsweeper',
      version='3.0',
      description='Set of programmes to handle import of items to MAM from asset folders',
      author='Andy Gallagher',
      author_email='andy.gallagher@theguardian.com',
      packages=['asset_folder_importer',
                'asset_folder_importer.asset_folder_sweeper',
                'asset_folder_importer.asset_folder_vsingester',
                'asset_folder_importer.premiere_get_referenced_media',
                'asset_folder_importer.fix_unattached_media',
                'asset_folder_importer.metadata_templates',
                'asset_folder_importer.asset_folder_verify_files',
                'asset_folder_importer.pluto',
                'asset_folder_importer.providers',
                ],
      package_data={
            'asset_folder_importer': ['metadata_templates/*']
      },
      scripts=['asset_folder_sweeper.py','asset_folder_verify_files.py',
               'asset_folder_vsingester.py','asset_permissions.pl',
               'prelude_importer.py','premiere_get_referenced_media.py',
               'fix_unattached_media.py','vs_resync_deleted.py', 'find_flushable_unimported_media.py',
               'remove_locks.py'],
      data_files=[
          ('/etc',['asset_folder_importer.cfg','footage_providers.yml']),
          ('/etc/sudoers.d',['asset_folder_sudo'])
      ]
      )
