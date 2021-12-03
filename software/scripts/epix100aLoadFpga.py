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
import ePixFpga as fpga
import argparse

# Set the argument parser
parser = argparse.ArgumentParser()

# Convert str to bool
argBool = lambda s: s.lower() in ['true', 't', 'yes', '1']

# Add arguments
parser.add_argument(
    "--pgp", 
    type     = str,
    required = False,
    default  = '/dev/pgpcard_0',
    help     = "PGP devide (default /dev/pgpcard_0)",
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
pgpVc1 = rogue.hardware.pgp.PgpCard(args.pgp,0,0) # Data & cmds
pgpVc0 = rogue.hardware.pgp.PgpCard(args.pgp,0,1) # Registers for ePix board
pgpVc2 = rogue.hardware.pgp.PgpCard(args.pgp,0,2) # PseudoScope
pgpVc3 = rogue.hardware.pgp.PgpCard(args.pgp,0,3) # Monitoring (Slow ADC)

# Create and Connect SRP to VC1 to send commands
srp = rogue.protocols.srp.SrpV0()
pyrogue.streamConnectBiDir(pgpVc1,srp)
            
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
