from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import ScriptTemplateViewSet, RouterScriptExecutionViewSet, download_script

app_name = "scripts"

router = DefaultRouter()
router.register("templates", ScriptTemplateViewSet, basename="script-templates")
router.register("executions", RouterScriptExecutionViewSet, basename="script-executions")

urlpatterns = [
    path("download/<str:token>/", download_script, name="script-download"),
    *router.urls,
]
