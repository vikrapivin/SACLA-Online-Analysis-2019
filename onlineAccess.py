'''
onlineAccess.py

by Matthew Ware, Takihiro Sato, Kathryn Ledbetter, and Jordan O'Neal

'''

# The MPCCD threshold value for no photons is fairly static. This should not need to be editted.
thresholdValue = 1000./3.65
#thresholdValue = -1000 # Set to negative to do no thresholding
print('MPCCD threshold is set to %f' % thresholdValue)

if thresholdValue < 1e-15:
    print('WARNING MPCCD IS NOT BEING THRESHOLDED')


###################################################################################################################
# Import required libraries
###################################################################################################################

import os, io, time, sys, socket
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# SACLA database library and online analysis library
sys.path.append('/home/software/SACLA_tool/local/python3.5/lib/python3.5/site-packages')
import dbpy, olpy

# Redirect output
from contextlib import contextmanager


###################################################################################################################
# Useful function definitions
###################################################################################################################

def merge_dictionaries( *args ):
    '''
    merges arbitrary number of dictionaries into a single dictionary
    input: dict1, dict2, dict3, ...
    output: merged dictionary
    '''
    z = {}
    for arg in args:
        # TODO: ensure that different dictionaries to not contradict each other
        z.update( arg )
    return z

@contextmanager
def custom_redirection(fileobj):
    old = sys.stdout
    sys.stdout = fileobj
    try:
        yield fileobj
    finally:
        sys.stdout = old

def logPrint(astring):
    f = open('onlineAccess.log','a+')
    f.write(astring+'\n')
    f.close()
    

###################################################################################################################
# dbpy access - ie database access
###################################################################################################################

def getEquip( tags , equip , hightag=201802 ):
    '''
    returns data from detector for specified tags, hightag
    input:
        tags: tuple of integer values
        equip: equipment name
        hightag: high tag integer value 
    output: detector value accross tags as float
    '''
    try:
        equipVals = dbpy.read_syncdatalist_float( equip, hightag , tags )
        return equipVals
    except Exception as e:
        logPrint(str(e))
        return np.nan

def getEquipInt( tags , equip , hightag=201802 ):
    '''
    returns data as integer from detector for specified tags, hightag
    input:
        tags: tuple of integer values
        equip: equipment name
        hightag: high tag integer value 
    output: detector value accross tags as integer
    '''
    return dbpy.read_syncdatalist( equip, hightag , tags )

def getNewestTag( equip ):
    '''
    returns newest low tag value
    input: detector to serve as reference to get tag value
    output: newest low tag value
    '''
    newtag = dbpy.read_tagnumber_newest( equip )
    return newtag[1]

def getNewestRun( bl ):
    '''
    returns newest run number for the beamline
    input: beamline as integer
    output: runnumber as integer
    '''
    return dbpy.read_runnumber_newest( bl )

def getDetectorList( bl , run ):
    '''
    returns available detector list for current beamline and run number
    Detectors are cameras like the MPCCD
    input: beamline and runnumber as integers
    output: tuple list of detector names
    '''
    return dbpy.read_detidlist( bl , run )

def getCurrentDetectorList( bl ):
    '''
    returns available detector list for current beamline and newest run number
    Detectors are cameras like the MPCCD
    input: beamline as integer
    output: tuple list of detector names
    '''
    return dbpy.read_detidlist( bl , getNewestRun(bl) )

def getEquipmentList(  ):
    '''
    returns available list of equipment 
    input: None
    output: tuple list of equipment names
    '''
    return dbpy.read_equiplist(  )

def getHighTag( bl , run ):
    '''
    returns high tag value for particular beamline and run number
    input: beamline and runnumber as integers
    output: high tag value as integer
    '''
    return dbpy.read_hightagnumber( bl , run )

def getCurrentHighTag( bl ):
    '''
    returns current high tag value for current beamline
    input: beamline
    output: hightag value
    '''
    return dbpy.read_hightagnumber( bl , getNewestRun(bl) )

def getEndTag( bl , run ):
    '''
    find last tag in a run
    input: beamline and runnumber as integers
    output: last low tag in run
    '''
    return dbpy.read_end_tagnumber( bl , run )

def getStartTag( bl , run ):
    '''
    find first tag in a run
    input: beamline and runnumber as integers
    output: first low tag in run
    '''
    return dbpy.read_start_tagnumber( bl , run )

def getTagRange( bl , run ):
    '''
    find tag range for a run
    input: beamline and runnumber as integers
    output: start tag, end tag
    '''
    return getStartTag(bl,run) , getEndTag(bl,run)

def getNewestHighTag( bl ):
    '''
    find newest high tag value for beamline
    input: beamline
    output: newest high tag value
    '''
    try:
        run = getNewestRun( bl )
        startTags = getStartTag( bl , run )
        return startTags[0]

    except Exception as e:
        logPrint('Could not get newest hightag. Defaulting to 201901. Error was '+str(e))
        return 201901






###################################################################################################################
# Grabbing data and camera rois
###################################################################################################################

def grabPointData( pointDetectors , tags , hightag=201802 ):
    '''
    Grabs the point detector / equipment read out for each equipment in the pointDetector array of strings for each tag
    input:
        pointDetectors: list of strings, e.g. ['xfel_bl_3_st_5_direct_bm_1_pd/charge','xfel_bl_3_shutter_1_open_valid/status']
        tags: tuple of integers containing the low tag value
        hightag: hightag integer
    output: 
        readout for each detector for each tag
    '''
    pointData = { pd:{'Data':getEquip( tags , pd , hightag=hightag )} for pd in pointDetectors }
    pointData['tags'] = tags
    return pointData

def grabNewestPointData( pointDetectors , ngrab=30, bl=3 , refDet='xfel_bl_3_tc_bm_2_pd/charge', lowestTag2Grab=None ):
    '''
    Grabs the most recent point data
    input:
        pointDetectors: list of strings, e.g. ['xfel_bl_3_st_5_direct_bm_1_pd/charge','xfel_bl_3_shutter_1_open_valid/status']
        ngrab: integer number of runs to grab
        bl: integer beamline
        refDet: which detector to use to get newest tag number
        lowestTag2Grab: prevents grabbing beyond a certain tag, i.e. you don't want to double grab from a previous request
    output: 
        readout for each detector for each of the ngrab tags
    '''
    hightag = getNewestHighTag( bl )
    tagf = getNewestTag( refDet )    
    tagLow = tagf-ngrab
    if lowestTag2Grab is not None:
        if tagLow <= lowestTag2Grab:
            tagLow = lowestTag2Grab + 1
    tags = tuple([ idx for idx in range(tagLow, tagf)])
    return grabPointData( pointDetectors , tags , hightag=hightag )

def makeDataFrame( pointData ):
    '''
    Converts data and roi dictionaries into pandas dataframe with the tag numbers as indexes
    '''
    data={}
    for pid in pointData.keys():
        if pid is not 'tags':
            data[pid] = np.array(pointData[pid]['Data'])
    index = pointData['tags']
    return pd.DataFrame( index=index, data=data )

def grabDetector(det, tags, hightag=201802):
    '''
    Grabs the detector object at the tags
    NOTE: The detector objects quickly leave memory. This cannot be used to look at old images.
    input:
        det: detector name
        tags: tuple of integers containing the low tag value
        hightag: high tag integer value
    output:
        detector: Size is [ntags, NX, NY, NZ...]
    '''
    objReader = olpy.StorageReader(det)
    objBuffer = olpy.StorageBuffer(objReader)
    
    initialized = False
    errorCount = 0
    isMPCCD = False
    
    for idx, tag in enumerate(tags):
      try:
        realtag = objReader.collect(objBuffer, tag)
        detArray = objBuffer.read_det_data(0)
        detInfo = objBuffer.read_det_info(0)
        try:
            gain = np.copy(detInfo['mp_absgain'])
            isMPCCD = True
        except KeyError as ex:
            gain = 1
        if not initialized:
            detArrays = np.zeros( ( len(tags), ) + detArray.shape )
        detArrays[idx,:,:] = np.copy(detArray) * gain
      except Exception as ex:
        logPrint(str(ex))
        errorCount +=1

    logPrint('Errored on %d of %d tags'%( errorCount , len(tags) ))
        
    if isMPCCD:
        detArrays[detArrays < thresholdValue] = 0.
    return detArrays

def grabNewestDetector(det, bl, refDet='xfel_bl_3_st_5_direct_bm_1_pd/charge'):
    '''
    Grabs the newest detector image
    input:
        det: detector name
        bl: beamline as integer value
        refDet: reference det to get current tag value
    output:
        detector: Size is [NX, NY, NZ...]
    '''
    
    tag = [getNewestTag(refDet)]
    hightag= getNewestHighTag(bl)
    detArray = grabDetector(det, tag, hightag=hightag)  

    return np.squeeze(detArray), tag[0], hightag

def grabROI(det, tags, X1, X2, Y1, Y2, 
                 hightag=201802):
    '''
    Caslculates roi of detector across tags
    input:
        det: detector name
        tags: tags to grab detector image on
        X1, Y1:lowert indexes of ROI
        X2: Y2: upper indexes of ROI
        hightag: hightag integer
    output:
        roi value across tags
    '''
    objReader = olpy.StorageReader(det)
    objBuffer = olpy.StorageBuffer(objReader)
    
    detROIs = np.array([0. for tag in tags])

    errorCount = 0
    
    for idx, tag in enumerate(tags):
      try:
        realtag = objReader.collect(objBuffer, tag)
        detArray = (objBuffer.read_det_data(0)) 
        detInfo = objBuffer.read_det_info(0)
        try:
            gain = np.copy(detInfo['mp_absgain'])
            detArray = detArray*gain
            detArray[detArray<thresholdValue] = 0.
        except KeyError as ex:
            gain = 1.
        NX,NY = detArray.shape
        #if X2 > NX:
        #    detROIs[idx] = 0
        #    continue
        #if Y2 > NY:
        #    detROIs[idx] = 0
        #    continue
        detROIs[idx] = np.nansum( detArray[X1:X2,Y1:Y2] ) 
      except Exception as ex:
        #raise ex
        logPrint(str(ex))
        errorCount +=1

    logPrint('Errored on %d of %d tags'%( errorCount , len(tags) ))
        
    return detROIs

def grabROIData( rois , tags , hightag=201802 ):
    '''
    Calculates roi for each roi in the suppled dictionary
    input:
        rois: dictionary of rois like 
            rois = { 'ROI1': {'Detector':'MPCCD-1-1-010',
                 'X1':1,
                 'X2':10,
                 'Y1':1,
                 'Y2':10} }   
        tags: tags to grab values across
        hightag: hightag integer
    output:
        returns every roi value across the tags
    '''
    roiData = {}
    for roi in rois.keys():
        det = rois[roi]['Detector']
        X1 = rois[roi]['X1']
        X2 = rois[roi]['X2']
        Y1 = rois[roi]['Y1']
        Y2 = rois[roi]['Y2']
        roiData[roi] = { 'Data':grabROI(det, tags, X1, X2, Y1, Y2, hightag=hightag), 'Detector':det, 'X1':X1, 'X2':X2, 'Y1':Y1, 'Y2':Y2 }
    roiData['tags'] = tags
    return roiData

def grabNewestROIData( rois , ngrab=30, bl=3 , refDet='xfel_bl_3_tc_bm_2_pd/charge', lowestTag2Grab=None ):
    '''
    Grabs the most recent roi data
    input:
        rois: dictionary of rois like 
            rois = { 'ROI1': {'Detector':'MPCCD-1-1-010',
                 'X1':1,
                 'X2':10,
                 'Y1':1,
                 'Y2':10} } 
        ngrab: integer number of runs to grab
        bl: integer beamline
        refDet: which detector to use to get newest tag number
        lowestTag2Grab: prevents grabbing beyond a certain tag, i.e. you don't want to double grab from a previous request
    output: 
        readout for each detector for each of the ngrab tags
    '''
    hightag = getNewestHighTag( bl )
    tagf = getNewestTag( refDet )    
    tagLow = tagf-ngrab
    if lowestTag2Grab is not None:
        if tagLow <= lowestTag2Grab:
            tagLow = lowestTag2Grab + 1
    tags = tuple([ idx for idx in range(tagLow, tagf)])
    return grabROIData( rois , tags , hightag=hightag )

def grabNewestData( pointDetectors, rois , 
                   ngrab=30, bl=3 , refDet='xfel_bl_3_tc_bm_2_pd/charge',
                   lowestTag2Grab = None):
    '''
    Grabs the most recent point and roi data
    input:
        pointDetectors: list of strings, e.g. ['xfel_bl_3_st_5_direct_bm_1_pd/charge','xfel_bl_3_shutter_1_open_valid/status']
        rois: dictionary of rois like 
            rois = { 'ROI1': {'Detector':'MPCCD-1-1-010',
                 'X1':1,
                 'X2':10,
                 'Y1':1,
                 'Y2':10} } 
        ngrab: integer number of runs to grab
        bl: integer beamline
        refDet: which detector to use to get newest tag number
        lowestTag2Grab: prevents grabbing beyond a certain tag, i.e. you don't want to double grab from a previous request
    output: 
        readout for each detector for each of the ngrab tags
    '''
    hightag = getNewestHighTag( bl )

    tagf = getNewestTag( refDet )    
    tagLow = tagf-ngrab
    if lowestTag2Grab is not None:
        if tagLow <= lowestTag2Grab:
            tagLow = lowestTag2Grab + 1
    tags = tuple([ idx for idx in range(tagLow, tagf)])
    if len(tags) == 0:
        return None
    roiDataDicts  = grabROIData( rois , tags , hightag=hightag)
    pointDataDicts = grabPointData( pointDetectors , tags , hightag=hightag )
    pointDataDicts.pop( 'tags' , None )
    return merge_dictionaries( roiDataDicts, pointDataDicts )





###################################################################################################################
# Use threaded class to load data in queue
###################################################################################################################

import threading
import collections

class dataHandler(threading.Thread):
	'''
		Generates a thread to pull in the point detector variables asynchronously with plotting.
	'''
    def __init__(self, bl=3, refDet='xfel_bl_3_tc_bm_2_pd/charge', ngrab=120, maxTags2Save = 2000):
		'''
			Initializes the thread. 
			input:
				bl: beamline number as integer
				refDet: detector to use as a reference for tag number
				ngrab: number of tags to grab at a time. 120 seems optimal.
				maxTags2Save: number of event information to store at a time
		'''
        threading.Thread.__init__(self)
        self.lock=threading.Lock()
        self.stopped = False
        self.isPaused = False
        self.pauseRequested = False
        self.newestTag = None
        self.dequeDicts = {'tags': collections.deque([np.nan],maxTags2Save), 'dummy':collections.deque([1],maxTags2Save)}
        
        self.ngrab = ngrab
        self.bl= bl
        self.refDet= refDet
        
        self.totalGrabbed = 0
        self.status = 'Waiting for initialization'
        self.last_status = 'Waiting for initialization'
        
        self.t0 = time.time()        
        self.saveAtTag = None
        self.maxTags2Save = maxTags2Save

        self.rois = {}
        self.pointDetectors = {}
        
    def setPointDetector(self, pointDetectors):
		'''
			Declare the pointdetectors you'd like to extract during the experiment.
			input:
				pointDetectors: list of strings, e.g. ['xfel_bl_3_st_5_direct_bm_1_pd/charge','xfel_bl_3_shutter_1_open_valid/status']
		'''
        self.pointDetectors = pointDetectors
        
        dequeDictPD = { pd : collections.deque([np.nan],self.maxTags2Save) for pd in self.pointDetectors}
        self.dequeDicts = merge_dictionaries( self.dequeDicts, dequeDictPD )
        
        self.status += ', point detectors initialized'
    
    def setROIs(self, rois):
		'''
			Declare the ROIs to use in the experiment.
			input:
				rois: dictionary of rois like 
						rois = { 'ROI1': {'Detector':'MPCCD-1-1-010',
							 'X1':1,
							 'X2':10,
							 'Y1':1,
							 'Y2':10} } 
		'''
        self.rois = rois

        try:
            availDets = getCurrentDetectorList(self.bl)
        except Exception as ex:
            print('Original error was '+str(ex))
            raise Exception('Detectors likely not setup for newest run. Try not setting rois.')            
                
        for roiName in rois.keys():
            if rois[roiName]['Detector'] not in availDets:
                raise ValueError('Detector %s not available' % rois[roiName]['Detector'])
        
        dequeDictROIs = { roiName : collections.deque([np.nan],self.maxTags2Save) for roiName in rois.keys()}
        self.dequeDicts = merge_dictionaries( self.dequeDicts, dequeDictROIs )
        
        self.status += ', rois initialized'
        
    def run(self):
		'''
			Main thread. Begin by running dh.start(), where dh is the initialized dataHandler object.
		'''
        self.status += ', running'
        self.last_status = 'running'
        while self.stopped is not True:
            t0=time.time()
            if self.stopped: break
            while self.pauseRequested:
                self.isPaused = True
            self.isPaused = False               


            #with open('/xnas/xufs06/mrware/TAIS2019/grabber.out', 'w+') as out:
            #    with custom_redirection(out):
            data = grabNewestData( self.pointDetectors, self.rois, ngrab=self.ngrab, 
            lowestTag2Grab=self.newestTag, bl=self.bl, refDet=self.refDet )
            if data is None:
                continue
            
            if len(data['tags'])<=0: 
                continue
            else:
                self.newestTag=max(data['tags'])
            self.totalGrabbed =  len(self.dequeDicts['tags'])
            self.updateDeques( data )
            while time.time()-t0 < self.ngrab/30.+1./30.:
                continue
            
        self.status += ', run completed.'
        self.last_status = 'run completed'

    def pause(self):
		'''
		Requests a pause in execution of the thread.
		Before accessing stored data, wait for self.isPaused eg dh.isPaused to return True.
		'''
        self.pauseRequested = True

    def restart(self):
		'''
		Restarts execution following a pause.
		'''
        self.pauseRequested = False

    @property
    def elapse(self):
		'''
		Returns the total execution time of the thread.
		'''
        return time.time()-self.t0

    def updateDeques(self, data):
		'''
		Updates the stored data using the data returned from grabNewestData(...)
		Called within thread. Not for user use.
		'''
        self.lock.acquire()
        for key in data.keys():
            if 'tags' in key:
                self.dequeDicts[key].extend(np.copy(data[key]))
                self.dequeDicts['dummy'].extend(np.ones_like(np.array(data[key])))
            else:           
                self.dequeDicts[key].extend( np.copy(data[key]['Data']) )
        self.lock.release()

    def keys(self):
		'''
		Returns the detectors and ROIs being stored.
		'''
        return self.dequeDicts.keys()

    def __getitem__(self,key):
		'''
		Returns the data stored in the deque.
		'''
        self.lock.acquire()
        data=np.copy(self.dequeDicts[key])
        self.lock.release()
        return data

    def requestStop(self):
		'''
		Requests termination of thread.
		'''
        self.stopped = True
        
    def printStatus(self):
		'''
		Prints current status of thread.
		'''
        if 'running' in self.status:
            print(self.status+'. # tags grabbed = '+str(self.totalGrabbed))
        else:
            print(self.status)
        
    def lastStatus(self):
		'''
		Returns last status of thread.
		'''
        return self.last_status+': '+str(self.totalGrabbed)
