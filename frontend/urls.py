from django.urls import path
from .views import (
    ResearchCreateView,
    ResearchDetailView,
    UserResearchListView,
    ResearchUpdateView,
    ResearchDeleteView,
    SiteCreateView,
    EvidenceCreateView,
    SiteListView,
    SiteDetailView,
    SiteUpdateView,
    SiteDeleteView,

)
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('user/<str:username>', UserResearchListView.as_view(), name='user-researches'),
    #path('post/<int:pk>/', PostDetailView.as_view(), name='post-detail'),
    path('research/<int:pk>/', ResearchDetailView.as_view(), name='research-detail'),
    path('research/new_research/', ResearchCreateView.as_view(), name='create-research'),
    path('research/<int:pk>/update/', ResearchUpdateView.as_view(), name='research-update'),
    path('research/<int:pk>/delete/', ResearchDeleteView.as_view(), name='research-delete'),
    path('api/preview-shapefile/', views.preview_shapefile, name='preview_shapefile'),
    path('site_create/', views.SiteCreateView.as_view(), name='site_create'),
    path('evidence_create/', views.EvidenceCreateView.as_view(), name='evidence_create'),
    path('ajax/load-typologies/', views.load_typologies, name='ajax_load_typologies'),
    path('ajax/load-typology-details/', views.load_typology_details, name='ajax_load_typology_details'),
    path('ajax/load-provinces/', views.load_provinces, name='ajax_load_provinces'),
    path('ajax/load-municipalities/', views.load_municipalities, name='ajax_load_municipalities'),
    path('sites/', SiteListView.as_view(), name='site_list'),
    path('site/<int:pk>/', SiteDetailView.as_view(), name='site_detail'),
    path('site/<int:pk>/update/', SiteUpdateView.as_view(), name='site_update'),
    path('site/<int:pk>/delete/', SiteDeleteView.as_view(), name='site_delete'),
    path('ajax/search-authors/', views.search_authors, name='ajax_search_authors'),



]
