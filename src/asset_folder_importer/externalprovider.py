class VSMetadataList(dict):
    """
    Subclass of a standard dictionary that allows the automatic recursive creation of a set of parameters suitable
    for an ItemSearchDocument
    """
    def _recurse_dict(self, data, parent):
        from xml.etree.ElementTree import Element, SubElement

        rtn = []
        for k, v in data.items():
            if isinstance(v, dict):
                if parent is None:
                    el = Element('group')
                    rtn.append(el)
                else:
                    el = SubElement(parent, 'group', {'mode': 'add'})
                nameEl = SubElement(el, 'name')
                nameEl.text = unicode(k)
                self._recurse_dict(v, el)
            elif isinstance(v, list):
                if parent is None:
                    el = Element('field')
                    rtn.append(el)
                else:
                    el = SubElement(parent, 'field')
                nameEl = SubElement(el, 'name')
                nameEl.text=unicode(k)
                for i in v:
                    valueEl = SubElement(el, 'value')
                    valueEl.text = unicode(i)
            else:
                if parent is None:
                    el = Element('field')
                    rtn.append(el)
                else:
                    el = SubElement(parent, 'field')
                nameEl = SubElement(el, 'name')
                nameEl.text=unicode(k)
                valueEl = SubElement(el, 'value')
                valueEl.text = unicode(v)
        return rtn

    def _my_tostring(self, element, encoding="UTF-8", method="xml", xml_declaration=False):
        import xml.etree.ElementTree as ET
        class dummy:
            pass
        data = []
        file = dummy()
        file.write = data.append
        ET.ElementTree(element).write(file, encoding)

        return "".join(data[1:])

    def to_vs_xml(self):

        #return "".join(data)
        lines = self._recurse_dict(self, None)

        return "\n".join(map(lambda x: self._my_tostring(x, encoding="UTF-8"), lines))

class ExternalProviderList(object):
    def __init__(self,providerlist):
        import yaml
        import logging

        self.filename = providerlist
        f=open(providerlist) #raises exception if file can't be opened
        self._data = yaml.load(f.read())
        f.close()
        self.logger = logging.getLogger('asset_folder_impoter.externalprovider')

    @staticmethod
    def get_provider(kls,*args,**kwargs):
        """
        Initialises the given metadata provider class.  Raises an exception if the class is not found.
        :param kls: python qualified pathname of the provider class
        :param args: any arguments required by the provider class
        :param kwargs: any keyword arguments required by the provider class
        :return: initialised instance of the named class
        """
        try:
            #module = kls + ".Provider"
            m = __import__( kls )
            #m = getattr(m, "Provider")
            parts = kls.split('.')
            for comp in parts[1:]:
                m = getattr(m, comp)
            return m.Provider(*args,**kwargs)
        except ImportError:
            parts = kls.split('.')
            module = ".".join(parts[:-1])
            m = __import__( module )
            for comp in parts[1:]:
                m = getattr(m, comp)
            return m(*args,**kwargs)

    @staticmethod
    def _build_regex_cache(relist):
        """
        Given an array of regular expressions, compiles them for later use
        :param relist:
        :return:
        """
        import re
        return map(lambda x: re.compile(x),relist)

    def _sanitise(self,data):
        if not 'grouped' in data:
            data['grouped'] = {}
        if not 'ungrouped' in data:
            data['ungrouped'] = {}
        return data

    def try_file(self,filepath,filename):
        """
        Attempt to find out information on a file using all of the registered providers
        :param filepath: path to the file on-disk
        :param filename: filename of the file on-disk
        :return: a dictionary of provided metadata, or None if no providers were found
        """
        for provider_name, provider_info in self._data.items():
            if not 'match' in provider_info:
                self.logger.warning("No match parameter in {0} block in yaml list {1}".format(provider_name,
                                                                                              self.filename))
                continue

            if not 'regex_cache' in provider_info:
                provider_info['regex_cache'] = self._build_regex_cache(provider_info['match'])

            for expr in provider_info['regex_cache']:
                match_data = expr.search(filename)
                if match_data:
                    provider = self.get_provider(provider_info['module']) #raises if it can't be found
                    data = provider.lookup(filepath, filename, match_data)
                    #if data is not None:
                    #    self._sanitise(data)
                    return VSMetadataList(data)

        self.logger.warning("No metadata provider matches filename {0}".format(filename))
        return None

if __name__ == '__main__':
    import logging
    from sys import argv
    from pprint import pprint
    from jinja2 import Environment,PackageLoader

    LOGFORMAT = '%(asctime)-15s - %(levelname)s - %(funcName)s: %(message)s'
    main_log_level = logging.DEBUG
    logging.basicConfig(format=LOGFORMAT, level=main_log_level)

    logging.info("running tests for externalprovider module")
    l = ExternalProviderList('footage_providers.yml')

    if len(argv) < 2:
        print "\nRun tests on externalprovider module. Usage: python externalprovider.py {filename-to-query}\n"
        exit(1)

    logging.info("running against filename %s" % argv[1])
    data = l.try_file("",argv[1])
    # logging.info("returned data:")
    # pprint(data)
    # print data.to_vs_xml()

    templateEnv = Environment(loader=PackageLoader('asset_folder_importer','metadata_templates'))
    mdTemplate = templateEnv.get_template('vsasset_test.xml')
    print mdTemplate.render({'externalmeta': data})
