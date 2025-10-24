from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.study_management.tile_management import datatables
from apps.study_management.tile_management.views import CreateTileSetView, CreateTileSetFilterView, FileSetDetailView, \
    ExportView, CreateByFileUpload, ExportCSV, UpdateView, CopyView, LockView, ShareView

router = DefaultRouter()
router.register('tileset-files', datatables.TileSetFilesViewSet, basename='tileset-files')
router.register('tileset-list', datatables.TileSetFilesViewSet, basename='tileset')

urlpatterns = [
                  path('create/', CreateTileSetView.as_view(), name='create'),
                  path('filter/', CreateTileSetFilterView.as_view(), name='filter'),
                  path('<uuid:tileset_pk>/', FileSetDetailView.as_view(), name='detail'),
                  path('<uuid:tileset_pk>/export/', ExportView.as_view(), name='export'),
                  path('<uuid:tileset_pk>/export-csv/', ExportCSV.as_view(), name='export-csv'),
                  path('<uuid:tileset_pk>/update/', UpdateView.as_view(), name='update'),
                  path('<uuid:tileset_pk>/copy/', CopyView.as_view(), name='copy'),
                  path('<uuid:tileset_pk>/lock/', LockView.as_view(), name='lock'),
                  path('<uuid:tileset_pk>/share/', ShareView.as_view(), name='share'),
                  path('create/file_upload/', CreateByFileUpload.as_view(), name='file-upload'),
              ] + router.urls
