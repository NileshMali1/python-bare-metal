from django.db import models
from lvm2.entities import Disk, Partition, PhysicalVolume, VolumeGroup, LogicalVolume, Snapshot
from tgtadm.iscsi_target import ISCSITarget
from enum import Enum, unique
import inspect


# Create your models here.

@unique
class InitiatorMode(Enum):
    AUTOMATIC = "A"
    MANUAL = "M"

    @classmethod
    def choices(cls):
        # get all members of the class
        members = inspect.getmembers(cls, lambda member: not (inspect.isroutine(member)))
        # filter down to just properties
        properties = [member for member in members if not (member[0][:2] == '__')]
        # format into django choice tuple
        choices = tuple([(str(property[1].value), property[0]) for property in properties])
        return choices


class Initiator(models.Model):
    """A machine booting into its NIC's PXE/iPXE boot program, is an initiator"""

    mac_address = models.CharField(max_length=17, null=False, blank=False)
    name = models.CharField(max_length=20, null=False, blank=False)
    mode = models.CharField(max_length=1, choices=InitiatorMode.choices(), default=InitiatorMode.AUTOMATIC.value,
                            null=False, blank=False)


class Target(models.Model):
    """A disk instance"""

    vgs = tuple([(vgroup.get_name(), vgroup.get_name()) for vgroup in VolumeGroup.get_all()])

    volume_group = models.CharField(max_length=20, choices=vgs)
    logical_volume = models.CharField(max_length=20, null=False, blank=False)
    snapshot = models.CharField()
