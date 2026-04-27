from django.contrib import admin
from django.urls import path, include
from . import swagger

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/v1/auth/", include("authentication.urls")),
    path("docs/", swagger.schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("redoc/", swagger.schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),

]
