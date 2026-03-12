from rest_framework import status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

from .models import ScriptTemplate, RouterScriptExecution
from .serializers import ScriptTemplateSerializer, RouterScriptExecutionSerializer

class ScriptTemplateViewSet(ModelViewSet):
    queryset = ScriptTemplate.objects.all()
    serializer_class = ScriptTemplateSerializer
    permission_classes = [IsAuthenticated]


class RouterScriptExecutionViewSet(ModelViewSet):
    queryset = RouterScriptExecution.objects.all()
    serializer_class = RouterScriptExecutionSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer: RouterScriptExecutionSerializer) -> None:
        serializer.save(status="PENDING")
