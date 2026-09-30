"""Root URLs. Everything lives under /api/v1/; errors are always JSON, never HTML."""

from django.conf import settings
from django.urls import include, path, re_path

from trips.views import DocsAssetView

handler400 = "trips.errors.handler400"
handler404 = "trips.errors.handler404"
handler500 = "trips.errors.handler500"

urlpatterns = [
    path("api/v1/", include("trips.urls")),
    # Swagger UI assets are self-hosted (no CDN, no whitenoise). STATIC_URL points here.
    re_path(
        rf"^{settings.STATIC_URL.lstrip('/')}(?P<path>.*)$",
        DocsAssetView.as_view(),
        name="docs-assets",
    ),
]
