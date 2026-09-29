"""Root URLs. Everything lives under /api/v1/; errors are always JSON, never HTML."""

from pathlib import Path

import drf_spectacular_sidecar
from django.conf import settings
from django.urls import include, path, re_path
from django.views.static import serve

handler400 = "trips.errors.handler400"
handler404 = "trips.errors.handler404"
handler500 = "trips.errors.handler500"

_SIDECAR_STATIC = Path(drf_spectacular_sidecar.__file__).parent / "static"

urlpatterns = [
    path("api/v1/", include("trips.urls")),
    # Swagger UI assets are self-hosted (no CDN, no whitenoise). STATIC_URL points here.
    re_path(
        rf"^{settings.STATIC_URL.lstrip('/')}(?P<path>.*)$",
        serve,
        {"document_root": _SIDECAR_STATIC},
        name="docs-assets",
    ),
]
