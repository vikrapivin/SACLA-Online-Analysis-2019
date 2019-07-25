# Online analysis of large array detectors and point detectors at SACLA

## Contributions by Matthew Ware, Takahiro Sato, Kathryn Ledbetter, and Jordan O'Neal

## Summary of online analysis:
Tools enable fast feedback during experiments. 
The primary library is onlineAccess.py.
Including in this repository are samples for accessing the large array detectors and the point detectors

### Online analysis at SACLA
Online analysis is available on the xu-bl1-anapc01, xu-bl1-anapc02, xu-bl2-anapc01, xu-bl2-anapc02,  xu-bl3-anapc01, and xu-bl3-anapc02.
Only the server corresponding to your beamline can access the data. 
For data intensive experiments, split analysis across anapc01 and anapc02.

### Accessing the server
The server can only be accessed on the opcon computers outside of the experimental hutches. 
To login, SSH via
```bash
ssh -Y USERNAME@xu-bl3-anapc01
```
where xu-bl3-anapc01 should be substituted with the appropriate server for your beamline.

### Installing the software
First FTP the git repository to xhpcfep.hpc.spring8.or.jp using the hpcwshost-01.hpc.spring8.or.jp network.
Also, you'll need to FTP an installation of python to this server. Use Anaconda3-2019.03-Linux-x86_64, available online.

The anapcs can contact this server. 
To copy the data from this server, go to the opcon computer and run 
```bash
ssh -Y USERNAME@xu-bl3-anapc01
scp -r USERNAME@xhpcfep.hpc.spring8.or.jp:PATHTOFILE/GITREPO .
scp -r USERNAME@xhpcfep.hpc.spring8.or.jp:PATHTOFILE/ANACONDA .
chmod +x ANACONDA.sh
./ANACONDA.sh # Installs python and libraries
logout
ssh -Y USERNAME@xu-bl3-anapc01
jupyter notebook # Opens a jupyter notebook for running the sample scripts in the git repo
```

### onlineAccess.py

This library defines the online data access libraries and functions. 
Examples of how to use it are including in the Jupyter notebooks.

### Point detector and ROI analysis
pointdet-and-roi-analysis.ipynb

This notebook walks you through initializing the dataHandling thread, and grabbing data from the online servers.
It also shows you how to plot that data in realtime. 
The plot updates at a 1-2 second interval depending on your setting for `ngrab` and `plotEvery`.

### Full array detector analysis
array-detector-analysis.ipynb

While pointdet-and-roi-analysis.ipynb walks you through the use of regions of interest (ROIs), the array-detector-analysis.ipynb notebook walks you through grabbing the entire detector image.

This code only works if the detector exists in the datastream. 
If the detector does not exist, it will crash.
If you want to test the code before the detector is installed in the hutch, there exists an anapc simulator on the HPC computers.

### ROIs selected Graphically by Users
operatorROI.py

This file must be reconfigured for a particular experiment by editing the name of the detector as well as the name of the I0 point detector.

This file retrieves 10 images by default using onlineAccess and the method in array-detector-analysis above. It then allows the user to draw an ROI. Once the ROI is selected the program retrieves the current detector image as often as possible, associated point detectors with the image and processes the data in one python process and ques it for graphing in another python process. The data is averaged until the plotting window is closed.

There are plans to improve this method for a future SACLA experiment using more retrieval processes and other worker threads that will process the data separately from the thread that grabs the data. This was simply a proof of concept.
