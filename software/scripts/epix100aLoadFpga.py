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

import rogue
import rogue.hardware.axi
import rogue.interfaces.stream

import ePixFpga as fpga

import surf
import surf.axi
import threading
import signal
import atexit
import yaml
import time
import sys
import argparse

# Set the argument parser
parser = argparse.ArgumentParser()

# Convert str to bool
argBool = lambda s: s.lower() in ['true', 't', 'yes', '1']

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
    "--mcs",
    type     = str,
    required = True,
    help     = "path to mcs file",
)

# Get the arguments
args = parser.parse_args()

# Create the PGP interfaces for ePix camera
pgpVc0 = rogue.hardware.axi.AxiStreamDma(args.dev,(args.lane*0x100)+0,True) # Data & cmds
pgpVc1 = rogue.hardware.axi.AxiStreamDma(args.dev,(args.lane*0x100)+1,True) # Registers for ePix board
pgpVc2 = rogue.hardware.axi.AxiStreamDma(args.dev,(args.lane*0x100)+2,True) # PseudoScope
pgpVc3 = rogue.hardware.axi.AxiStreamDma(args.dev,(args.lane*0x100)+3,True) # Monitoring (Slow ADC)

# Create and Connect SRP to VC0 to send commands
srp = rogue.protocols.srp.SrpV3()
srp == pgpVc0

##############################
# Set base
##############################
class EpixBoard(pyrogue.Root):
    def __init__(self, srp, **kwargs):
        super().__init__(name = 'ePixBoard', description = 'ePix 100a Board', **kwargs)
        self.add(fpga.Epix100a(name='ePix100aFPGA', offset=0, memBase=srp, hidden=False, enabled=True))

# Create GUI
ePixBoard = EpixBoard(srp=srp, pollEn=False, initRead=False)
ePixBoard.start()

# Create useful pointers
AxiVersion = ePixBoard.ePix100aFPGA.AxiVersion
PROM       = ePixBoard.ePix100aFPGA.MicronN25Q

print ( '###################################################')
print ( '#                 Old Firmware                    #')
print ( '###################################################')
AxiVersion.printStatus()

# Program the FPGA's PROM
PROM.LoadMcsFile(args.mcs)

# Check if PROM successfully programmed
if(PROM._progDone):
    print('\nReloading FPGA firmware from PROM ....')
    AxiVersion.FpgaReload()
    time.sleep(10)
    print('\nReloading FPGA done')

    print ( '###################################################')
    print ( '#                 New Firmware                    #')
    print ( '###################################################')
    AxiVersion.printStatus()
else:
    print('Failed to program FPGA')

ePixBoard.stop()
exit()
