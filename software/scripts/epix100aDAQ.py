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
import rogue
import pyrogue as pr
import pyrogue.pydm
import ePixFpga as fpga
import argparse

from ePixViewer.asics import ePix100a
from ePixViewer import EnvDataReceiver
from ePixViewer import ScopeDataReceiver

import os
import subprocess

top_level = os.path.realpath(__file__).split('software')[0]

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
    "--dev",
    type     = str,
    required = False,
    default  = '/dev/datadev_0',
    help     = "device file",
)

parser.add_argument(
    "--lane",
    type     = int,
    required = False,
    default  = 0,
    help     = "PGP Lane",
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
    def __init__(self, **kwargs):
        super().__init__(name = 'ePixBoard', description = 'ePix 100a Board', **kwargs)
        
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

        cmd = rogue.protocols.srp.Cmd()
        pyrogue.streamConnect(cmd, pgpVc1)
        pyrogue.streamConnect(cmd, pgpVc2)
        pyrogue.streamConnect(cmd, pgpVc3)

        srp = rogue.protocols.srp.SrpV3()
        srp == pgpVc0

        self.zmqServer = pr.interfaces.ZmqServer(root=self, addr='*', port=9099)
        self.addInterface(self.zmqServer)
        
        self.rate = rogue.interfaces.stream.RateDrop(True,1)
        
        self.add(ePix100a.DataReceiverEpix100a(name = f"DataReceiver"))
        pgpVc1 >> self.rate >> getattr(self, f"DataReceiver")

        envConf = [
                [
                    {   'id': 7, 'name': 'Strong Back Temp. (deg. C)', 'conv': lambda data: data/100, 'color': '#FFFFFF'  },
                    {   'id': 8, 'name': 'Ambient Temp. (deg. C)',      'conv': lambda data: data/100, 'color': '#FF00FF' },
                    {   'id': 9, 'name': 'Humidity (%%)',    'conv': lambda data: data/100, 'color': '#00FFFF'  },
                    {   'id': 10, 'name': 'ASIC Analog Current (Amps)',   'conv': lambda data: data/1000, 'color': '#FFFF00'  },
                    {   'id': 11, 'name': 'ASIC Digital Current (Amps)',   'conv': lambda data: data/1000, 'color': '#F0F0F0'  },
                    {   'id': 12, 'name': 'Guard Ring Current (Amps)',   'conv': lambda data: data/1000, 'color': '#F0500F'  },
                    {   'id': 13, 'name': 'Analog Voltage (Volts)',   'conv': lambda data: data/1000, 'color': '#503010'  },
                    {   'id': 14, 'name': 'Digital Voltage (Volts)',   'conv': lambda data: data/1000, 'color': '#777777'  }
                ],
        ]
        
        self.add(
            EnvDataReceiver(
                config = envConf[0], 
                clockT = None, 
                rawToData = lambda raw: float(raw),
                name = f"EnvData"
            )
        )
        pgpVc3 >> getattr(self, f"EnvData")

        self.add(ScopeDataReceiver(name = f"ScopeData"))
        pgpVc2 >> getattr(self, f"ScopeData")
        
        @self.command()
        def OpenCameraViewer():
            subprocess.Popen(
                ["python", 
                 top_level+"software/python/ePixViewer-sub/python/ePixViewer/runLiveDisplay.py", 
                 "--dataReceiver", 
                 "rogue://0/root.DataReceiver", 
                 "image", 
                 "--title", 
                 "Camera", 
                 "--sizeY", 
                 "708", 
                 "--sizeX",
                 "768", 
                 "--serverList",
                 "localhost:{}".format(9099)
                 ], shell=False
             )
        
        @self.command()
        def OpenEnvViewer():
            subprocess.Popen(
                ["python", 
                 top_level+"software/python/ePixViewer-sub/python/ePixViewer/runLiveDisplay.py", 
                 "--dataReceiver", 
                 "rogue://0/root.EnvData", 
                 "env", 
                 "--title", 
                 "Environment", 
                 "--serverList",
                 "localhost:{}".format(9099)
                 ], shell=False
             )
        
        @self.command()
        def OpenScopeViewer():
            subprocess.Popen(
                ["python", 
                 top_level+"software/python/ePixViewer-sub/python/ePixViewer/runLiveDisplay.py", 
                 "--dataReceiver", 
                 "rogue://0/root.ScopeData", 
                 "pseudoscope", 
                 "--title", 
                 "Scope", 
                 "--serverList",
                 "localhost:{}".format(9099)
                 ], shell=False
             )



        @self.command()
        def Trigger():
            cmd.sendCmd(0, 0)

        # Add Devices, defined at AxiVersionEpix100a file
        self.add(fpga.Epix100a(name='ePix100aFPGA', offset=0, memBase=srp, hidden=False, enabled=True))
        self.add(
            pyrogue.RunControl(
                name = 'runControl', 
                description='Run Controller ePix 100a', 
                cmd=self.Trigger, 
                rates={1:'1 Hz', 2:'2 Hz', 4:'4 Hz', 8:'8 Hz', 10:'10 Hz', 30:'30 Hz', 60:'60 Hz', 120:'120 Hz'}
            )
        )


ePixBoard = EpixBoard()
ePixBoard.start()

print("Starting PyDM")
pyrogue.pydm.runPyDM(
    serverList  = ePixBoard.zmqServer.address,
    sizeX=700,
    sizeY=800,
)

ePixBoard.stop()
exit()
