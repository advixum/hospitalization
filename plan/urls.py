from django.urls import path
from . import views


app_name = 'plan'
urlpatterns = [
    path('', views.AuthView.as_view(), name='login'),
    path('logout/', views.ExitView.as_view(), name='logout'),
    path('main/', views.MainView.as_view(), name='main'),
    path('new/', views.NewPatientView.as_view(), name='new'),
    path('<int:pk>/', views.UpdatePatientView.as_view(), name='update'),
    path('table/', views.csv_response, name='table'),
    path('week/', views.week_list, name='week'),
    path(views.directory+'<path:filename>/', views.download),
    #path('test/', views.test, name='test'),
]