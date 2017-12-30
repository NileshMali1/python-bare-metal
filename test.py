from com.nls90.wrapper.lvm.physical_volume import PhysicalVolume
from com.nls90.wrapper.lvm.volume_group import VolumeGroup
from com.nls90.wrapper.lvm.logical_volume import LogicalVolume


# print(PhysicalVolume.list())
# print(VolumeGroup.list())
print(LogicalVolume.create("nls", "test", 20))
print(LogicalVolume.list())
print(LogicalVolume.remove("/dev/test/nls"))