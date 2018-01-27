from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.exceptions import ParseError
from rest_framework.decorators import detail_route
from api.models import Initiator, Target, LogicalUnit, Snapshot
from api.serializers import InitiatorSerializer, TargetSerializer, LogicalUnitSerializer, SnapshotSerializer
from django.urls import resolve
from urllib.parse import urlparse
from helpers.lvm2.entities import VolumeGroup
from helpers.tgtadm.iscsi_target import ISCSITarget


def url_resolver(url):
    resolved_func, unused_args, resolved_kwargs = resolve(urlparse(url).path)
    return resolved_kwargs['pk']


class InitiatorViewSet(viewsets.ModelViewSet):
    queryset = Initiator.objects.all()
    serializer_class = InitiatorSerializer


class TargetViewSet(viewsets.ModelViewSet):
    queryset = Target.objects.all()
    serializer_class = TargetSerializer

    """
    def list(self, request):
        pass
    def retrieve(self, request, pk=None):
        pass
    """
    # def update(self, request, pk=None):
    #    target = Target.objects.get(pk=pk)
    #    if target:

    # def partial_update(self, request, pk=None):
    #    raise ParseError("Unable to partially update")

    @detail_route(methods=["PATCH"])
    def attach(self, request, pk):
        if not pk:
            raise ParseError("PK Not found")
        target = Target.objects.get(pk=pk)
        if not target:
            raise ParseError("Target DB instance not found with pk")
        lv = VolumeGroup(target.logical_volumes[0].group).get_logical_volumes(target.logical_volumes[0].name)
        if not lv:
            raise ParseError("Target disk not found")
        if target.active_snapshot:
            disk_path = lv.get_snapshots(target.active_snapshot.name)[0].get_path()
        else:
            disk_path = lv.get_path()
        iscsi_target = ISCSITarget(pk, target.name)
        if not iscsi_target.exists():
            if iscsi_target.add():
                pass
        if iscsi_target.exists():
            (lun, exists) = iscsi_target.get_logical_unit_number(disk_path)
            if lun and not exists:
                iscsi_target.attach_logical_unit(disk_path, lun)

    @detail_route(methods=["PATCH"])
    def detach(self, request, pk):
        if not pk:
            raise ParseError("PK Not found")
        target = Target.objects.get(pk=pk)
        if not target:
            raise ParseError("Target DB instance not found with pk")
        lv = VolumeGroup(target.group).get_logical_volumes(target.name)
        if not lv:
            raise ParseError("Target disk not found")
        if target.active_snapshot:
            disk_path = lv.get_snapshots(target.active_snapshot.name)[0].get_path()
        else:
            disk_path = lv.get_path()
        iscsi_target = ISCSITarget(pk, target.name)
        if iscsi_target.exists():
            (lun, exists) = iscsi_target.get_logical_unit_number(disk_path)
            if lun and exists:
                iscsi_target.detach_logical_unit(lun)


    @detail_route(methods=["PATCH"])
    def activate(self, request, pk):
        if not pk:
            raise ParseError("PK Not found")
        target = Target.objects.get(pk=pk)
        if not target:
            raise ParseError("Target DB instance not found with pk")
        lv = VolumeGroup(target.logical_volumes[0].group).get_logical_volumes(target.logical_volumes[0].name)
        if not lv:
            raise ParseError("Target disk not found")
        if target.active_snapshot:
            disk_path = lv.get_snapshots(target.active_snapshot.name)[0].get_path()
        else:
            disk_path = lv.get_path()
        iscsi_target = ISCSITarget(pk, target.name)
        if not iscsi_target.exists():
            if iscsi_target.add():
                pass
        if iscsi_target.exists():
            (lun, exists) = iscsi_target.get_logical_unit_number(disk_path)
            if lun and not exists:
                iscsi_target.attach_logical_unit(disk_path, lun)
        if iscsi_target.exists():
            iscsi_target.bind_to_initiator()

    @detail_route(methods=["PATCH"])
    def deactivate(self, request, pk):
        if not pk:
            raise ParseError("PK Not found")
        target = Target.objects.get(pk=pk)
        if not target:
            raise ParseError("Target DB instance not found with pk")
        lv = VolumeGroup(target.group).get_logical_volumes(target.name)
        if not lv:
            raise ParseError("Target disk not found")
        if target.active_snapshot:
            disk_path = lv.get_snapshots(target.active_snapshot.name)[0].get_path()
        else:
            disk_path = lv.get_path()
        iscsi_target = ISCSITarget(pk, target.name)
        if iscsi_target.exists():
            iscsi_target.unbind_from_initiator()
        if iscsi_target.exists():
            (lun, exists) = iscsi_target.get_logical_unit_number(disk_path)
            if lun and exists:
                iscsi_target.detach_logical_unit(lun)
        if iscsi_target.exists():
            if iscsi_target.remove():
                pass


class LogicalUnitViewSet(viewsets.ModelViewSet):
    queryset = LogicalUnit.objects.all()
    serializer_class = LogicalUnitSerializer

    @staticmethod
    def get_logical_volume(pk):
        logical_unit = LogicalUnit.objects.get(pk=pk)
        if not logical_unit:
            return None
        return VolumeGroup(logical_unit.group).get_logical_volumes(logical_unit.name)

    @detail_route(methods=["PATCH"])
    def revert(self, request, pk):
        if not pk:
            raise ParseError("PK Not found")
        logical_volume = self.get_logical_volume(pk)
        if not logical_volume:
            raise ParseError("Logical volume not found")
        if request.data.__contains__('snapshot') and request.data.__getitem__('snapshot'):
            snapshots = logical_volume.get_snapshots(request.data.__getitem__('snapshot'))
        else:
            snapshots = logical_volume.get_snapshots()
        if snapshots:
            snap_name = snapshots[0].get_name()
            if logical_volume.revert_to_snapshot(snap_name):
                return Response("Successfully reverted to snapshot '%s'" % snap_name, status=status.HTTP_200_OK)
            return Response("Could not revert to snapshot '%s'" % snap_name, status=status.HTTP_417_EXPECTATION_FAILED)
        return Response("Could not find any snapshot to revert to.", status=status.HTTP_417_EXPECTATION_FAILED)

    @detail_route(methods=["PATCH"])
    def dump(self, request, pk):
        if not pk:
            raise ParseError("PK Not found")
        logical_volume = self.get_logical_volume(pk)
        if not logical_volume:
            raise ParseError("Logical volume not found")
        if request.data.__contains__('local_file') and request.data.__getitem__('local_file'):
            op = logical_volume.dump_to_image(request.data.__getitem__('local_file'))
            if op:
                message = "Successfully dumped the disk. Details: %s" % op
                status_code = status.HTTP_200_OK
            else:
                message = "Failed to dump the disk. Details: %s" % op
                status_code = status.HTTP_417_EXPECTATION_FAILED
            return Response(message, status=status_code)
        return Response("No valid 'local_file' key found", status=status.HTTP_400_BAD_REQUEST)

    @detail_route(methods=["PATCH"])
    def restore(self, request, pk=None):
        if not pk:
            raise ParseError("PK Not found")
        logical_volume = self.get_logical_volume(pk)
        if not logical_volume:
            raise ParseError("Target disk not found")
        if request.data.__contains__('local_file') and request.data.__getitem__('local_file'):
            op = logical_volume.restore_from_image(request.data.__getitem__('local_file'))
            if op:
                message = "Successfully restored the disk. Details: %s" % op
                status_code = status.HTTP_200_OK
            else:
                message = "Failed to restore the disk. Details: %s" % op
                status_code = status.HTTP_417_EXPECTATION_FAILED
            return Response(message, status=status_code)
        return Response("No valid 'local_file' key found", status=status.HTTP_400_BAD_REQUEST)

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
                if request.data.__contains__('boot') and request.data.__getitem__('root'):
                    boot = True if str(request.data.__getitem__('boot')).lower() == "true" else False
                    logical_unit.boot = boot
                if request.data.__contains__('active') and request.data.__getitem__('active'):
                    active = True if str(request.data.__getitem__('active')).lower() == "true" else False
                    logical_unit.active = active
                if request.data.__contains__('target') and request.data.__getitem__('target'):
                    logical_unit.target = Target.objects.get(pk=url_resolver(request.data.__getitem__('target')))
                logical_unit.save()
            return Response(LogicalUnitSerializer(instance=logical_unit, context={'request': request}).data)
        raise ParseError("Logical unit could not be created. %s" % status)

    def destroy(self, request, pk=None):
        logical_unit = LogicalUnit.objects.get(pk=pk)
        if logical_unit:
            vg = VolumeGroup(logical_unit.group)
            if vg and vg.contains_logical_volume(logical_unit.name) and vg.remove_logical_volume(logical_unit.name):
                logical_unit.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
        raise ParseError("Could not delete resource for some reason")


class SnapshotViewSet(viewsets.ModelViewSet):
    queryset = Snapshot.objects.all()
    serializer_class = SnapshotSerializer

    def create(self, request):
        if request.data.__contains__('name') and request.data.__contains__('logical_unit'):
            logical_unit = LogicalUnit.objects.get(pk=url_resolver(request.data.__getitem__('logical_unit')))
            if not logical_unit:
                raise ParseError("Logical unit not found.")
            lv = VolumeGroup(logical_unit.group).get_logical_volumes(logical_unit.name)
            size = float(request.data.__getitem__('size_in_gb')) if request.data.__contains__('size_in_gb') else 5.0
            if lv and not lv.contains_snapshot(request.data.__getitem__('name')) and\
                    lv.create_snapshot(request.data.__getitem__('name'), size):
                snapshot, created = Snapshot.objects.get_or_create(name=request.data.__getitem__('name'),
                                                                   logical_unit=logical_unit)
                if created:
                    snapshot.size_in_gb = size
                    snapshot.save()
                return Response(SnapshotSerializer(instance=snapshot, context={'request': request}).data)
            raise ParseError("Resource could not be created. %s" % status)
        raise ParseError("'name' & 'group' fields are required and should have valid data")

    def destroy(self, request, pk=None):
        snapshot = Snapshot.objects.get(pk=pk)
        if snapshot:
            lv = VolumeGroup(snapshot.logical_unit.group).get_logical_volumes(snapshot.logical_unit.name)
            if lv and lv.contains_snapshot(snapshot.name) and lv.remove_snapshot(snapshot.name):
                snapshot.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
        raise ParseError("Could not delete resource for some reason")
