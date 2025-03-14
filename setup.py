from setuptools import setup

# use softlinks to make the various "board_support_package" submodules
# look like subpackages.  Then __init__.py will modify
# sys.path so that the correct "local" versions of surf etc. are
# picked up.  A better approach would be using relative imports
# in the submodules, but that's more work.  _cpo

setup(
    name = 'epix100a_gen2',
    description = 'Epix 100a gen2 package',
    packages = [
        'epix100a_gen2.ePixFpga',
        'epix100a_gen2.ePixViewer',
        'epix100a_gen2.ePixAsics',
        'epix100a_gen2.surf',
        'epix100a_gen2.surf.axi',
        'epix100a_gen2.surf.protocols',
        'epix100a_gen2.surf.protocols.batcher',
        'epix100a_gen2.surf.protocols.jesd204b',
        'epix100a_gen2.surf.protocols.clink',
        'epix100a_gen2.surf.protocols.htsp',
        'epix100a_gen2.surf.protocols.rssi',
        'epix100a_gen2.surf.protocols.ssi',
        'epix100a_gen2.surf.protocols.i2c',
        'epix100a_gen2.surf.protocols.ssp',
        'epix100a_gen2.surf.protocols.pgp',
        'epix100a_gen2.surf.devices.ti',
        'epix100a_gen2.surf.devices.transceivers',
        'epix100a_gen2.surf.devices.microchip',
        'epix100a_gen2.surf.devices.analog_devices',
        'epix100a_gen2.surf.devices.intel',
        'epix100a_gen2.surf.devices.micron',
        'epix100a_gen2.surf.devices.nxp',
        'epix100a_gen2.surf.devices.silabs',
        'epix100a_gen2.surf.devices.cypress',
        'epix100a_gen2.surf.devices',
        'epix100a_gen2.surf.devices.linear',
        'epix100a_gen2.surf.misc',
        'epix100a_gen2.surf.ethernet.xaui',
        'epix100a_gen2.surf.ethernet.gige',
        'epix100a_gen2.surf.ethernet.ten_gig',
        'epix100a_gen2.surf.ethernet.udp',
        'epix100a_gen2.surf.ethernet.mac',
        'epix100a_gen2.surf.ethernet',
        'epix100a_gen2.surf.dsp',
        'epix100a_gen2.surf.dsp.fixed',
        'epix100a_gen2.surf.xilinx',
        'epix100a_gen2',
    ],
    package_dir = {
        'epix100a_gen2': 'software/python/epix100a_gen2',
        'epix100a_gen2.surf': 'firmware/submodules/surf/python/surf',
        'epix100a_gen2.ePixFpga': 'software/python/ePixFpga',
        'epix100a_gen2.ePixViewer': 'software/python/submodules/ePixViewer',
        'epix100a_gen2.ePixAsics': 'software/python/ePixAsics',
    }
)
