from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.exceptions import ParseError
from rest_framework.decorators import detail_route, list_route
from api.models import Initiator, Target
from api.serializers import InitiatorSerializer, TargetSerializer
from lvm2.entities import VolumeGroup, LogicalVolume, Snapshot
from urllib.parse import urlparse
from django.urls import resolve

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
    def dump(self, request, pk=None):
        if request.data.__contains__('to_file'):
            target = Target.objects.get(pk=pk)
            if target:
                vg = VolumeGroup(target.group)
                if vg:
                    lv = vg.get_logical_volumes(target.name)
                    if lv and lv.dump_to_image(request.data.__getitem__('to_file')):
                        return Response("Successfully dumped the disk to file", status=status.HTTP_200_OK)
        return Response("Please provide valid file path as value to 'to_file' key in json format",
                        status=status.HTTP_400_BAD_REQUEST)

    @detail_route(methods=["PATCH"])
    def restore(self, request, pk=None):
        print(pk)
        print(repr(request.data))

    def create(self, request):
        if request.data.__contains__('name') and request.data.__contains__('group'):
            vg = VolumeGroup(request.data.__getitem__('group'))
            size = request.data.__getitem__('size_in_gb') if request.data.__contains__('size_in_gb') else 20.0
            if vg and vg.create_logical_volume(request.data.__getitem__('name'), size):
                target, created = Target.objects.get_or_create(name=request.data.__getitem__('name'),
                                                                group=request.data.__getitem__('group'))
                if created:
                    print(size)
                    print(type(size))
                    target.size_in_gb = float(size)
                    if request.data.__contains__('initiator'):
                        target.initiator = Initiator.objects.get(pk=url_resolver(request.data.__getitem__('initiator')))
                    if request.data.__contains__('boot'):
                        boot = True if str(request.data.__getitem__('boot')).lower() == "true" else False
                        target.boot = boot
                    if request.data.__contains__('active'):
                        active = True if str(request.data.__getitem__('active')).lower() == "true" else False
                        target.active = active
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
