Asset Sweeper
=============

How to run locally
==================

You should run:

 `\$ source setup_env.sh`
 
in order to set up the PYTHONPATH that will allow `gnmvidispine` and `asset_folder_importer` to run.

Requirements:
-------------

 - Postgres 9.0+
 - Python 2.6+
 
I would generally recommend running this in a VM container, but you can run it locally on a Mac (or probably Windows too!) if you want

Step one - set up Postgres
--------------------------

On Linux, installing Postgres is usually as simple as:
     ```$ sudo yum install postgresql-91```
or 
     ```$ sudo apt-get install postgresql-server```
 
On a Mac, I would generally recommend Macports.  Once downloaded and installed (https://www.macports.org), you should be
able to simply run:
     ``$ sudo port install postgresql91-server postgresql91``
 
Next, you will need to run initdb and any other commands that the setup program tells you too.

Next, set up a user.  I recommend using this username, as the schema files automatically grant permissions to it:
    ``$ sudo -u postgres 'createuser assetimporter``
    
Then, create the database:
    ``$ sudo -u postgres 'createdb asset_folder_importer -O assetimporter``

Then, you need to install the database schema.  Assuming that postgres is running as the postgres user, run:
    ``$ sudo -u postgres 'psql asset_folder_importer < src/asset_folder_importer/asset_folder_importer_database.sql``
    ``$ sudo -u postgres 'psql asset_folder_importer < src/asset_folder_importer/schema_update_1.sql``
    
**Note** - the Postgres management commands (psql, initdb, creatuser, etc.) may not be in your PATH.
On my Mac, I have to prepend the installation path (`/opt/local/lib/postgresql91/bin/`) to make the above commands work.

Step two - set up a Virtualenv
------------------------------

I would strongly recommend setting up a Python virtual environment to host the installation environment (this is not necessary if you're running on a dedicated VM though).

```

$ sudo pip install virtualenv
$ mkdir -p ~/venv/assetimporter
$ virtualenv --python=python2.6 ~/venv/assetimporter
$ source ~/venv/assetimporter/bin/activate
(assetimporter) $
```
  
Tools like IntelliJ and PyCharm can simplify this process for you, consult their documentation for more details.

Once you have activated the virtual environment, you have a seperate python installation you can use and break
to your heart's content without damaging anything. And you can always blow it away and reinstall.

Next, install the Python requirements:

  ```
  (assetimporter) $ sudo pip install -r requirements.txt
  ```
  
If psycopg2 (the Postgres library) refuses to install, ensure that you have the relevant postgresql-devel or postgres91-dev packages
installed.  It needs these in order to compile its copy of the C interface library.

Step 3 - set up your configuration
----------------------------------



How to remove locks
-------------------

If vsingester will not run then you can remove the lock my using the remove_locks.py script. To use it become root and run the following command: -

```
python ./remove_locks.py [--config=/path/to/config/file] [--scriptname=scriptname]
```
If --config is not passed, then it expects the config file to be located at /etc/asset_folder_importer.cfg.
If --scriptname is not passed, then it will work on asset_folder_vsingester.

You should see the following output if there was a lock present when the script was run: -

Script is locked. Removing lock.

If the script could not find a lock it will output the following line: -

Script is not locked.


Other
-----

To be completed!
