

class ISCSIInitiator(object):
    """iSCSI initiator object"""

    def __init__(self, ip_address, name):
        self._ip_address = ip_address
        self._name = name

    def get_ip_address(self):
        return self._ip_address

    def get_name(self):
        return self._name

    def set_ip_address(self, ip_address):
        self._ip_address = ip_address

    def set_name(self, name):
        self._name = name
