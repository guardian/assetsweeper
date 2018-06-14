import subprocess
import logging

logger = logging.getLogger(__name__)

def posix_get_mime(filepath,db):
    try:
        (out, err) = subprocess.Popen(['/usr/bin/file','-b','--mime-type',filepath],stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()
        if out:
            return out.rstrip('\n')
        return None
    except Exception as e:
        logger.error("Error using /usr/bin/file to get MIME type: %s" % e.message)
        db.insert_sysparam("warning","Error using /usr/bin/file to get MIME type: %s" % e.message)
        return None