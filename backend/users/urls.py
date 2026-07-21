"""URL configuration for the users app."""

from django.urls import path

from . import views

app_name = 'users'

urlpatterns = [
    path('register/', views.RegisterPageView.as_view(), name='register'),
    path('login/', views.LoginPageView.as_view(), name='login'),
    path('api/register/', views.RegisterAPIView.as_view(), name='api-register'),
    path('api/login/', views.LoginAPIView.as_view(), name='api-login'),
]
