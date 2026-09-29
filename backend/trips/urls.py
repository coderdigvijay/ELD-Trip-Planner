from django.urls import path
from drf_spectacular.views import SpectacularJSONAPIView, SpectacularSwaggerSplitView

from trips.views import HealthView

urlpatterns = [
    path("health", HealthView.as_view(), name="health"),
    path("schema", SpectacularJSONAPIView.as_view(), name="schema"),
    # Split view: the init script is a separate same-origin request, so the CSP needs no inline script.
    path("docs", SpectacularSwaggerSplitView.as_view(url_name="schema"), name="docs"),
]
