from django.urls import path, include

from apps.federation import views

urlpatterns = [
    # path('certificates/', views.CertificateView.as_view(), name='certificate'),
    # path('cert_token/', views.CertView.as_view(), name='certificate-token'),
    # path('import/', views.ImportFormView.as_view(), name='import'),
    # path('retrieve/', views.ImportInboxMessage.as_view(), name='retrieve'),
    path('', views.MyCodeView.as_view(), name='index'),
    path('nodes/', views.NodeListView.as_view(), name='node-list'),
    path('nodes/add/', views.AddNodeView.as_view(), name='add-node'),
    path('nodes/delete/<uuid:pk>/', views.DeleteNodeView.as_view(), name='delete-node'),
    path('transfer/', include(('apps.federation.file_transfer.urls', 'file_transfer'))),
    path('invitation/', include(('apps.federation.federation_invitation.urls', 'invitation')))
]
