from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.study_management import datatables
from apps.study_management.views import StudyListView, StudyDetailView, StudyArmDetailView, \
    StudyArmTabTilesetsDetailView, StudyArmTabFilesExportView, StudyArmTabCasesDetailView, \
    StudyArmCreateImportFolderView, ExportImportedFilesAsCSV, CreateCaseView, add_files_to_case_form_view, \
    CaseFileTableView, StudyCreateView, DeleteCaseView, TableActionView, UpdateView

router = DefaultRouter()
router.register(r'studies', datatables.StudyDataTableView, basename='studies')
router.register(r'cases', datatables.StudyArmCaseTableView, basename='study-arm')
router.register(r'files', datatables.StudyArmCaseFileTableView, basename='study-arm-case-files')
router.register(r'study-arm-files', datatables.StudyArmFileTableView, basename='study-arm-files')
router.register(r'study-arm-cases', datatables.StudyArmCaseTableView, basename='study-arm-cases')
router.register(r'study-arm-tilesets', datatables.StudyArmTileSetListSet, basename='study-arm-tilesets')

urlpatterns = [
                  path('', StudyListView.as_view(), name='list'),
                  path('create/', StudyCreateView.as_view(), name='create'),
                  path('<uuid:pk>/', StudyDetailView.as_view(), name='detail'),
                  path('<uuid:pk>/<uuid:arm_pk>/case/new/', CreateCaseView.as_view(), name='create-case'),
                  path('<uuid:pk>/<uuid:arm_pk>/case/delete/', DeleteCaseView.as_view(), name='delete-case'),
                  path('<uuid:pk>/<uuid:arm_pk>/case/<uuid:case_pk>/files/add/', add_files_to_case_form_view,
                       name='add-file-to-case'),
                  path('<uuid:pk>/<uuid:arm_pk>/', StudyArmDetailView.as_view(), name='arm-detail'),
                  path('<uuid:pk>/<uuid:arm_pk>/update/', UpdateView.as_view(), name='arm-update'),
                  path('<uuid:pk>/<uuid:arm_pk>/table-action/', TableActionView.as_view(), name='table-action'),
                  path('<uuid:pk>/<uuid:arm_pk>/files/export/', StudyArmTabFilesExportView.as_view(),
                       name='arm-export'),
                  path('<uuid:pk>/<uuid:arm_pk>/files/export-imported/', ExportImportedFilesAsCSV.as_view(),
                       name='arm-export-csv'),
                  path('<uuid:pk>/<uuid:arm_pk>/import-folder/', StudyArmCreateImportFolderView.as_view(),
                       name='arm-import-folder'),
                  path('<uuid:pk>/<uuid:arm_pk>/tilesets/', StudyArmTabTilesetsDetailView.as_view(),
                       name='arm-detail-tilesets'),
                  path('<uuid:pk>/<uuid:arm_pk>/cases/', StudyArmTabCasesDetailView.as_view(), name='arm-detail-cases'),
                  path('<uuid:pk>/<uuid:arm_pk>/import/',
                       include(('apps.study_management.import_data.urls', 'import_data'))),
                  path('<uuid:pk>/<uuid:arm_pk>/tile_management/',
                       include(('apps.study_management.tile_management.urls', 'tile_management'))),
                  path('<uuid:pk>/<uuid:arm_pk>/case/files/', CaseFileTableView.as_view(), name='case-files')
              ] + router.urls
