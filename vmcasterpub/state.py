
import sys
if sys.version_info < (2, 4):
    print "Your python interpreter is too old. Please consider upgrading."
    sys.exit(1)

if sys.version_info < (2, 5):
    import site
    import os.path
    from distutils.sysconfig import get_python_lib
    found = False
    module_dir = get_python_lib()
    for name in os.listdir(module_dir):
        lowername = name.lower()
        if lowername[0:10] == 'sqlalchemy' and 'egg' in lowername:
            sqlalchemy_dir = os.path.join(module_dir, name)
            if os.path.isdir(sqlalchemy_dir):
                site.addsitedir(sqlalchemy_dir)
                found = True
                break
    if not found:
        print "Could not find SQLAlchemy installed."
        sys.exit(1)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import vmcasterpub.dishpubdb as model

import os.path
import logging
import optparse
from __version__ import version
import urllib2
import urllib
import hashlib
import datetime
import os, statvfs
import shutil
import commands
try:
    import simplejson as json
except:
    import json

import urlparse
import subprocess
import time
import types



# Taken from earlier vmlitrustlib

time_required_metadata = [u'dc:date:created',
        u'dc:date:expires',
    ]
time_required_metadata_set = set(time_required_metadata)

endorser_required_metadata = [u'hv:ca',
        u'hv:dn',
        u'hv:email',
        u'dc:creator',
    ]
endorser_required_metadata_set = set(endorser_required_metadata)

image_required_metadata = [u'dc:title',
        u'dc:description',
        u'hv:size',
        u'sl:checksum:sha512',
        u'sl:arch',
        u'hv:uri',
        u'dc:identifier',
        u'sl:os',
        u'sl:osversion',
        u'sl:comments',
        u'hv:hypervisor',
        u'hv:version',
    ]
image_required_metadata_set = set(image_required_metadata)


imagelist_required_metadata = [u'dc:date:created',
        u'dc:date:expires',
        u'dc:identifier',
        u'dc:description',
        u'dc:title',
        u'dc:source',
        u'hv:version',
        u'hv:uri',
    ]
imagelist_required_metadata_set = set(imagelist_required_metadata)

imagelist_required_metadata_types = [u'hv:endorser',
        u'hv:images',
    ]
imagelist_required_metadata_types_set = set(imagelist_required_metadata_types)





class imagelistpub:
    def __init__(self,databaseConnectionString):
        self.log = logging.getLogger("imagelistpub")
        self.engine = create_engine(databaseConnectionString, echo=False)
        model.init(self.engine)
        self.SessionFactory = sessionmaker(bind=self.engine)
        #self.Session = self.SessionFactory()
    
    def endorserList(self):
        Session = self.SessionFactory()
        query_endorser = Session.query(model.Endorser)
        if query_endorser.count() == 0:
            self.log.warning('No endorsers found')            
        for endorser in query_endorser:
            print endorser.subject

    def endorserAdd(self, subject):
        Session = self.SessionFactory()
        query_endorser = Session.query(model.Endorser).\
            filter(model.Endorser.subject == subject)
        if query_endorser.count() == 0:
            newEndorser = model.Endorser(subject)
            Session.add(newEndorser)
            Session.commit()
            return True
        self.log.warning("Endorser is already present with this subject")
        return False
    def endorserDel(self, subject):
        Session = self.SessionFactory()
        query_endorser = Session.query(model.Endorser).\
            filter(model.Endorser.subject == subject)
        if query_endorser.count() == 0:
            self.log.warning("Endorser does not exist.")
            return False      
        for item in query_endorser:
            Session.delete(item)
        Session.commit()
        return True


    def endorserMetadataUpdate(self, subject,key,value):
        Session = self.SessionFactory()
        query_endorser = Session.query(model.Endorser).\
            filter(model.Endorser.subject == subject)
        if query_endorser.count() == 0:
            self.log.warning("Endorser does not exist.")
            return False
        SelEndorser = query_endorser.one()
        EndorserId = SelEndorser.id
        query_endorsermetadata = Session.query(model.EndorserMetadata).\
            filter(model.Endorser.subject == subject).\
            filter(model.Endorser.id == model.EndorserMetadata.fkEndorser).\
            filter(model.EndorserMetadata.key == key)
        if query_endorsermetadata.count() == 0:
            self.log.warning("making new key '%s' with value '%s'" % (key,value))
            newpetadata = model.EndorserMetadata(EndorserId, key,value)
            Session.add(newpetadata)
        else:
            for item in query_endorsermetadata:
                item.value = value
        Session.commit()
        return True


    def endorserMetadataDel(self, subject,key):
        self.log.error("not implemented yet")
    
    def endorserDump(self, subject):
        Session = self.SessionFactory()
        query_endorser = Session.query(model.Endorser).\
            filter(model.Endorser.subject == subject)
        if query_endorser.count() == 0:
            self.log.warning("Endorser does not exist.")
            return None
        SelEndorser = query_endorser.one()
        output = {"hv:dn" : str(SelEndorser.subject)}
        EndorserId = SelEndorser.id
        query_endorsermetadata = Session.query(model.EndorserMetadata).\
            filter(model.Endorser.subject == subject).\
            filter(model.Endorser.id == model.EndorserMetadata.fkEndorser)
        for item in query_endorsermetadata:
            try:
                value = int(item.value)
            except ValueError:
                value = str(item.value)
            
            output[str(item.key)] = value
        return output

    def imageListEndorserConnect(self, imagelistUUID,endorserSubject):
        Session = self.SessionFactory()
        queryEndorsements = Session.query(model.Endorsement).\
            filter(model.Endorser.subject == endorserSubject).\
            filter(model.Imagelist.identifier == imagelistUUID ).\
            filter(model.Imagelist.id == model.Endorsement.fkImageList).\
            filter(model.Endorser.id == model.Endorsement.fkEndorser)
        if queryEndorsements.count() > 0:
            self.log.warning("'%s' already endorses '%s'" % (endorserSubject,imagelistUUID))
            return False

        query_imagelists = Session.query(model.Imagelist).\
            filter(model.Imagelist.identifier == imagelistUUID )
        if query_imagelists.count() == 0:
            self.log.warning('No imagelists found')
            return False
        query_endorser = Session.query(model.Endorser).\
            filter(model.Endorser.subject == endorserSubject)
        if query_endorser.count() == 0:
            self.log.warning("Endorser does not exist.")
            return False
        imagelist = query_imagelists.one()
        endorser = query_endorser.one()
        endorsement = model.Endorsement(imagelist.id,endorser.id)
        Session.add(endorsement)
        Session.commit()
        return True
    def imageListEndorserDisconnect(self, imagelistUUID,endorserSubject):
        Session = self.SessionFactory()
        queryEndorsements = Session.query(model.Endorsement).\
            filter(model.Endorser.subject == endorserSubject).\
            filter(model.Imagelist.identifier == imagelistUUID ).\
            filter(model.Imagelist.id == model.Endorsement.fkImageList).\
            filter(model.Endorser.id == model.Endorsement.fkEndorser)
        if queryEndorsements.count() == 0:
            self.log.warning("'%s' does not endorse '%s'" % (endorserSubject,imagelistUUID))
            return False
        for item in queryEndorsements:
            Session.delete(item)
            
        Session.commit()
        return True
    
    
    def imageListImageConnect(self, imagelistUUID,imageUUID):
        Session = self.SessionFactory()
        queryimageBindings = Session.query(model.ImageListImage).\
            filter(model.Image.identifier == imageUUID).\
            filter(model.Imagelist.identifier == imagelistUUID ).\
            filter(model.Imagelist.id == model.ImageListImage.fkImageList).\
            filter(model.Image.id == model.ImageListImage.fkImage)
        if queryimageBindings.count() > 0:
            self.log.warning("'%s' already linked to '%s'" % (imageUUID,imagelistUUID))
            return False

        query_imagelists = Session.query(model.Imagelist).\
            filter(model.Imagelist.identifier == imagelistUUID )
        if query_imagelists.count() == 0:
            self.log.warning('No matching imagelist found')
            return False
        query_image = Session.query(model.Image).\
            filter(model.Image.identifier == imageUUID)
        if query_image.count() == 0:
            self.log.warning("Image does not exist.")
            return False
        imagelist = query_imagelists.one()
        image = query_image.one()
        imageBinding = model.ImageListImage(imagelist.id,image.id)
        Session.add(imageBinding)
        Session.commit()
        return True
    
    
    def imageListImageDisconnect(self, imagelistUUID,imageUUID):
        Session = self.SessionFactory()
        queryImageListImage = Session.query(model.ImageListImage).\
            filter(model.Image.identifier == imageUUID).\
            filter(model.Imagelist.identifier == imagelistUUID ).\
            filter(model.Imagelist.id == model.ImageListImage.fkImageList).\
            filter(model.Image.id == model.ImageListImage.fkImage)
        if queryImageListImage.count() == 0:
            self.log.warning("'%s' is not linked to '%s'" % (imagelistUUID,imagelistUUID))
            return False
        for item in queryImageListImage:
            Session.delete(item)
        Session.commit()
        return True
    

    def imageListList(self):
        Session = self.SessionFactory()
        query_imagelists = Session.query(model.Imagelist)
        if query_imagelists.count() == 0:
            self.log.warning('No imagelists found')            
        for imagelist in query_imagelists:
            print imagelist.identifier
        
    def imageListAdd(self,UUID):
        Session = self.SessionFactory()
        query_imagelists = Session.query(model.Imagelist).\
                filter(model.Imagelist.identifier == UUID )
        if query_imagelists.count() > 0:
            self.log.warning('Imagelist already exists')
            return False
        newImage = model.Imagelist(UUID)
        Session.add(newImage)
        Session.commit()
        return True

    def imagesDel(self,UUID):
        Session = self.SessionFactory()
        query_imagelists = Session.query(model.Imagelist).\
                filter(model.Imagelist.identifier == UUID )
        for item in query_imagelists:
            Session.delete(item)
        Session.commit()
        return True
    def imageShow(self,UUID):
        Session = self.SessionFactory()
        query_imagelist_images = Session.query(model.Image).\
                filter(model.Image.identifier == UUID )
        count = query_imagelist_images.count()
        
        imagesarray = []
        if query_imagelist_images.count() > 0:
            
            for image in query_imagelist_images:
                imagemetadata = {u"dc:identifier" : str(image.identifier)}
                query_imageMetadata = Session.query(model.ImageMetadata).\
                    filter(model.Image.identifier ==  image.identifier).\
                    filter(model.Image.id == model.ImageMetadata.fkImage)
                for imageItem in query_imageMetadata:
                    if imageItem.key in ["hv:size"]:
                        imagemetadata[imageItem.key] = int(imageItem.value)
                    else:
                        imagemetadata[imageItem.key] = imageItem.value
                return imagemetadata
        return None
 
        
    def imageListShow(self,UUID):
        Session = self.SessionFactory()
        query_imagelists = Session.query(model.Imagelist).\
                filter(model.Imagelist.identifier == UUID )
        if query_imagelists.count() == 0:
            self.log.warning('No imagelists found')
            return None
        imagelist = query_imagelists.one()
        outModel = {}
        query_imagelistmetadata = Session.query(model.ImagelistMetadata).\
                filter(model.Imagelist.identifier == UUID ).\
                filter(model.Imagelist.id == model.ImagelistMetadata.fkImageList)
        for item in query_imagelistmetadata:
            outModel[item.key] = item.value
        query_imagelist_images = Session.query(model.Image).\
                filter(model.Imagelist.identifier == UUID ).\
                filter(model.ImageListImage.fkImageList == model.Imagelist.id).\
                filter(model.ImageListImage.fkImage == model.Image.id)
                
        if query_imagelist_images.count() > 0:
            imagesarray = []
            for image in query_imagelist_images:
                imagemetadata = {u"dc:identifier" : str(image.identifier)}
                query_imageMetadata = Session.query(model.ImageMetadata).\
                    filter(model.Image.identifier ==  image.identifier).\
                    filter(model.Image.id == model.ImageMetadata.fkImage)
                for imageItem in query_imageMetadata:
                    if imageItem.key in ["hv:size"]:
                        try:
                            imagemetadata[imageItem.key] = int(imageItem.value)
                        except:
                            self.log.warning("Invalid value for 'hv:size'")
                            imagemetadata[imageItem.key] = imageItem.value
                    else:
                        imagemetadata[imageItem.key] = imageItem.value
                imagesarray.append({u'hv:image' : imagemetadata})
            outModel[u'hv:images'] = imagesarray
        outModel[u'dc:identifier'] = imagelist.identifier
            
        query_endorser = Session.query(model.Endorser).\
                filter(model.Imagelist.identifier == UUID ).\
                filter(model.Endorsement.fkImageList ==  model.Imagelist.id).\
                filter(model.Endorsement.fkEndorser ==  model.Endorser.id)
        endorserList = []
        for endorser in query_endorser:
            endosersID = int(endorser.id)
            endorserMetadata = {}
            query_metaData = Session.query(model.EndorserMetadata).\
                filter(model.Imagelist.identifier == UUID ).\
                filter(model.Endorser.id == endosersID ).\
                filter(model.Endorsement.fkImageList ==  model.Imagelist.id).\
                filter(model.Endorsement.fkEndorser ==  model.Endorser.id).\
                filter(model.EndorserMetadata.fkEndorser == model.Endorser.id)
                
            for metasdata in query_metaData:
                endorserMetadata[metasdata.key] = metasdata.value
            endorserMetadata["hv:dn"] = endorser.subject
            endorserList.append({ 'hv:x509' : endorserMetadata })
        if len(endorserList) > 0:
            if len(endorserList) == 1:
                outModel['hv:endorser'] = endorserList[0]
            else:
                outModel['hv:endorser'] = endorserList
            
        return {'hv:imagelist' : outModel}
    def imagelist_key_get(self,imageListUuid, imagelist_key):
        self.log.debug("start:imagelist_key_get(%s,%s,%s)" % (self,imageListUuid, imagelist_key))
        Session = self.SessionFactory()
        query_imagelists = Session.query(model.ImagelistMetadata).\
                filter(model.Imagelist.identifier == imageListUuid).\
                filter(model.Imagelist.id == model.ImagelistMetadata.fkImageList).\
                filter(model.ImagelistMetadata.key == imagelist_key)
                
        if query_imagelists.count() == 0:
            self.log.warning("No imagelist key '%s' found" % (imagelist_key))
            return None
        newMetaData = query_imagelists.one()
        output = newMetaData.value
        return str(output)
        
        
    def imagelist_key_update(self,imageListUuid, imagelist_key, imagelist_key_value):
        self.log.debug("start:imagelist_key_update %s - %s - %s" % (imageListUuid, imagelist_key, imagelist_key_value))
        Session = self.SessionFactory()
        query_imagelists = Session.query(model.Imagelist).\
                filter(model.Imagelist.identifier == imageListUuid)
        if query_imagelists.count() == 0:
            self.log.warning('No imagelists found')
            return None
        if imagelist_key in ['dc:identifier','hv:endorser','hv:images']:
            self.log.warning("Reserved key '%s' cannot be added" % (imagelist_key))
            return None
        query_imagekeys = Session.query(model.ImagelistMetadata).\
                filter(model.Imagelist.identifier == imageListUuid).\
                filter(model.Imagelist.id == model.ImagelistMetadata.fkImageList).\
                filter(model.ImagelistMetadata.key == imagelist_key)
        if not query_imagekeys.count() == 0:
            metadata = query_imagekeys.one()
            if metadata.value != imagelist_key_value:
                metadata.value = imagelist_key_value
                Session.add(metadata)
                Session.commit()
            return imagelist_key_value
        ThisImageList = query_imagelists.one()
        newMetaData = model.ImagelistMetadata(ThisImageList.id,imagelist_key,imagelist_key_value)
        Session.add(newMetaData)
        Session.commit()
        return imagelist_key_value

    def imagelist_key_del(self,imageListUuid, imagelist_key):
        Session = self.SessionFactory()
        query_imagelists = Session.query(model.ImagelistMetadata).\
                filter(model.Imagelist.identifier == imageListUuid).\
                filter(model.Imagelist.id == model.ImagelistMetadata.fkImageList).\
                filter(model.ImagelistMetadata.key == imagelist_key)
        if query_imagelists.count() == 0:
            self.log.warning('No imagelist key "%s" found' % (imagelist_key))
            return None
        newMetaData = query_imagelists.one()
        Session.delete(newMetaData)
        Session.commit()
        return True


                
    def imageList(self):
        output = []
        Session = self.SessionFactory()
        query_image = Session.query(model.Image)
        for item in query_image:
            output.append(str(item.identifier))
        return output
    
    def image_get_imagelist(self,imageUuid):
        Session = self.SessionFactory()
        query_imagelists = Session.query(model.Imagelist.identifier).\
            filter(model.Imagelist.id == model.ImageListImage.fkImageList).\
            filter(model.Image.id == model.ImageListImage.fkImage).\
            filter(model.Image.identifier == imageUuid)
        output = []
        for item in query_imagelists:
            output.append(str(item.identifier))
        return output

    def image_key_get(self,imageUuid,image_key):
        Session = self.SessionFactory()
        query_imagelists = Session.query(model.ImageMetadata).\
                filter(model.Image.identifier == imageUuid).\
                filter(model.Image.id == model.ImageMetadata.fkImage).\
                filter(model.ImageMetadata.key == image_key)

        if query_imagelists.count() == 0:
            self.log.warning("No image meta data found for image '%s' with key '%s'" % (imageUuid,image_key))
            return None
        if query_imagelists.count() > 1:
            self.log.warning('To  much image metadata found')
            return None
        outputRow = query_imagelists.one()
        return str(outputRow.value)
        
    def image_key_update(self, imageUuid ,image_key, image_value):
        Session = self.SessionFactory()
        
        query_image = Session.query(model.Image).\
                filter(model.Image.identifier == imageUuid)
        if query_image.count() == 0:
            self.log.warning('Image does not exist.')
            return None
        query_image_metadata = Session.query(model.ImageMetadata).\
                filter(model.Image.identifier == imageUuid).\
                filter(model.Imagelist.id == model.ImageListImage.fkImageList).\
                filter(model.Image.id == model.ImageListImage.fkImage).\
                filter(model.Image.id == model.ImageMetadata.fkImage).\
                filter(model.ImageMetadata.key == image_key)
        if query_image_metadata.count() == 0:
            image = query_image.one()
            newmetadata = model.ImageMetadata(image.id,image_key,image_value)
            Session.add(newmetadata)
            Session.commit()
            return True
        newmetadata = query_image_metadata.one()
        if newmetadata.value != image_value:
            newmetadata.value = image_value
            Session.add(newmetadata)
            Session.commit()
            return True
        return True
    def image_key_delete(self, imageUuid ,image_key):
        Session = self.SessionFactory()
        query_image_metadata = Session.query(model.ImageMetadata).\
                filter(model.Image.identifier == imageUuid).\
                filter(model.Imagelist.id == model.ImageListImage.fkImageList).\
                filter(model.Image.id == model.ImageListImage.fkImage).\
                filter(model.Image.id == model.ImageMetadata.fkImage).\
                filter(model.ImageMetadata.key == image_key)
        if query_image_metadata.count() == 0:
            self.log.warning('image key not found')
            self.log.debug('imageUuid=%s' % (imageUuid))
            self.log.debug('image_key=%s' % (image_key))
            return True
        for item in query_image_metadata:
            Session.delete(item)
        Session.commit()
        return True

    def image_keys(self,imageListUuid, imageUuid):
        Session = self.SessionFactory()
        query_imagekeys = Session.query(model.ImageMetadata).\
                filter(model.Imagelist.identifier == imageListUuid).\
                filter(model.Imagelist.id == model.Image.fkImageList).\
                filter(model.Image.identifier == imageUuid)
        if query_imagekeys.count() == 0:
            self.log.warning('no details found')
            return None
        for item in query_imagekeys:
            print "'%s' : '%s'" % (item.key,item.value)
        return True

    def imageAdd(self,UUID):
        Session = self.SessionFactory()
        query_imagelists = Session.query(model.Image).\
                filter(model.Image.identifier == UUID )
        if query_imagelists.count() > 0:
            self.log.warning('Image already exists')
            return False
        newImage = model.Image(UUID)
        Session.add(newImage)
        Session.commit()
        return True   

    def imageDelete(self,ImageUUID):
        Session = self.SessionFactory()
        query_imagelists = Session.query(model.Image).\
               filter(model.Image.identifier == ImageUUID)
        NoItems = True
        for item in query_imagelists:
            NoItems = False
            Session.delete(item)
        if not NoItems:
            Session.commit()
            return True
        else:
            self.log.info("No items deleted")
        return False

    def importer(self,dictInput):
        if not 'hv:imagelist' in dictInput.keys():
            self.log.error("JSON is not a 'hv:imagelist'")
            return False
        content = dictInput['hv:imagelist']
        if not 'dc:identifier' in content.keys():
            self.log.error("Imagelists does not contain a 'dc:identifier'")
            return False
        identifier = content['dc:identifier']
        self.imageListAdd(identifier)
        for key in content.keys():
            if key in ['dc:identifier','hv:endorser','hv:images']:
                continue
            if isinstance(content[key], str):
                self.imagelist_key_update(identifier, key,content[key])
        if 'hv:images' in content.keys():
            for image in content['hv:images']:
                if not 'hv:image' in image.keys():
                    self.log.warning("ignoring image '%s'" % (image))
                    continue
                imagecontent = image['hv:image']
                if not 'dc:identifier' in imagecontent.keys():
                    self.log.warning("image has no ID '%s'" % (image))
                    continue
                imageIdentifier = imagecontent['dc:identifier']
                self.imageAdd(imageIdentifier)
                self.imageListImageConnect(identifier, imageIdentifier)
                for key in imagecontent.keys():
                    if key in ['dc:identifier']:
                        continue
                    self.image_key_update( imageIdentifier ,key,imagecontent[key] )
        if 'hv:endorser' in content.keys():
            # make endorsers a list under all cases.
            endorsersAll = [content['hv:endorser']]
            if type(content['hv:endorser']) is types.ListType:
                endorsersAll = content['hv:endorser']
            for endorser in endorsersAll:
                if not 'hv:x509' in endorser.keys():
                    self.log.error("Error processing '%s' so ignoring" % (endorser))
                    continue
                endorserDetails = endorser['hv:x509']
                if not 'hv:dn' in endorserDetails.keys():
                    self.log.error("Error finding DN in '%s' so ignoring" % (endorserDetails))
                    continue
                endorserSubject = endorserDetails['hv:dn']
                self.endorserAdd(endorserSubject)
                self.imageListEndorserConnect(identifier,endorserSubject)
                for key in endorserDetails.keys():
                    if key in ['hv:dn']:
                        continue
                    value = endorserDetails[key]
                    self.endorserMetadataUpdate(endorserSubject,key,value)
        for key in content.keys():
            if key in ['hv:endorser' , 'hv:images' ,'dc:identifier']:
                continue
            value = content[key]
            self.imagelist_key_update(identifier,key,value)
        return True        


    def checkMissingFields(self,imagelistUUID,subject,issuerSub):
        content = self.imageListShow(imagelistUUID)
        if content == None:
            self.log.error("Image list '%s' could not be retrived." % (imagelistUUID))
            return False
        if not 'hv:imagelist' in content.keys():
            self.log.error("Image list is not well defined for '%s'" % (imagelistUUID))
            return False
        imageliststuff = content['hv:imagelist']
        imagelistKeys = imageliststuff.keys()
        missingImageListMetaData = imagelist_required_metadata_set.difference(imagelistKeys)
        if len(missingImageListMetaData) > 0:
            self.log.error("Image list metadata was missing for '%s'." % (imagelistUUID))
            for item in missingImageListMetaData:
                self.log.error("Please add '%s' to the image list metadata." % (item))
            return False
        if "hv:images" in imagelistKeys:
            # We have images
            imagesfromImageList = imageliststuff["hv:images"]
            for imageRawDetails in imagesfromImageList:
                if not 'hv:image' in imageRawDetails.keys():
                    self.log.error("Image has an invalid format.")
                    return False
                imageDetails = imageRawDetails['hv:image']
                imageKeys = imageDetails.keys()
                if not "dc:identifier" in imageKeys:
                    self.log.error("Image list has an image without an identifier.")
                    print imageKeys
                    return False
                imageIdentifier = imageDetails["dc:identifier"]
                missingImageMetaData = image_required_metadata_set.difference(imageKeys)
                if len(missingImageMetaData) > 0:
                    self.log.error("Image metadata is missing for '%s'." % (imageIdentifier))
                    for item in missingImageMetaData:
                        self.log.error("Please add '%s' to the metadata for image '%s'." % (item,imageIdentifier))
                    return False
        if not "hv:endorser" in imagelistKeys:
            self.log.error("No endorsers found in '%s'." % (imagelistUUID))
            return False
        else:
            #we have endorsers
            endorserUntypedList = imageliststuff["hv:endorser"]
            
            if type(endorserUntypedList) is dict:
                endorserUntypedList = [endorserUntypedList]
            if len(endorserUntypedList) == 0:
                self.log.error("No endorsers found.")
                return False
            foundEndorser = False
            for endorserItem in endorserUntypedList:
                if not 'hv:x509' in endorserItem.keys():
                    self.log.error("Enderser is invalid '%s'." % (endorserItem))
                    return False
                endorserDetails = endorserItem["hv:x509"]
                reqMetaData = endorser_required_metadata_set.difference(endorserDetails.keys())
                if len(reqMetaData) > 0:
                    self.log.error("Image metadata is missing for '%s'." % (endorserDetails))
                    for item in reqMetaData:
                        self.log.error("Please add '%s' to the metadata for endorser '%s'." % (item,endorserDetails))
                    return False
                if endorserDetails["hv:dn"] == subject and endorserDetails["hv:ca"] == issuerSub:
                    foundEndorser = True
            if not foundEndorser:
                self.log.error("Could not find an endorser matching your certificate '%s' issued by '%s'." % (subject,issuerSub))
                return False
        return True
