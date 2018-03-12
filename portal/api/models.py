import inspect
from enum import Enum, unique
from django.db import models
from helpers.lvm2.entities import VolumeGroup
from helpers.lvm2.entities import DiskStatus as LogicalUnitStatus


class PDU(models.Model):
    name = models.CharField(max_length=50, null=False, blank=False, unique=True)
    ip_address = models.GenericIPAddressField(protocol="both", unpack_ipv4=True, blank=False, null=False, unique=True)
    mac_address = models.CharField(max_length=17, null=True, blank=True, unique=True)
    total_outlets = models.PositiveSmallIntegerField(default=0)
    model = models.CharField(max_length=100, null=True, blank=True)
    serial = models.CharField(max_length=100, null=True, blank=True)
    username = models.CharField(max_length=100, null=True, blank=True)
    password = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.name + " [hash IP '" + self.ip_address + "']"


class KVM(models.Model):
    name = models.CharField(max_length=50, null=False, blank=False, unique=True)
    ip_address = models.GenericIPAddressField(protocol="both", unpack_ipv4=True, blank=False, null=False, unique=True)
    mac_address = models.CharField(max_length=17, null=True, blank=True, unique=True)
    total_ports = models.PositiveSmallIntegerField(default=0)
    model = models.CharField(max_length=100, null=True, blank=True)
    serial = models.CharField(max_length=100, null=True, blank=True)
    username = models.CharField(max_length=100, null=True, blank=True)
    password = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.name + " [has IP '" + self.ip_address + "']"


@unique
class InitiatorMode(Enum):
    AUTOMATIC = "A"
    MANUAL = "M"

    @classmethod
    def choices(cls):
        members = inspect.getmembers(cls, lambda member: not (inspect.isroutine(member)))
        properties = [member for member in members if member[0][:2] != '__' and member[0] not in ['name', 'value']]
        choices = tuple([(str(property[1].value), property[0]) for property in properties])
        return choices


class Initiator(models.Model):
    mac_address = models.CharField(max_length=17, null=False, blank=False, unique=True)
    name = models.CharField(max_length=20, null=False, blank=False, unique=True)
    mode = models.CharField(max_length=1, choices=InitiatorMode.choices(), default=InitiatorMode.AUTOMATIC.value,
                            null=False, blank=False)
    ip_address = models.GenericIPAddressField(protocol="both", unpack_ipv4=True, blank=True, null=True)
    pdu_device = models.ForeignKey(PDU, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="outlet_endpoint")
    pdu_device_port = models.PositiveSmallIntegerField(default=0)
    kvm_device = models.ForeignKey(KVM, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="port_endpoint")
    kvm_device_port = models.PositiveSmallIntegerField(default=0)
    last_initiated = models.DateTimeField(null=True, blank=False)

    def __str__(self):
        return self.name + " [has MAC address '" + self.mac_address + "']"


@unique
class TargetStatus(Enum):
    OFFLINE = "0"
    ONLINE = "1"
    LOCKED = "2"

    @classmethod
    def choices(cls):
        members = inspect.getmembers(cls, lambda member: not (inspect.isroutine(member)))
        properties = [member for member in members if member[0][:2] != '__' and member[0] not in ['name', 'value']]
        choices = tuple([(str(property[1].value), property[0]) for property in properties])
        return choices


class Target(models.Model):
    name = models.CharField(max_length=100, null=False, blank=False, unique=True)
    boot = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    status = models.CharField(max_length=1, choices=TargetStatus.choices(), default=str(TargetStatus.OFFLINE.value))
    initiator = models.OneToOneField(Initiator, on_delete=models.SET_NULL, null=True, blank=False, related_name="target")

    def __str__(self):
        if self.initiator:
            return self.name + " [is target of '" + self.initiator.name + "']"
        else:
            return self.name


class LogicalUnit(models.Model):
    name = models.CharField(max_length=100, null=False, blank=False, unique=True)
    vendor_id = models.CharField(max_length=50, null=True, blank=True)
    product_id = models.CharField(max_length=50, null=True, blank=True)
    product_rev = models.CharField(max_length=50, null=True, blank=True)
    groups = tuple([(group.get_name(), group.get_name()) for group in VolumeGroup.get_all()])
    group = models.CharField(max_length=20, choices=groups)
    size_in_gb = models.FloatField(default=20.0)
    use = models.BooleanField(default=True, null=False, blank=False)
    status = models.CharField(max_length=1, choices=LogicalUnitStatus.choices(), default=LogicalUnitStatus.OFFLINE.value)
    boot_count = models.PositiveSmallIntegerField(default=0, blank=False, null=False)
    last_attached = models.DateTimeField(null=True)
    target = models.ForeignKey(Target, on_delete=models.SET_NULL, null=True, blank=False, related_name="logical_units")

    def __str__(self):
        return self.name


class Snapshot(models.Model):
    name = models.CharField(max_length=100, null=False, blank=False, unique=True)
    size_in_gb = models.FloatField(default=5.0)
    active = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)
    logical_unit = models.ForeignKey(LogicalUnit, on_delete=models.CASCADE, null=False, blank=False,
                                     related_name="snapshots")

    def __str__(self):
        return self.name + " [is snapshot of '" + self.logical_unit.name + "']"
