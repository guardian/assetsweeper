#!/usr/bin/python
# -*- coding: utf-8 -*-

filepath = 'Día 2'

safe_filepath = unicode(filepath, errors='strict')


safe_filepath2 = filepath.encode('utf-8', errors='strict')

print safe_filepath2