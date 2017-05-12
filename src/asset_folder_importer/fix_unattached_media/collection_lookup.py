import logging
import re
import os
from gnmvidispine.vs_search import VSCollectionSearch, VSException
from exceptions import *


class CollectionLookup(object):
    def __init__(self, startpath, host, port, user, password):
        self._startpath = startpath
        self._logger = logging.getLogger("CollectionLookup")
        self._logger.level = logging.DEBUG
        self._host = host
        self._port = port
        self._user = user
        self._pass = password
        
        self._keyword_splitter = re.compile(r'_')
    
    def listdirs(self):
        for workgroup in os.listdir(self._startpath):
            wgpath = os.path.join(self._startpath, workgroup)
            if workgroup == "." or workgroup == ".." or not os.path.isdir(
                    wgpath) or workgroup == "Branding" or workgroup == "Multimedia_News":
                continue
            self._logger.debug(workgroup)
            for commission in os.listdir(wgpath):
                commpath = os.path.join(wgpath, commission)
                if commission == "." or commission == ".." or not os.path.isdir(commpath):
                    continue
                self._logger.debug(workgroup + " -> " + commission)
                
                for user_project in os.listdir(commpath):
                    project_path = os.path.join(commpath, user_project)
                    if project_path == "." or project_path == ".." or not os.path.isdir(project_path):
                        continue
                    self._logger.debug(workgroup + " -> " + commission)
                    
                    yield {'project': user_project, 'commission': commission, 'workgroup': workgroup,
                           'path'   : project_path}
    
    def find_matching_entry(self, result, wanted_title):
        import re
        title_munger = re.compile(r'[^\w\d]+')
        # titles = map(lambda x: x.get('title'), result.results(shouldPopulate=True))
        
        for item in result.results(shouldPopulate=False):
            item.populate(item.name,specificFields='title')
            to_match = title_munger.sub('_', item.get('title'))
            self._logger.debug("matching {0} against {1}".format(to_match, wanted_title))
            if to_match == wanted_title:
                return item
        
        self._logger.debug("nothing matched")
        return None
    
    def find_in_vs(self, projectinfo):
        """
        Tries to locate the project with the given user/projectname in Vidispine.
        :param projectinfo: dictionary of project information. Currently expects one key, 'project'.
        :return: None if the project was not found, or the project ID if it was
        """
        if not isinstance(projectinfo, dict): raise KeyError
        
        s = VSCollectionSearch(host=self._host, port=self._port, user=self._user, passwd=self._pass)
        
        projectparts = projectinfo['project'].split('_')
        if projectparts[0] == 'videoproducer1' or projectparts[0] == 'audioproducer1' or projectparts[0] == 'localhome':
            project_index = 1
        else:
            project_index = 2
        
        if (len(projectparts) < 2):
            project_index = 1
        
        project_only = "_".join(projectparts[project_index:])
        self._logger.info("searching for {0}".format(project_only))
        
        search_title = self._keyword_splitter.sub(' ', project_only)
        
        if search_title == "":
            raise InvalidProjectError("Nothing to search for")
        
        s.addCriterion({'title': "\"{0}\"".format(search_title)})
        s.addCriterion({'gnm_type': 'Project'})
        try:
            result = s.execute()
        except VSException as e:
            self._logger.error("{0}. Searching for {1}".format(str(e), search_title))
            raise
        
        self._logger.info("Returned {0} hits for {1} on exact".format(result.totalItems, projectinfo['project']))
        
        if (result.totalItems == 1):
            for r in result.results(shouldPopulate=False):
                return r.name
        
        if result.totalItems == 0:
            s = VSCollectionSearch(host=self._host, port=self._port, user=self._user, passwd=self._pass)
            s.addCriterion({'title': "{0}".format(search_title)})
            s.addCriterion({'gnm_type': 'Project'})
            result = s.execute()
            self._logger.info("Returned {0} hits for {1} on inexact".format(result.totalItems, projectinfo['project']))
            if (result.totalItems == 1):
                for r in result.results(shouldPopulate=False):
                    return r.name
        
        # ok so we have more than one entry.
        wanted_title = "_".join(projectparts[project_index:])
        best_guess = self.find_matching_entry(result, wanted_title)
        if best_guess is not None:
            self._logger.debug(
                "Found {0} as best matching between {1} and {2}".format(best_guess.name, best_guess.get('title'),
                                                                        wanted_title))
            return best_guess.name
        
        interesting = ['title', 'gnm_asset_category', 'gnm_type']
        for collection in result.results(shouldPopulate=False):
            collection.populate(collection.name, specificFields=interesting)
            self._logger.info("Got {0}".format(collection.name))
            for f in interesting:
                self._logger.info("\t{0}: {1}".format(f, collection.get(f)))
        
        if result.totalItems < 4:
            for r in result.results(shouldPopulate=False):
                return r.name
        return None