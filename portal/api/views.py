from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.exceptions import ParseError
from rest_framework.decorators import detail_route
from django.http import JsonResponse
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.urls import resolve
from urllib.parse import urlparse
from api.models import PDU, KVM, Initiator, Target, LogicalUnit, Snapshot
from api.serializers import PDUSerializer, KVMSerializer, InitiatorSerializer, TargetSerializer, LogicalUnitSerializer,\
    SnapshotSerializer
from helpers.lvm2.entities import VolumeGroup
from helpers.lvm2.entities import DiskStatus as LogicalUnitStatus
from helpers.tgtadm.iscsi_target import ISCSITarget
from helpers.tgtadm.iscsi_initiator import ISCSIInitiator
from datetime import datetime


def url_resolver(url):
    resolved_func, unused_args, resolved_kwargs = resolve(urlparse(url).path)
    return resolved_kwargs['pk']


class PDUViewSet(viewsets.ModelViewSet):
    queryset = PDU.objects.all()
    serializer_class = PDUSerializer


class KVMViewSet(viewsets.ModelViewSet):
    queryset = KVM.objects.all()
    serializer_class = KVMSerializer


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
    def attach_all_usable_logical_units(target):
        logical_units = target.logical_units.filter(status=LogicalUnitStatus.OFFLINE.value, use=True)
        for logical_unit in logical_units:
            LogicalUnitViewSet.detach_from_target(logical_unit)  # if already attached, detach it
            LogicalUnitViewSet.attach_to_target(logical_unit)
            logical_unit.status = LogicalUnitStatus.ONLINE.value
            logical_unit.save()

    @staticmethod
    def detach_all_active_logical_units(iscsi_target):
        active_logical_units = iscsi_target.list_active_logical_units()
        for lun_id in active_logical_units:
            iscsi_target.detach_logical_unit(lun_id)

    @staticmethod
    def get_boot_logical_unit(target):
        get_next_disk = False
        logical_unit = target.logical_units.filter(status=LogicalUnitStatus.BUSY.value).first()
        if logical_unit and logical_unit.boot_count <= 0 and logical_unit.snapshots.filter(active=True):
            logical_unit.status = LogicalUnitStatus.MODIFIED.value
            logical_unit.save()
            LogicalUnitViewSet.detach_from_target(logical_unit)
            get_next_disk = True
        if not logical_unit or get_next_disk:
            logical_unit = target.logical_units.filter(status=LogicalUnitStatus.ONLINE.value, last_attached=None
                                                       ).first()
            if not logical_unit:
                try:
                    logical_unit = target.logical_units.filter(status=LogicalUnitStatus.ONLINE.value
                                                               ).earliest("last_attached")
                except ObjectDoesNotExist:
                    pass
        return logical_unit if logical_unit else None

    @detail_route()
    def get_boot_disk_info(self, request, pk):
        target = Target.objects.get(pk=pk)
        iscsi_target = ISCSITarget(pk, target.name)
        if not iscsi_target.exists():
            iscsi_target.add()
        iscsi_target.bind_to_initiator()  # opposite: iscsi_target.unbind_from_initiator()
        self.detach_all_active_logical_units(iscsi_target)
        iscsi_target.close_initiator_connections(ISCSIInitiator(target.initiator.ip_address))
        logical_unit = self.get_boot_logical_unit(target)
        if not logical_unit:
            return JsonResponse({'result': False, 'message': "No logical unit found for booting"})
        check_passed = LogicalUnitViewSet.attach_to_target(logical_unit)
        if not check_passed:
            return JsonResponse({'result': False, 'message': "Unable to attach logical unit to target"})
        logical_unit.status = LogicalUnitStatus.BUSY.value
        logical_unit.last_attached = timezone.now()
        if logical_unit.boot_count > 0:
            logical_unit.boot_count -= 1
        logical_unit.save()
        target.initiator.last_initiated = datetime.now()
        target.initiator.save()
        return JsonResponse({'result': True, "lun": "{0:x}".format(logical_unit.id), "iqn": iscsi_target.get_name(),
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
                return JsonResponse({'result': True, "lun": "{0:x}".format(logical_unit.id), "iqn": iscsi_target.get_name(),
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
    def map_status(status):
        if status.lower() not in ["offline", "online", "busy", "modified", "mounted"]:
            return None
        if status.lower() == "offline":
            return LogicalUnitStatus.OFFLINE.value
        if status.lower() == "online":
            return LogicalUnitStatus.ONLINE.value
        if status.lower() == "busy":
            return LogicalUnitStatus.BUSY.value
        if status.lower() == "modified":
            return LogicalUnitStatus.MODIFIED.value
        if status.lower() == "mounted":
            return LogicalUnitStatus.MOUNTED.value

    def get_queryset(self):
        status = self.request.query_params.get("status", None)
        if status:
            status = self.map_status(status)
            if status:
                self.queryset = self.queryset.filter(status=status)
        return self.queryset

    @staticmethod
    def get_device_path(logical_unit):
        volume_group = VolumeGroup(logical_unit.group)
        if not volume_group:
            return None
        logical_volumes = volume_group.get_logical_volumes(logical_unit.name)
        if not logical_volumes:
            return None
        active_snapshot = logical_unit.snapshots.filter(active=True).first()
        if active_snapshot:
            snapshots = logical_volumes[0].get_snapshots(active_snapshot.name)
            return snapshots[0].get_path() if snapshots else None
        snapshot = logical_unit.snapshots.filter().first()
        return logical_volumes[0].get_path() if not snapshot else None

    @staticmethod
    def get_logical_volume(logical_unit):
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
    def attach_to_target(logical_unit):
        iscsi_target = ISCSITarget(logical_unit.target.id, logical_unit.target.name)
        if not iscsi_target.exists():
            iscsi_target.add()
        device_path = LogicalUnitViewSet.get_device_path(logical_unit)
        if device_path and iscsi_target.attach_logical_unit(device_path, logical_unit.id):
            return iscsi_target.update_logical_unit_params(logical_unit.id, vendor_id=logical_unit.vendor_id,
                                                           product_id=logical_unit.product_id,
                                                           product_rev=logical_unit.product_rev)
        return False

    @staticmethod
    def detach_from_target(logical_unit):
        iscsi_target = ISCSITarget(logical_unit.target.id, logical_unit.target.name)
        if not iscsi_target.exists():
            return True
        return iscsi_target.detach_logical_unit(logical_unit.id)

    @detail_route()
    def get_mount_device_path(self, request, pk):
        logical_unit = LogicalUnit.objects.get(pk=pk)
        device_path = self.get_device_path(logical_unit)
        if device_path:
            return JsonResponse({"result": True, "device_path": device_path})
        return JsonResponse({"result": False, "device_path": None, "message": "No device found"})

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
            self.detach_from_target(logical_unit)
            if virtual_group.remove_logical_volume(logical_unit.name) and virtual_group.create_logical_volume(logical_unit.name, size, unit):
                return Response("Created...")
        return ParseError("error: unable to recreate...")

    @detail_route(methods=["PATCH"])
    def revert(self, request, pk):
        logical_unit = LogicalUnit.objects.get(pk=pk)
        if logical_unit.status in [LogicalUnitStatus.BUSY.value, LogicalUnitStatus.MOUNTED.value]:
            return JsonResponse(
                {"result": False, "message": "Disk is busy or mounted, turn machine off and turn disk offline"}
            )
        if request.data.__contains__('snapshot') and request.data.__getitem__('snapshot'):
            snapshot_name = request.data.__getitem__('snapshot')
        else:
            snapshot = self.get_active_snapshots(pk)
            snapshot_name = snapshot.name if snapshot else None
        if not snapshot_name:
            return JsonResponse({"result": False, "message": "Could not find any active snapshot to revert to"})
        logical_volume = self.get_logical_volume(logical_unit)
        if not logical_volume:
            return JsonResponse({"result": False, "message": "Logical volume not found"})
        if LogicalUnitViewSet.detach_from_target(logical_unit) and logical_volume.revert_to_snapshot(snapshot_name):
            logical_unit.status = LogicalUnitStatus.ONLINE.value
            logical_unit.save()
            return JsonResponse({"result": True, "message": "Successfully reverted to snapshot '%s'" % snapshot_name})
        return JsonResponse({"result": False, "message": "Could not revert to snapshot '%s'" % snapshot_name})

    @detail_route(methods=["PATCH"])
    def dump(self, request, pk):
        logical_unit = LogicalUnit.objects.get(pk=pk)
        logical_volume = self.get_logical_volume(logical_unit)
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
        logical_unit = LogicalUnit.objects.get(pk=pk)
        logical_volume = self.get_logical_volume(logical_unit)
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
                if request.data.__contains__('vendor_id') and request.data.__getitem__('vendor_id'):
                    logical_unit.vendor_id = request.data.__getitem__('vendor_id')
                if request.data.__contains__('product_id') and request.data.__getitem__('product_id'):
                    logical_unit.product_id = request.data.__getitem__('product_id')
                if request.data.__contains__('product_rev') and request.data.__getitem__('product_rev'):
                    logical_unit.product_rev = request.data.__getitem__('product_rev')
                if request.data.__contains__('use') and request.data.__getitem__('use'):
                    logical_unit.use = True if str(request.data.__getitem__('use')).lower() == "true" else False
                if request.data.__contains__('status') and request.data.__getitem__('status'):
                    logical_unit.status = request.data.__getitem__('status')
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
            self.detach_from_target(logical_unit)
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

    def create(self, request):
        if request.data.__contains__('name') and request.data.__contains__('logical_unit'):
            logical_unit = LogicalUnit.objects.get(pk=url_resolver(request.data.__getitem__('logical_unit')))
            if not logical_unit:
                raise ParseError("Logical unit not found.")
            if logical_unit.status != LogicalUnitStatus.OFFLINE.value:
                raise ParseError("Logical unit must be offline and its initiator machine must also be turned off")
            LogicalUnitViewSet.detach_from_target(logical_unit)
            logical_volume = LogicalUnitViewSet.get_logical_volume(logical_unit)
            size = float(request.data.__getitem__('size_in_gb')) if request.data.__contains__('size_in_gb') else 5.0
            if logical_volume and not logical_volume.contains_snapshot(request.data.__getitem__('name')) and \
                    logical_volume.create_snapshot(request.data.__getitem__('name'), size):
                snapshot, created = Snapshot.objects.get_or_create(name=request.data.__getitem__('name'),
                                                                   logical_unit=logical_unit)
                if created:
                    snapshot.size_in_gb = size
                    if request.data.__contains__('description') and request.data.__getitem__('description'):
                        snapshot.description = request.data.__getitem__('description')
                    if request.data.__contains__('active') and request.data.__getitem__('active'):
                        snapshot.active = True if str(request.data.__getitem__('active')).lower() == "true" else False
                    snapshot.save()
                return Response(SnapshotSerializer(instance=snapshot, context={'request': request}).data)
            raise ParseError("Resource could not be created. %s" % status)
        raise ParseError("'name' & 'group' fields are required and should have valid data")

    def destroy(self, request, pk):
        snapshot = Snapshot.objects.get(pk=pk)
        if snapshot.logical_unit.status != LogicalUnitStatus.OFFLINE.value:
            raise ParseError("Logical unit must be offline and its initiator machine must also be turned off")
        LogicalUnitViewSet.detach_from_target(snapshot.logical_unit)
        logical_volume = LogicalUnitViewSet.get_logical_volume(snapshot.logical_unit)
        if logical_volume:
            logical_volume.remove_snapshot(snapshot.name)
        snapshot.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
