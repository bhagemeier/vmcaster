# Makes things in right format.

from  ConfigParserJson import jsonConfigParser as ConfigParser
import os

import logging
import uploader

class Error(Exception):
    """Base class for exceptions in this module."""
    pass

class InputError(Error):
    """Exception raised for errors in the input.

    Attributes:
        msg  -- explanation of the error
    """

    def __init__(self, msg):
        self.msg = msg



class hostUploader:
    def __init__(self,cfgFile):
        self.log = logging.getLogger("hostUploader")
        self.config = ConfigParser()
        self.config.read(cfgFile)
        self.allHosts = {}
        for section in self.config.sections():
            writeProto = None
            if self.config.has_option(section, 'protocol'):
                writeProto = self.config.getJson(section,'protocol')
            else:
                self.log.error("Section '%s' is missing a 'protocol' config setting." % (section))
                continue
            serverName = None
            if self.config.has_option(section, 'server'):
                serverName = self.config.getJson(section,'server')
            else:
                self.log.error("Section '%s' is missing a 'server' config setting." % (section))
                continue
            uriReplace = None
            if self.config.has_option(section, 'uriReplace'):
                uriReplace = self.config.getJson(section,'uriReplace')
            else:
                self.log.error("Section '%s' is missing a 'uriReplace' config setting." % (section))
                continue
            
            uriPrefix = None
            if self.config.has_option(section, 'uriMatch'):
                uriMatch = self.config.getJson(section,'uriMatch')
            else:
                self.log.error("Section '%s' is missing a 'uriMatch' config setting." % (section))
                continue
            self.allHosts[serverName] = {'serverName' : serverName,
                'writeProto' : writeProto,
                'uriReplace' : uriReplace,
                'uriMatch' : uriMatch}
            
    def replaceFile(self,localPath,remoteHost,externalPath):
        numberHosts = len(self.allHosts)
        if numberHosts == 0:
            self.log.warning("No hosts configred, please check the configuration file.")
            raise InputError("No hosts configured")
        if not remoteHost in self.allHosts:
            self.log.warning("Hosts '%s' is not configured." % (remoteHost))
            self.log.info("Available hosts:" % (self.allHosts.keys()))
            raise InputError("Host '%s' is not registered" % remoteHost)
        if not os.path.isfile(localPath):
            raise InputError("File not found at path '%s'" % localPath)
        u1 = uploader.uploaderFacade()
        u1.uploader = self.allHosts[remoteHost]["writeProto"]
        u1.remotePrefix = self.allHosts[remoteHost]["uriReplace"]
        u1.externalPrefix = self.allHosts[remoteHost]["uriMatch"]
        output = u1.replace(localPath,externalPath)
        return output
    def uploadFile(self,localPath,remoteHost,remotePath):
        if not remoteHost in self.allHosts:
            self.log.info("Available hosts:" % (self.allHosts.keys()))
            raise InputError("Host '%s' is not known" % remoteHost)
        if not os.path.isfile(localPath):
            raise InputError("file not found at localpath '%s'" % localPath)
        u1 = uploader.uploaderFacade()
        u1.uploader = self.allHosts[remoteHost]["writeProto"]
        u1.remotePrefix = self.allHosts[remoteHost]["uriReplace"]
        u1.externalPrefix = self.allHosts[remoteHost]["uriMatch"]
        return u1.upload(localPath,remotePath)
    def deleteFile(self,remoteHost,remotePath):
        if not remoteHost in self.allHosts:
            self.log.info("Available hosts:" % (self.allHosts.keys()))
            raise InputError("Host '%s' is not known" % remoteHost)
        u1 = uploader.uploaderFacade()
        u1.uploader = self.allHosts[remoteHost]["writeProto"]
        u1.remotePrefix = self.allHosts[remoteHost]["uriReplace"]
        u1.externalPrefix = self.allHosts[remoteHost]["uriMatch"]
        return u1.delete(remotePath)
        
if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    obj = hostUploader('publisher.cfg')
    #obj.uploadFile('/etc/fstab','dish.desy.de','dfsdfsdf')
    obj.delete('dfsdfsdf')
