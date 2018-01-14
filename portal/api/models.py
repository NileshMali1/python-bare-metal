import inspect
from enum import Enum, unique
from django.db import models
from helpers.lvm2.entities import VolumeGroup


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
    last_initiated = models.DateTimeField()

    def __str__(self):
        return self.name + " [has MAC address '" + self.mac_address + "']"


@unique
class TargetState(Enum):
    OFFLINE = 0
    ONLINE = 1
    LOCKED = 2

    @classmethod
    def choices(cls):
        members = inspect.getmembers(cls, lambda member: not (inspect.isroutine(member)))
        properties = [member for member in members if member[0][:2] != '__' and member[0] not in ['name', 'value']]
        choices = tuple([(str(property[1].value), property[0]) for property in properties])
        return choices


class Target(models.Model):
    name = models.CharField(max_length=20, null=False, blank=False)
    groups = tuple([(group.get_name(), group.get_name()) for group in VolumeGroup.get_all()])
    group = models.CharField(max_length=20, choices=groups)
    size_in_gb = models.FloatField(default=20.0)
    boot = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    initiator = models.ForeignKey(Initiator, on_delete=models.SET_NULL, null=True, blank=False, related_name="targets")

    class Meta:
        unique_together = ('name', 'group')

    def __str__(self):
        if self.initiator:
            return self.name + " [is target of '" + self.initiator.name + "']"
