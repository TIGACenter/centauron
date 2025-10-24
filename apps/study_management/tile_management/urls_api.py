from django.urls import path

from apps.study_management.tile_management.api import AddFileToTileSet

urlpatterns = [
    path('tileset/<uuid:tileset_pk>/add/', AddFileToTileSet.as_view()),

]
