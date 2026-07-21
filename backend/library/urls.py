"""URL routes for the Luma library."""

from django.urls import path

from . import views

app_name = 'library'

urlpatterns = [
    path('', views.CatalogView.as_view(), name='catalog'),
    path('<slug:slug>/read/', views.BookReadView.as_view(), name='book-read'),
    path('<slug:slug>/', views.BookDetailView.as_view(), name='book-detail'),
]
