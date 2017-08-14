import os
import logging
import re

logger = logging.getLogger(__name__)

is_multimedia = re.compile(r'^Multimedia')


def get_asset_folder_for(folderpath):
    """
    Reads the folder path given and returns the asset folder segment, if indeed this is an asset folder.
    Raises a ValueError if the path is not recognised
    :param folderpath: path to check
    :return: asset folder path
    """
    split_parts = folderpath.split('/')

    #if the format is correct, [4] should be 'Assets' , [5] should be working group, [6] commission and [7] should be user_project
    if split_parts[4]!='Assets':
        raise ValueError("{0} does not look like an asset folder path".format(folderpath))

    if not is_multimedia.match(split_parts[5]):
        logger.warning("Folder path {0} is suspicious: {1} does not start 'Multimedia'".format(folderpath, split_parts[5]))

    tojoin = split_parts[5:8]
    return os.path.join(*tojoin)