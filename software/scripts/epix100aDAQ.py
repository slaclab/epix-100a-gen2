#!/usr/bin/env python3
#-----------------------------------------------------------------------------
# This file is part of the rogue_example software. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the rogue_example software, including this file, may be
# copied, modified, propagated, or distributed except according to the terms
# contained in the LICENSE.txt file.
#-----------------------------------------------------------------------------
import setupLibPaths

import rogue.hardware.pgp
import pyrogue.utilities.prbs
import pyrogue.utilities.fileio
import pyrogue.gui
import surf
import surf.axi
import surf.protocols.ssi
import threading
import signal
import atexit
import yaml
import time
import sys
import testBridge
import ePixViewer as vi
import ePixFpga as fpga
import argparse

try:
    from PyQt5.QtWidgets import *
    from PyQt5.QtCore    import *
    from PyQt5.QtGui     import *
except ImportError:
    from PyQt4.QtCore    import *
    from PyQt4.QtGui     import *

    # Set the argument parser
parser = argparse.ArgumentParser()

# Convert str to bool
argBool = lambda s: s.lower() in ['true', 't', 'yes', '1']

# Add arguments
parser.add_argument(
    "--pollEn",
    type     = argBool,
    required = False,
    default  = False,
    help     = "Enable auto-polling",
)

parser.add_argument(
    "--initRead",
    type     = argBool,
    required = False,
    default  = False,
    help     = "Enable read all variables at start",
)

parser.add_argument(
    "--viewer",
    type     = argBool,
    required = False,
    default  = True,
    help     = "Start viewer",
)

parser.add_argument(
    "--gui",
    type     = argBool,
    required = False,
    default  = True,
    help     = "Start control GUI",
)

parser.add_argument(
    "--dev",
    type     = str,
    required = False,
    default  = '/dev/datadev_0',
    help     = "true to show gui",
)

parser.add_argument(
    "--lane",
    type     = int,
    required = False,
    default  = 0,
    help     = "PGP Lane",
)

parser.add_argument(
    "--verbose",
    type     = argBool,
    required = False,
    default  = False,
    help     = "Print debug info",
)

parser.add_argument(
    "--simulation",
    type     = argBool,
    required = False,
    default  = False,
    help     = "Connect to VCS simulation",
)

# Get the arguments
args = parser.parse_args()

#############################################
# Define if the GUI is started (1 starts it)
START_GUI = args.gui
START_VIEWER = args.viewer
#############################################
#print debug info
PRINT_VERBOSE = args.verbose
#############################################

# Create the PGP interfaces for ePix camera
if args.simulation:
    pgpVc0 = rogue.interfaces.stream.TcpClient('localhost',9000)
    pgpVc1 = rogue.interfaces.stream.TcpClient('localhost',9002)
    pgpVc2 = rogue.interfaces.stream.TcpClient('localhost',9004)
    pgpVc3 = rogue.interfaces.stream.TcpClient('localhost',9006)
else:
    pgpVc0 = rogue.hardware.axi.AxiStreamDma(args.dev,(args.lane*0x100)+0,True) # Data & cmds
    pgpVc1 = rogue.hardware.axi.AxiStreamDma(args.dev,(args.lane*0x100)+1,True) # Registers for ePix board
    pgpVc2 = rogue.hardware.axi.AxiStreamDma(args.dev,(args.lane*0x100)+2,True) # PseudoScope
    pgpVc3 = rogue.hardware.axi.AxiStreamDma(args.dev,(args.lane*0x100)+3,True) # Monitoring (Slow ADC)

# Add data stream to file as channel 1
# File writer
dataWriter = pyrogue.utilities.fileio.StreamWriter(name = 'dataWriter')
pyrogue.streamConnect(pgpVc1, dataWriter.getChannel(0x1))
# Add pseudoscope to file writer
pyrogue.streamConnect(pgpVc2, dataWriter.getChannel(0x2))
pyrogue.streamConnect(pgpVc3, dataWriter.getChannel(0x3))

#After git hash builds 9ac7dcd (8/4/2017) commands for epix camera can be sent on VC0 or VC2
#this is to fulfill a request by EUXFEL project.
cmd = rogue.protocols.srp.Cmd()
VC_NUM_ID = 0
if (VC_NUM_ID == 0):
   pyrogue.streamConnect(cmd, pgpVc1)
elif (VC_NUM_ID == 2):
   pyrogue.streamConnect(cmd, pgpVc2)
else:
    VC_NUM_ID = 0
    pyrogue.streamConnect(cmd, pgpVc1)

# Create and Connect SRP to VC0 to send commands
srp = rogue.protocols.srp.SrpV3()
srp == pgpVc0

#############################################
# Microblaze console printout
#############################################
class MbDebug(rogue.interfaces.stream.Slave):

    def __init__(self):
        rogue.interfaces.stream.Slave.__init__(self)
        self.enable = False

    def _acceptFrame(self,frame):
        if self.enable:
            p = bytearray(frame.getPayload())
            frame.read(p,0)
            print('-------- Microblaze Console --------')
            print(p.decode('utf-8'))

#######################################
# Custom run control
#######################################
class MyRunControl(pyrogue.RunControl):
    def __init__(self,name):
        pyrogue.RunControl.__init__(self,name, description='Run Controller ePix 100a',  rates={1:'1 Hz', 2:'2 Hz', 4:'4 Hz', 8:'8 Hz', 10:'10 Hz', 30:'30 Hz', 60:'60 Hz', 120:'120 Hz'})
        self._thread = None

    def _setRunState(self,dev,var,value,changed):
        if changed:
            if self.runState.get(read=False) == 'Running':
                self._thread = threading.Thread(target=self._run)
                self._thread.start()
            else:
                self._thread.join()
                self._thread = None


    def _run(self):
        self.runCount.set(0)
        self._last = int(time.time())


        while (self.runState.value() == 'Running'):
            delay = 1.0 / ({value: key for key,value in self.runRate.enum.items()}[self._runRate])
            time.sleep(delay)
            self._root.ssiPrbsTx.oneShot()

            self._runCount += 1
            if self._last != int(time.time()):
                self._last = int(time.time())
                self.runCount._updated()

##############################
# Set base
##############################
class EpixBoard(pyrogue.Root):
    def __init__(self, guiTop, cmd, dataWriter, srp, **kwargs):
        super().__init__(name = 'ePixBoard', description = 'ePix 100a Board', **kwargs)
        #self.add(MyRunControl('runControl'))
        self.add(dataWriter)
        self.guiTop = guiTop

        @self.command()
        def Trigger():
            #print("Sending cmd through VC" , VC_NUM_ID)
            cmd.sendCmd(0, 0)

        # Add Devices, defined at AxiVersionEpix100a file
        self.add(fpga.Epix100a(name='ePix100aFPGA', offset=0, memBase=srp, hidden=False, enabled=True))
        self.add(pyrogue.RunControl(name = 'runControl', description='Run Controller ePix 100a', cmd=self.Trigger, rates={1:'1 Hz', 2:'2 Hz', 4:'4 Hz', 8:'8 Hz', 10:'10 Hz', 30:'30 Hz', 60:'60 Hz', 120:'120 Hz'}))

if (PRINT_VERBOSE): dbgData = rogue.interfaces.stream.Slave()
if (PRINT_VERBOSE): dbgData.setDebug(60, "DATA[{}]".format(0))
if (PRINT_VERBOSE): pyrogue.streamTap(pgpVc1, dbgData)

# Create GUI
appTop = QApplication(sys.argv)
guiTop = pyrogue.gui.GuiTop(group = 'ePix100aGui')
ePixBoard = EpixBoard(guiTop, cmd, dataWriter, srp)
ePixBoard.start()
guiTop.addTree(ePixBoard)
guiTop.resize(1000,800)

# Viewer gui
gui = vi.Window(cameraType = 'ePix100a')
gui.eventReader.frameIndex = 0
#gui.eventReaderImage.VIEW_DATA_CHANNEL_ID = 0
gui.setReadDelay(0)
pyrogue.streamTap(pgpVc1, gui.eventReader)
pyrogue.streamTap(pgpVc2, gui.eventReaderScope)# PseudoScope
pyrogue.streamTap(pgpVc3, gui.eventReaderMonitoring) # Slow Monitoring

# Run gui
if (START_GUI):
    appTop.exec_()

# Close window and stop polling
def stop():
    mNode.stop()
#    epics.stop()
    ePixBoard.stop()
    exit()

# Start with: ipython -i scripts/epix100aDAQ.py for interactive approach
print("Started rogue mesh and epics V3 server. To exit type stop()")
