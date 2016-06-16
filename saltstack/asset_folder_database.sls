{% set dbuser = salt['pillar.get']('asset_folder_importer:dbuser', 'assetimporter') %}
{% set dbpass = salt['pillar.get']('asset_folder_importer:dbpass', '***REMOVED***') %}

db_user:
  postgres_user.present:
    - name: {{ dbuser }}
    - createdb: False
    - createroles: False
    - encrypted: True
    - login: True
    - superuser: False
    - password: {{ dbpass }}
    - user: postgres

asset_folder_importer:
  postgres_database.present:
    - owner: {{ dbuser }}
    - user: postgres
    
/tmp/asset_folder_importer_database.sql:
  file.managed:
    - source: salt://assetimporter/files/asset_folder_importer/asset_folder_importer_database.sql
    - user: postgres
    - group: postgres
    - mode: 600
    
schema_install:
  cmd.run:
    - name: "psql asset_folder_importer < /tmp/asset_folder_importer_database.sql"
    - user: postgres 
    - cwd: /var/lib/pgsql
  watch:
    - file: /tmp/asset_folder_importer_database.sql
    
tempfile_cleanup:
  file.absent:
    - name: /tmp/asset_folder_importer_database.sql
