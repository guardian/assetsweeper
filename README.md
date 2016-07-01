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

python ./remove_locks.py

You should see the following output if there was a lock present when the script was run: -

Locked

If the script could not find a lock it will output the following line: -

Not locked


Other
-----

To be completed!