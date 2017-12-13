__author__ = 'dave'
import re


class IgnoreList(object):
    """
    this class represents a static "ignore" list of regexes, to be matched against directory and file names
    """
    #mark a file as to be ignored, if any of these regexes match. This will prevent vsingester from importing it.
    pathShouldIgnore = [
        'Adobe Premiere Pro Preview Files',
        'System Volume Information',
        '\.Spotlight.*',
        '\.numbers',
        '\.plist$',
        '\.TMP',
        '^\.',  #should ignore a literal dot, but only if it follows a /
        '\.pk$',
        '\.PFL$',
        '\.PFR$',   #Cubase creates these filetypes
        '\.peak$',
        '\.pek$',
        '_synctemp', #this is created by PluralEyes
        '\.cfa$',
        '\.aep Logs',
        'Adobe Premiere Pro Video Previews'
    ]

    def __init__(self):
        """
        initialise the class by compiling the above list
        :return: None
        """
        self.reShouldIgnore = []
        for expr in self.pathShouldIgnore:
            self.reShouldIgnore.append(re.compile(expr))

    def should_ignore(self, dirname, filename):
        """
        Check the given path to see if either the directory name or the file name match
        :param dirname: directory name portion of the path
        :param filename: filename portion of the path
        :return: Boolean indicating whether to ignore the file
        """
        for expr in self.reShouldIgnore:
            if expr.search(dirname) is not None:
                return True
            if expr.search(filename) is not None:
                return True
        return False
