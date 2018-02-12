from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.exceptions import ParseError
from rest_framework.decorators import detail_route
from django.http import JsonResponse
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.urls import resolve
from urllib.parse import urlparse
from api.models import Initiator, Target, LogicalUnit, LogicalUnitStatus, Snapshot
from api.serializers import InitiatorSerializer, TargetSerializer, LogicalUnitSerializer, SnapshotSerializer
from helpers.lvm2.entities import VolumeGroup
from helpers.tgtadm.iscsi_target import ISCSITarget
from helpers.tgtadm.iscsi_initiator import ISCSIInitiator


def url_resolver(url):
    resolved_func, unused_args, resolved_kwargs = resolve(urlparse(url).path)
    return resolved_kwargs['pk']


class InitiatorViewSet(viewsets.ModelViewSet):
    queryset = Initiator.objects.all()
    serializer_class = InitiatorSerializer


class TargetViewSet(viewsets.ModelViewSet):
    queryset = Target.objects.all()
    serializer_class = TargetSerializer

    def get_queryset(self):
        mac_address = self.request.query_params.get("mac_address", None)
        if mac_address:
            self.queryset = self.queryset.filter(initiator__mac_address=mac_address)
        return self.queryset

    @staticmethod
    def attach_all_usable_logical_units(target, iscsi_target):
        logical_units = target.logical_units.filter(status=LogicalUnitStatus.OFFLINE.value, use=True)
        for logical_unit in logical_units:
            device_path = LogicalUnitViewSet.get_device_path(logical_unit)
            if not device_path:
                continue
            lun_id = iscsi_target.get_logical_unit_number(device_path)
            if lun_id and str(lun_id) != str(logical_unit.id) and iscsi_target.detach_logical_unit(lun_id):
                lun_id = None
            if not lun_id and iscsi_target.attach_logical_unit(device_path, logical_unit.id):
                lun_id = logical_unit.id
            if lun_id:
                logical_unit.status = LogicalUnitStatus.ONLINE.value
            logical_unit.save()

    @staticmethod
    def get_next_boot_disk(target):
        get_next_disk = False
        logical_unit = target.logical_units.filter(status=LogicalUnitStatus.BUSY.value).first()
        if logical_unit:
            if logical_unit.boot_count <= 0:
                if logical_unit.snapshots.filter(active=True):
                    logical_unit.status = LogicalUnitStatus.MODIFIED.value
                else:
                    logical_unit.status = LogicalUnitStatus.ONLINE.value
                logical_unit.save()
                get_next_disk = True
        if not logical_unit or get_next_disk:
            logical_unit = target.logical_units.filter(
                status=LogicalUnitStatus.ONLINE.value, last_attached=None).first()
            if not logical_unit:
                try:
                    logical_unit = target.logical_units.filter(status=LogicalUnitStatus.ONLINE.value).earliest("last_attached")
                except ObjectDoesNotExist:
                    logical_unit = None
        return logical_unit if logical_unit else None

    @detail_route()
    def get_boot_disk_info(self, request, pk):
        target = Target.objects.get(pk=pk)
        iscsi_target = ISCSITarget(pk, target.name)
        if not iscsi_target.exists() and iscsi_target.add():
            pass
        self.attach_all_usable_logical_units(target, iscsi_target)
        iscsi_target.close_initiator_connections(ISCSIInitiator(target.initiator.ip_address))
        iscsi_target.bind_to_initiator() # opposite: iscsi_target.unbind_from_initiator()
        logical_unit = self.get_next_boot_disk(target)
        if not logical_unit:
            return JsonResponse({'result': False, 'message': "No logical unit found for booting"})
        logical_unit.status = LogicalUnitStatus.BUSY.value
        logical_unit.last_attached = timezone.now()
        if logical_unit.boot_count > 0:
            logical_unit.boot_count -= 1
        logical_unit.save()
        return JsonResponse({'result': True, "lun": str(logical_unit.id), "iqn": iscsi_target.get_name(),
                             'message': "use lun id and iqn to form iSCSI URL"})

    @detail_route()
    def get_map_disk_info(self, request, pk):
        target = Target.objects.get(pk=pk)
        iscsi_target = ISCSITarget(pk, target.name)
        if not iscsi_target.exists() and iscsi_target.add():
            pass
        iscsi_target.bind_to_initiator()  # opposite: iscsi_target.unbind_from_initiator()
        logical_unit = target.logical_units.filter(status=LogicalUnitStatus.MODIFIED.value).first()
        if not logical_unit:
            return JsonResponse({'result': False, 'message': "No logical unit found for mapping"})
        device_path = LogicalUnitViewSet.get_device_path(logical_unit)
        if device_path:
            lun_id = iscsi_target.get_logical_unit_number(device_path)
            if lun_id and str(lun_id) == str(logical_unit.id):
                logical_unit.status = LogicalUnitStatus.MOUNTED.value
                logical_unit.save()
                return JsonResponse({'result': True, "lun": str(logical_unit.id), "iqn": iscsi_target.get_name(),
                                     'message': "use lun id and iqn to form iSCSI URL"})
            return JsonResponse({'result': False, 'message': "No target online or online with different id"})
        return JsonResponse({'result': False, 'message': "No logical volume path was discovered"})

    def destroy(self, request, pk):
        target = Target.objects.get(pk=pk)
        if not target:
            raise ParseError("Target not found")
        iscsi_target = ISCSITarget(pk, target.name)
        if iscsi_target.exists():
            iscsi_target.close_all_connections()
            iscsi_target.detach_all_logical_units()
            iscsi_target.remove()
        target.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    """
    def list(self, request):
        pass
    def retrieve(self, request, pk=None):
        pass
    def update(self, request, pk=None):
        target = Target.objects.get(pk=pk)
        if target:
    def partial_update(self, request, pk=None):
        raise ParseError("Unable to partially update")
    """


class LogicalUnitViewSet(viewsets.ModelViewSet):
    queryset = LogicalUnit.objects.all()
    serializer_class = LogicalUnitSerializer

    @staticmethod
    def get_device_path(logical_unit):
        volume_group = VolumeGroup(logical_unit.group)
        if not volume_group:
            return None
        logical_volumes = volume_group.get_logical_volumes(logical_unit.name)
        if not logical_volumes:
            return None
        logical_volume = logical_volumes[0]
        device_path = logical_volume.get_path()
        active_snapshot = logical_unit.snapshots.filter(active=True).first()
        if active_snapshot:
            snapshot = logical_volume.get_snapshots(active_snapshot.name)
            device_path = snapshot.get_path()
        return device_path

    @staticmethod
    def get_logical_volume(pk):
        logical_unit = LogicalUnit.objects.get(pk=pk)
        if not logical_unit:
            return None
        virtual_group = VolumeGroup(logical_unit.group)
        if not virtual_group:
            return None
        logical_volumes = virtual_group.get_logical_volumes(logical_unit.name)
        return logical_volumes[0] if logical_volumes else None

    @staticmethod
    def get_active_snapshots(pk):
        logical_unit = LogicalUnit.objects.get(pk=pk)
        if not logical_unit:
            return None
        snapshots = logical_unit.snapshots.filter(active=True)
        return snapshots[0] if snapshots else None

    @staticmethod
    def detach(logical_unit):
        iscsi_target = ISCSITarget(logical_unit.target.id, logical_unit.target.name)
        if iscsi_target.exists():
            device_path = LogicalUnitViewSet.get_device_path(logical_unit)
            if device_path:
                lun_id = iscsi_target.get_logical_unit_number(device_path)
                if lun_id and iscsi_target.detach_logical_unit(lun_id):
                    return True
        return False

    @detail_route(methods=["PATCH"])
    def recreate(self, request, pk):
        logical_unit = LogicalUnit.objects.get(pk=pk)
        if not logical_unit:
            return ParseError("No logical unit")
        virtual_group = VolumeGroup(logical_unit.group)
        if not virtual_group:
            return ParseError("No volume group")
        logical_volumes = virtual_group.get_logical_volumes(logical_unit.name)
        logical_volume = logical_volumes[0] if logical_volumes else None
        if logical_volume:
            (size, unit) = logical_volume.get_size()
            self.detach(logical_unit)
            if virtual_group.remove_logical_volume(logical_unit.name) and virtual_group.create_logical_volume(logical_unit.name, size, unit):
                return Response("Created...")
        return ParseError("error: unable to recreate...")

    @detail_route(methods=["PATCH"])
    def revert(self, request, pk):
        if request.data.__contains__('snapshot') and request.data.__getitem__('snapshot'):
            snapshot_name = request.data.__getitem__('snapshot')
        else:
            snapshot = self.get_active_snapshots(pk)
            snapshot_name = snapshot.name if snapshot else None
        if not snapshot_name:
            return Response("Could not find any active snapshot to revert to.", status=status.HTTP_417_EXPECTATION_FAILED)
        logical_volume = self.get_logical_volume(pk)
        if not logical_volume:
            raise ParseError("Logical volume not found")
        if logical_volume.revert_to_snapshot(snapshot_name):
            return Response("Successfully reverted to snapshot '%s'" % snapshot_name, status=status.HTTP_200_OK)
        return Response("Could not revert to snapshot '%s'" % snapshot_name, status=status.HTTP_417_EXPECTATION_FAILED)

    @detail_route(methods=["PATCH"])
    def dump(self, request, pk):
        logical_volume = self.get_logical_volume(pk)
        if not logical_volume:
            raise ParseError("Logical volume not found")
        if not request.data.__contains__('local_file') or not request.data.__getitem__('local_file'):
            return Response("No valid 'local_file' key found", status=status.HTTP_400_BAD_REQUEST)
        output = logical_volume.dump_to_image(request.data.__getitem__('local_file'))
        if output:
            message = "Successfully dumped the disk. Details: %s" % output
            status_code = status.HTTP_200_OK
        else:
            message = "Failed to dump the disk. Details: %s" % output
            status_code = status.HTTP_417_EXPECTATION_FAILED
        return Response(message, status=status_code)

    @detail_route(methods=["PATCH"])
    def restore(self, request, pk):
        logical_volume = self.get_logical_volume(pk)
        if not logical_volume:
            raise ParseError("Target disk not found")
        if not request.data.__contains__('local_file') or not request.data.__getitem__('local_file'):
            return Response("No valid 'local_file' key found", status=status.HTTP_400_BAD_REQUEST)
        output = logical_volume.restore_from_image(request.data.__getitem__('local_file'))
        if output:
            message = "Successfully restored the disk. Details: %s" % output
            status_code = status.HTTP_200_OK
        else:
            message = "Failed to restore the disk. Details: %s" % output
            status_code = status.HTTP_417_EXPECTATION_FAILED
        return Response(message, status=status_code)

    def create(self, request):
        if not (request.data.__contains__('name') and request.data.__contains__('group')):
            raise ParseError("'name' & 'group' fields are required and should have valid data")
        vg = VolumeGroup(request.data.__getitem__('group'))
        if not vg:
            raise ParseError("No volume group found with that name")
        if vg.contains_logical_volume(request.data.__getitem__('name')):
            raise ParseError("Logical unit with that name does exist")
        size = float(request.data.__getitem__('size_in_gb')) if request.data.__contains__('size_in_gb') else 20.0
        if vg.create_logical_volume(request.data.__getitem__('name'), size):
            logical_unit, created = LogicalUnit.objects.get_or_create(name=request.data.__getitem__('name'),
                                                                      group=request.data.__getitem__('group'))
            if created:
                logical_unit.size_in_gb = size
                if request.data.__contains__('use') and request.data.__getitem__('use'):
                    logical_unit.use = True if str(request.data.__getitem__('use')).lower() == "true" else False
                if request.data.__contains__('status') and request.data.__getitem__('status'):
                    logical_unit.status = int(request.data.__getitem__('status'))
                if request.data.__contains__('boot_count') and request.data.__getitem__('boot_count'):
                    logical_unit.boot_count = int(request.data.__getitem__('boot_count'))
                if request.data.__contains__('target') and request.data.__getitem__('target'):
                    logical_unit.target = Target.objects.get(pk=url_resolver(request.data.__getitem__('target')))
                logical_unit.save()
            return Response(LogicalUnitSerializer(instance=logical_unit, context={'request': request}).data)
        raise ParseError("Logical unit could not be created. %s" % status)

    def destroy(self, request, pk):
        logical_unit = LogicalUnit.objects.get(pk=pk)
        if logical_unit:
            self.detach(logical_unit)
            volume_group = VolumeGroup(logical_unit.group)
            if volume_group and volume_group.contains_logical_volume(logical_unit.name) and\
                    not volume_group.remove_logical_volume(logical_unit.name):
                        raise ParseError("Could not remove logical volume")
            logical_unit.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        raise ParseError("Could not found the logical unit")


class SnapshotViewSet(viewsets.ModelViewSet):
    queryset = Snapshot.objects.all()
    serializer_class = SnapshotSerializer

    @staticmethod
    def get_logical_volume(vgroup_name, lv_name):
        volume_group = VolumeGroup(vgroup_name)
        if not volume_group:
            return None
        logical_volumes = volume_group.get_logical_volumes(lv_name)
        return logical_volumes[0] if logical_volumes else None

    def create(self, request):
        if request.data.__contains__('name') and request.data.__contains__('logical_unit'):
            logical_unit = LogicalUnit.objects.get(pk=url_resolver(request.data.__getitem__('logical_unit')))
            if not logical_unit:
                raise ParseError("Logical unit not found.")
            logical_volume = self.get_logical_volume(logical_unit.group, logical_unit.name)
            size = float(request.data.__getitem__('size_in_gb')) if request.data.__contains__('size_in_gb') else 5.0
            if logical_volume and not logical_volume.contains_snapshot(request.data.__getitem__('name')) and \
                    logical_volume.create_snapshot(request.data.__getitem__('name'), size):
                snapshot, created = Snapshot.objects.get_or_create(name=request.data.__getitem__('name'),
                                                                   logical_unit=logical_unit)
                if created:
                    snapshot.size_in_gb = size
                    if request.data.__contains__('active') and request.data.__getitem__('active'):
                        snapshot.active = True if str(request.data.__getitem__('active')).lower() == "true" else False
                    snapshot.save()
                return Response(SnapshotSerializer(instance=snapshot, context={'request': request}).data)
            raise ParseError("Resource could not be created. %s" % status)
        raise ParseError("'name' & 'group' fields are required and should have valid data")

    def destroy(self, request, pk=None):
        snapshot = Snapshot.objects.get(pk=pk)
        if snapshot:
            logical_volume = self.get_logical_volume(snapshot.logical_unit.group, snapshot.logical_unit.name)
            if logical_volume and logical_volume.contains_snapshot(snapshot.name) and\
                    not logical_volume.remove_snapshot(snapshot.name):
                raise ParseError("Could not delete snapshot")
            snapshot.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        raise ParseError("No snapshot instance found")
