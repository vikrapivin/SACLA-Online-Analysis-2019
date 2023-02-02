'''
    An example of how to see SACLA data in real time at a graphically specified ROI
    Uses the roipoly class
    Only tested at bl3_eh2, your mileage will vary
    This is a truly paralleled process
    Contributors: Viktor Krapivin and Peihao Sun.
    Based from SACLA Online Analysis 2019 by Matthew Ware, Takihiro Sato, Kathryn Ledbetter, and Jordan O'Neal
'''

import os, io, time, sys, socket
import numpy as np
import pandas as pd

# SACLA database library and online analysis library
sys.path.append('/home/software/SACLA_tool/local/python3.5/lib/python3.5/site-packages')
import dbpy, olpy

# Import custom online library
import onlineAccess


# Plot options
import matplotlib
matplotlib.rcParams['backend']='Qt5Agg'
matplotlib.use('Qt5Agg')

import matplotlib.pyplot as plt
import matplotlib.widgets as widgets

from roipoly import RoiPoly

import multiprocessing
import time

'''
    A method to display the ROI given ax. The display_roi method in the RoiPoly package does
    not support display an ROI unless the graph that displays it is returned by plt.gca()
'''
def display_roi(roi_disp, ax, **linekwargs):
    line = plt.Line2D(roi_disp.x + [roi_disp.x[0]], roi_disp.y + [roi_disp.y[0]],
                          color=roi_disp.color, **linekwargs)
    ax.add_line(line)

NX = 512
NY = 1024

def grabDetector( detectorName, bl=3, refDet='xfel_bl_3_tc_bm_2_pd/charge' ):
    if detectorName is 'debug':
        dummyTag = onlineAccess.getNewestTag('xfel_bl_3_tc_bm_2_pd/charge' )
        dummyHightag = onlineAccess.getCurrentHighTag(3)
        return dummyTile(), dummyTag, dummyHightag
    else:
        return onlineAccess.grabNewestDetector(detectorName, bl, refDet=refDet)

def getStatus(tag, hightag):
    machineStatusName = 'xfel_mon_bpm_bl3_0_3_beamstatus/summary'
    status = onlineAccess.getEquip( (tag,), equip=machineStatusName, hightag=hightag)
    return(status[0]>0.1)

def returnTenFrames( detectorName , integrateOver = 100):
    intMPCCD = np.zeros( (NY,NX) )
    nframes = 0
    tag = 0
    for idx in range(integrateOver):
        detFrame, tag, hightag = grabDetector(detectorName)

        if getStatus(tag,hightag) is False:
            continue

        nframes += 1.
        intMPCCD += detFrame*3.65
        time.sleep(1./29.)

    tenFrames =  (intMPCCD/nframes)
    return tenFrames, tag

def isData( anArray ):
    return (np.abs(anArray)>0) & (~np.isnan(anArray))

def bindata(xx, yy, binstart, binend, bins=50):
    edges = np.linspace(binstart, binend, bins+1)
    counts, _ = np.histogram(xx, bins=edges)
    print(xx)
    print(yy)
    print(edges)
    sums, throwaway = np.histogram(xx, bins=edges, weights=yy)
    centers = 0.5 * (edges[:-1] + edges[1:])
    return sums * 1./counts, centers, np.sum(xx<edges[0])+np.sum(xx>edges[-1])

# bin shots Here
'''
    Copyright 2019 by Viktor Krapivin, claimed only on the class binROI.
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''
class binROI(multiprocessing.Process):
    
    def __init__(self, result_queue, detector, tagStart, startBin, endbin, mask, roiBins, t0offset):
        multiprocessing.Process.__init__(self)
        self.result_queue = result_queue
        self.tagStart = tagStart
        self.mask = mask
        self.detector = detector
        self.roiBins2 = roiBins
        self.starterBin = startBin
        self.enderbin = endbin
        self.nomDelayOff = t0offset


    def run(self):
        proc_name = self.name
        while True:
            detArrer, curTag, hightager = onlineAccess.grabNewestDetector(self.detector, 3, refDet='xfel_bl_3_st_5_direct_bm_1_pd/charge')
            if(curTag == self.tagStart):
                #if you are having problems, you could try uncommenting below and adjusting sleep time but not required
                #time.sleep(0.005)
                continue
            self.tagStart = curTag
            #read some point detectors that are from the same tag # as retreived above.
            detReading = onlineAccess.grabPointData(['xfel_bl_3_st_2_pd_user_5_fitting_peak/voltage', 'xfel_mon_bpm_bl3_0_3_beamstatus/summary', 'xfel_bl_3_st_2_motor_1/position'], (curTag,) , hightag=hightager)
            i0det = detReading['xfel_bl_3_st_2_pd_user_5_fitting_peak/voltage']
            i0det = i0det['Data']
            i0det = np.array(i0det)
            beamStatus = detReading['xfel_mon_bpm_bl3_0_3_beamstatus/summary']
            beamStatus = beamStatus['Data']
            beamStatus = np.array(beamStatus)
            nominalDelay = detReading['xfel_bl_3_st_2_motor_1/position']
            nominalDelay = nominalDelay['Data']
            nominalDelay = np.array(nominalDelay)
            idxs = isData(beamStatus) & (i0det > 0.01)
            idxs = idxs.ravel() # this and some commands below probably should be scrutinized for performance; this is a hack used to get the variable in the right data structure
            nominalDelay_ps = nominalDelay* 6.666e-3 - self.nomDelayOff
            detArraysROI = np.sum(detArrer[self.mask])
            detArraysROI = np.copy(np.array(detArraysROI).ravel())
            if idxs[0]>0:
                binROIs, bin_nomDel, testor = bindata(nominalDelay_ps, detArraysROI, self.starterBin, self.enderbin, bins=self.roiBins2)
                whereIsNaN = np.isnan(binROIs)
                binROIs[whereIsNaN] = 0
            else:
                binROIs = 0
                binInts = 0
                bin_nomDel = 0
            self.result_queue.put_nowait((binROIs, bin_nomDel, idxs.sum(), i0det, beamStatus, detArraysROI,curTag))
            self.tagStart = curTag
        #once again below can be uncommented and adjusted, but there is no loss in performance unless you are running many other programs on anapc.
        #not sleeping will just use up one core of processing on the anapc
        # not a problem as this loop is running on a different core than the loop below
        #time.sleep(0.005)
        return
#class Task(object):

if __name__ == '__main__':
    results = multiprocessing.Queue()
    
    # configure below for your experiment
    detectorName = 'MPCCD-8N0-3-002-6'
    integrateOver = 10
    t0offset = -10
    
    fig = plt.figure()
    tenFrames, curTag = returnTenFrames(detectorName, integrateOver = integrateOver)
    plt.imshow(tenFrames)
    my_roi = RoiPoly(color='r', fig=fig)
    plt.imshow(tenFrames)
    my_roi.display_roi()
    mask = my_roi.get_mask(tenFrames)
    
    #binning parameters
    roiBins = 40
    startBin = -2.0
    endbin = 3.0
    binCounterBin = np.zeros(roiBins)
    
    binTheData = binROI(results, detectorName, curTag, startBin, endbin, mask, roiBins, t0offset)
    binTheData.start()
    binROIs = np.zeros(roiBins)
    bin_nomDel = np.zeros(roiBins)
    i0det = 0
    beamStatus = 0
    detArraysROIs = 0
    tagSel = 0
    totalShots = 0
    
    fig, (ax1, ax2, ax3) =plt.subplots(3, 1)
    plt.axis('off')
    fig.show()
    figure_open=True
    photonEnergykeV = 13.8
    graphingInit = False
    # close event handler and figure open are inspired by array-detector-analysis.ipynb by Matthew Ware
    # Tells loop to exit if the figure is closed
    def close_event_handler(evt):
        global figure_open
        figure_open=False
        print("closed figure")
    fig.canvas.mpl_connect('close_event',close_event_handler)
    while figure_open:
        if results.empty() is True:
            plt.pause(0.001)
            continue
        binROIsTemp, bin_nomDelTemp, shotsInBin, i0detTemp, beamStatusTemp, detArraysROIsTemp, tagSelTemp = results.get()
        if shotsInBin < 1:
            pass
        else:
            graphingInit = True
            binAddMask = (binROIsTemp>0)
            binROIs[binAddMask] = np.divide((np.multiply(binROIs[binAddMask],binCounterBin[binAddMask]) + binROIsTemp[binAddMask] ), binCounterBin[binAddMask]+1)
            #binCounterBin[binAddMask] = binCounterBin[binAddMask] + 1 # works but below should be better if binROI is rewritten to get more than 1 event
            binCounterBin =  np.add(binCounterBin[binAddMask], binROIsTemp)
            bin_nomDel = bin_nomDelTemp
            totalShots = totalShots + shotsInBin
        if type(i0det) is int:
            # turn integers into 1D arrays
            i0det = np.copy(i0detTemp).ravel()
            beamStatus = np.copy(beamStatusTemp).ravel()
            detArraysROIs = np.copy(detArraysROIsTemp).ravel()
            tagSel = np.copy(tagSelTemp).ravel()
        else:
            i0det = np.append(i0det, i0detTemp)
            beamStatus = np.append(beamStatus, beamStatusTemp)
            detArraysROIs = np.append(detArraysROIs, detArraysROIsTemp)
            tagSel = np.append(tagSel, tagSelTemp)
        idxs = isData(beamStatus)
        ax1.clear()
        ax1.scatter(i0det[idxs], detArraysROIs[idxs], s=3, c='b' )
        ax1.set_xlabel('I0')
        ax1.set_ylabel('ROI')
        
        ax2.clear()
        if graphingInit is True:
            ax2.plot(bin_nomDel, binROIs, 'o-')
            ax2.set_xlabel('nominal delay in ps, total {} shots'.format(idxs.sum()))
            ax2.set_ylabel('ROI')
        
        ax3.clear()
        ax3.scatter(tagSel[idxs], detArraysROIs[idxs], s=3, c='b' )
        ax3.set_xlabel('tags')
        ax3.set_ylabel('ROI')
        
        #t0 = time.time()
        print('next plot')
        #print(t0)
        
        fig.canvas.draw()
        plt.pause(0.001)
    binTheData.terminate()
    
