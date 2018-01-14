from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.exceptions import ParseError
from rest_framework.decorators import detail_route
from api.models import Initiator, Target
from api.serializers import InitiatorSerializer, TargetSerializer
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
    def activate(self, request, pk):
        if not pk:
            raise ParseError("PK Not found")
        target = Target.objects.get(pk=pk)
        if not target:
            raise ParseError("Target DB instance not found with pk")
        lv = VolumeGroup(target.group).get_logical_volumes(target.name)
        if not lv:
            raise ParseError("Target disk not found")
        iscsi_target = ISCSITarget(pk, target.name)
        if not iscsi_target.exists():
            if iscsi_target.add():
                pass
        if iscsi_target.exists():
            (lun, exists) = iscsi_target.get_logical_unit_number(lv.get_path())
            if lun and not exists:
                iscsi_target.attach_logical_unit(lv.get_path(), lun)

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
        iscsi_target = ISCSITarget(pk, target.name)
        if iscsi_target.exists():
            (lun, exists) = iscsi_target.get_logical_unit_number(lv.get_path())
            if lun and exists:
                iscsi_target.detach_logical_unit(lun)
        if iscsi_target.exists():
            if iscsi_target.remove():
                pass

    @detail_route(methods=["PATCH"])
    def dump(self, request, pk):
        if not pk:
            raise ParseError("PK Not found")
        target = Target.objects.get(pk=pk)
        if not target:
            raise ParseError("Target DB instance not found with pk")
        lv = VolumeGroup(target.group).get_logical_volumes(target.name)
        if not lv:
            raise ParseError("Target disk not found")
        if request.data.__contains__('local_file') and request.data.__getitem__('local_file'):
            op = lv.dump_to_image(request.data.__getitem__('local_file'))
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
        target = Target.objects.get(pk=pk)
        if not target:
            raise ParseError("Target DB instance not found with pk")
        lv = VolumeGroup(target.group).get_logical_volumes(target.name)
        if not lv:
            raise ParseError("Target disk not found")
        if request.data.__contains__('local_file') and request.data.__getitem__('local_file'):
            op = lv.restore_from_image(request.data.__getitem__('local_file'))
            if op:
                message = "Successfully restored the disk. Details: %s" % op
                status_code = status.HTTP_200_OK
            else:
                message = "Failed to restore the disk. Details: %s" % op
                status_code = status.HTTP_417_EXPECTATION_FAILED
            return Response(message, status=status_code)
        return Response("No valid 'local_file' key found", status=status.HTTP_400_BAD_REQUEST)

    def create(self, request):
        if request.data.__contains__('name') and request.data.__contains__('group'):
            vg = VolumeGroup(request.data.__getitem__('group'))
            size = float(request.data.__getitem__('size_in_gb')) if request.data.__contains__('size_in_gb') else 20.0
            if vg and vg.create_logical_volume(request.data.__getitem__('name'), size):
                target, created = Target.objects.get_or_create(name=request.data.__getitem__('name'),
                                                                group=request.data.__getitem__('group'))
                if created:
                    target.size_in_gb = size
                    if request.data.__contains__('boot') and request.data.__getitem__('root'):
                        boot = True if str(request.data.__getitem__('boot')).lower() == "true" else False
                        target.boot = boot
                    if request.data.__contains__('active') and request.data.__getitem__('active'):
                        active = True if str(request.data.__getitem__('active')).lower() == "true" else False
                        target.active = active
                    if request.data.__contains__('initiator') and request.data.__getitem__('initiator'):
                        target.initiator = Initiator.objects.get(pk=url_resolver(request.data.__getitem__('initiator')))
                    target.save()
                return Response(TargetSerializer(instance=target, context={'request': request}).data)
            raise ParseError("Resource could not be created. %s" % status)
        raise ParseError("'name' & 'group' fields are required and should have valid data")

    def destroy(self, request, pk=None):
        target = Target.objects.get(pk=pk)
        if target:
            vg = VolumeGroup(target.group)
            if vg and vg.remove_logical_volume(target.name):
                target.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
        raise ParseError("Could not delete resource for some reason")
