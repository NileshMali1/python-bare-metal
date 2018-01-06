

class ISCSIInitiator(object):
    """iSCSI initiator object"""

    def __init__(self, address, name):
        self._address = address
        self._name = name

    def get_address(self):
        return self._address

    def get_name(self):
        return self._name

    def set_address(self, address):
        self._address = address

    def set_name(self, name):
        self._name = name
