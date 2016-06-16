{#- this saltstate installs asset_folder_importer from the vidispine scripts repo -#}
{%- set python_version = "2.6" -%}
{%- set site_packages = "/usr/lib64/python" + python_version + "/site-packages" -%}
{%- set install_path = "/usr/local/scripts/asset_folder_importer" -%}
{%- set symlink_path = "/usr/local/bin" -%}
{%- set username = "asset_folder_importer" -%}
{%- set owner_uid = username -%}
{%- set owner_gid = 0 -%}
{%- set module_perm = '0644' -%}
{%- set config_perm = '0640' -%}
{%- set bin_perm = '0755' -%}

{#- NOTE: you need to have GNMVidispine available for installation in the root
of your saltstates, otherwise Salt claims it can't find THIS state -#}
include:
  - GNMVidispine

#install python and any modules required
baserequirements:
  pkg.installed:
    - pkgs:
      - python
      - python-psycopg2
      - python-setuptools
      - python-jinja2

#create a user to run as
{{ username }}:
  user.present:
    - full_name: Service account for importing asset content into Vidispine
    - home: /home/{{ username }}
    - groups:
      - cds

/etc/asset_folder_importer.cfg:
  file.managed:
    - source: salt://assetimporter/files/asset_folder_importer.cfg
    - user: {{ owner_uid }}
    - group: {{ owner_gid }}
    - mode: {{ config_perm }}

{{ site_packages }}/asset_folder_importer:
  file.recurse:
    - source: salt://assetimporter/files/asset_folder_importer
    - exclude_pat: 'E@(\.svn)'
    - include_empty: true
    - makedirs: true
    - user: {{ owner_uid }}
    - group: {{ owner_gid }}
    - file_mode: {{ module_perm }}

{{ install_path }}:
  file.directory:
    - user: root
    - group: root
    - mode: '755'
    - makedirs: True
    
{% for scriptfile in ['asset_folder_sweeper.py','asset_folder_vsingester.py','prelude_importer.py',''] %}
{{ install_path }}/{{ scriptfile }}:
  file.managed:
    - source: salt://assetimporter/files/{{ scriptfile }}
    - user: {{ owner_uid }}
    - group: {{ owner_gid }}
    - mode: {{ bin_perm }}
    - makedirs: True
    
{{ scriptfile }}_symlink:
  file.symlink:
    - name: {{ symlink_path }}/{{ scriptfile }}
    - target: {{ install_path }}/{{ scriptfile }}
{% endfor %}

{{ install_path }}/asset_permissions.pl:
  file.managed:
    - source: salt://assetimporter/files/asset_permissions.pl
    - user: root
    - group: {{ owner_gid }}
    - mode: '4555'  #this needs to be installed suid-root, to set permissions on files.  Therefore it cannot be writable to anyone.
    - makedirs: True

script1_cron:
  cron.present:
    - name: {{ install_path }}/asset_folder_sweeper.py
    - user: {{ username }}
    - minute: 10
    - comment: First script that populates the database with the filesystem state of the assets folders

script2_cron:
  cron.present:
    - name: {{ install_path }}/prelude_importer.py
    - user: {{ username }}
    - minute: 40
    - comment: Second script that populates the database with information from all Prelude ingest projects in the system

script3_cron01:
  cron.present:
    - name: {{ install_path }}/asset_folder_vsingester.py
    - user: {{ username }}
    - hour: '*/3'
    - minute: 0
    - comment: Third script that goes through the database of assets and associated Prelude projects and updates Vidispine with all assets

