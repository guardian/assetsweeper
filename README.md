Asset Sweeper
=============

How to run locally
------------------

You should run:

 \$ source setup_env.sh
 
in order to set up the PYTHONPATH that will allow gnmvidispine and asset_folder_importer to run.


How to remove locks
-------------------

If vsingester will not run then you can remove the lock my using the remove_locks.py script. To use it become root and run the following command: -

python ./remove_locks.py [--config=/path/to/config/file] [--scriptname=scriptname]
If --config is not passed, then it expects the config file to be located at /etc/asset_folder_importer.cfg.
If --scriptname is not passed, then it will work on asset_folder_vsingester.

You should see the following output if there was a lock present when the script was run: -

Script is locked. Removing lock.

If the script could not find a lock it will output the following line: -

Script is not locked.


Other
-----

To be completed!