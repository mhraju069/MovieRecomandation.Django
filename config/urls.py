from django.contrib import admin
from django.urls import path, include
from . import swagger
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls')),
    path("api/v1/auth/", include("authentication.urls")),
    path("api/v1/subscription/", include("subscription.urls")),
    path("api/v1/payment/", include("payment.urls")),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("docs/", swagger.schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("redoc/", swagger.schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),

]
