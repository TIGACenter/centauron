from rest_framework.routers import SimpleRouter

from apps.project.project_case import datatables

router = SimpleRouter()
router.register('datatable-case', datatables.CaseTableView, 'case')

urlpatterns = [
    # path('<uuid:project_pk>/new/', CreateCaseFormView.as_view(), name='new')
] + router.urls
