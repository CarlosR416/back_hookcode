from rest_framework.routers import DefaultRouter
from .views import ScriptTemplateViewSet, RouterScriptExecutionViewSet

app_name = "scripts"

router = DefaultRouter()
router.register("templates", ScriptTemplateViewSet, basename="script-templates")
router.register("executions", RouterScriptExecutionViewSet, basename="script-executions")

urlpatterns = router.urls
