from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.db import models
from django.shortcuts import render, get_object_or_404, redirect
from .shapefile_utils import extract_geometry_from_shapefile
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView
)
from collections import defaultdict
import re
import os
from django.core.files.storage import default_storage
from django.conf import settings
from .models import (
    Research, Author, Typology, TypologyDetail, ResearchAuthor, Province,
    Municipality, SiteResearch, Investigation, SiteBibliography, Sources, 
    SiteSources, Image, Bibliography, SiteRelatedDocumentation, ArchEvBiblio, 
    ArchEvSources, ArchEvRelatedDoc, ArchEvResearch, SiteInvestigation, 
    SiteArchEvidence, Site, ArchaeologicalEvidence, SiteToponymy, Interpretation,
    Chronology, SourcesType, ImageType, ImageScale
)
from django.urls import reverse_lazy, reverse
from django.contrib.staticfiles.views import serve
from .forms import ResearchForm, SiteForm, ArchaeologicalEvidenceForm
from .utils import parse_geometry_string, create_folium_map, get_or_create_author_for_user, create_user_and_author




def save_uploaded_image(image_file, subfolder='images'):
    """
    Save uploaded image file to media folder and return the accessible URL path.
    Returns: /media/images/filename.ext or None if save fails
    """
    if not image_file:
        return None
    
    try:
        # Sanitize filename - keep only alphanumeric, dots, hyphens, underscores
        filename = image_file.name
        filename = "".join(c for c in filename if c.isalnum() or c in '._-')
        
        if not filename:
            return None
        
        # Create subdirectory path
        media_path = f'{subfolder}/{filename}'
        
        # Save file to media folder
        file_path = default_storage.save(media_path, image_file)
        
        # Return accessible URL path
        return f'/media/{file_path}'
    except Exception as e:
        print(f"Error saving image: {e}")
        return None


def home(request):
    """
    Home page view with statistics
    """
    from django.db.models import Count
    # Get statistics for the homepage
    total_research = Research.objects.count()
    total_sites = Site.objects.count()
    total_evidence = ArchaeologicalEvidence.objects.count()
    total_users = User.objects.filter(is_active=True).count()
    
    context = {
        'total_research': total_research,
        'total_sites': total_sites,
        'total_evidence': total_evidence,
        'total_users': total_users,
    }
    return render(request, 'frontend/home.html', context)


def getfile(request):
    return serve(request, 'File')


class ResearchListView(LoginRequiredMixin, ListView):
    model = Research
    template_name = 'frontend/research_list.html'  # <app>/<model>_<viewtype>.html
    context_object_name = 'researches'
    ordering = ['-year']
    paginate_by = 5

    def get_queryset(self):
        return Research.objects.all().order_by('-year')


class PublicResearchListView(ListView):
    """
    Public view (no authentication required) to display all research with related sites and evidence
    """
    model = Research
    template_name = 'frontend/public_research_list.html'
    context_object_name = 'researches'
    ordering = ['-year']
    paginate_by = 10

    def get_queryset(self):
        return Research.objects.all().order_by('-year')


class PublicResearchDetailView(DetailView):
    """
    Public view (no authentication required) to display research details with all related sites and evidence
    """
    model = Research
    template_name = 'frontend/public_research_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        research = self.object

        # Get all sites related to this research (use values_list to avoid geometry comparison issues)
        site_ids = SiteResearch.objects.filter(id_research=research).values_list('id_site_id', flat=True)
        sites = Site.objects.filter(id__in=site_ids)
        
        # Get all archaeological evidence related to this research (directly)
        # Use values_list to get IDs first, then fetch objects to avoid geometry comparison
        direct_evidence_ids = ArchEvResearch.objects.filter(
            id_research=research.id
        ).values_list('id_archaeological_evidence_id', flat=True)
        direct_evidences = ArchaeologicalEvidence.objects.filter(id__in=direct_evidence_ids)
        
        # Get archaeological evidence linked through sites
        site_evidence_ids = SiteArchEvidence.objects.filter(
            id_site_id__in=site_ids
        ).values_list('id_archaeological_evidence_id', flat=True)
        site_evidences = ArchaeologicalEvidence.objects.filter(id__in=site_evidence_ids)
        
        # Combine all evidence IDs and fetch unique objects
        all_evidence_ids = set(list(direct_evidence_ids) + list(site_evidence_ids))
        all_evidences = ArchaeologicalEvidence.objects.filter(id__in=all_evidence_ids)
        
        # Get authors for this research (distinct to avoid duplicates)
        author_ids = ResearchAuthor.objects.filter(id_research=research).values_list('id_author_id', flat=True).distinct()
        authors = Author.objects.filter(id__in=author_ids)
        
        # For each site, get its related data
        sites_with_details = []
        for site in sites:
            # Get evidence IDs for this site (avoid distinct on geometry)
            site_evidence_ids_list = SiteArchEvidence.objects.filter(
                id_site_id=site.id
            ).values_list('id_archaeological_evidence_id', flat=True)
            site_evidences_list = ArchaeologicalEvidence.objects.filter(id__in=site_evidence_ids_list)
            
            site_data = {
                'site': site,
                'toponymy': SiteToponymy.objects.filter(id_site=site).first(),
                'interpretation': Interpretation.objects.filter(id_site=site).first(),
                'investigation': SiteInvestigation.objects.filter(id_site=site).select_related('id_investigation').first(),
                'bibliography': SiteBibliography.objects.filter(id_site=site).select_related('id_bibliography').first(),
                'sources': SiteSources.objects.filter(id_site=site).select_related('id_sources').first(),
                'related_doc': SiteRelatedDocumentation.objects.filter(id_site=site).first(),
                'images': Image.objects.filter(id_site=site).select_related('id_image_type', 'id_image_scale'),
                'evidences': site_evidences_list,
            }
            sites_with_details.append(site_data)
        
        # For each evidence, get its related data
        evidences_with_details = []
        for evidence in all_evidences:
            evidence_data = {
                'evidence': evidence,
                'bibliography': ArchEvBiblio.objects.filter(id_archaeological_evidence=evidence).select_related('id_bibliography').first(),
                'sources': ArchEvSources.objects.filter(id_archaeological_evidence=evidence).select_related('id_sources').first(),
                'related_doc': ArchEvRelatedDoc.objects.filter(id_archaeological_evidence=evidence).first(),
            }
            evidences_with_details.append(evidence_data)
        
        # Create Folium map for research geometry
        map_html = None
        if research.geometry:
            map_html = create_folium_map(
                research.geometry, 
                research_title=research.title or "Research Area"
            )
        
        # Add user and research info for permission checks in template
        context.update({
            'sites_with_details': sites_with_details,
            'evidences_with_details': evidences_with_details,
            'authors': authors,
            'map_html': map_html,
            'research_owner': research.submitted_by if research.submitted_by else None,
        })
        return context


class ResearchCatalogView(ListView):
    """Public catalog page with research → site → evidence tree."""
    model = Research
    template_name = 'frontend/research_catalog.html'
    context_object_name = 'researches'
    paginate_by = 5

    def get_queryset(self):
        queryset = Research.objects.all().select_related('submitted_by').order_by('title')
        search_query = self.request.GET.get('q', '').strip()
        
        if search_query:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(abstract__icontains=search_query) |
                Q(keywords__icontains=search_query)
            )
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        researches = list(context.get('researches', []))
        search_query = self.request.GET.get('q', '').strip()
        context['search_query'] = search_query

        if not researches:
            context['catalog_entries'] = []
            return context

        research_ids = [research.id for research in researches]

        site_links = SiteResearch.objects.filter(
            id_research_id__in=research_ids
        ).select_related('id_site')
        site_ids = [link.id_site_id for link in site_links]

        sites = Site.objects.filter(id__in=site_ids).select_related(
            'id_country', 'id_region', 'id_province', 'id_municipality'
        )
        site_by_id = {site.id: site for site in sites}

        site_map = defaultdict(list)
        for link in site_links:
            site = site_by_id.get(link.id_site_id)
            if site:
                site_map[link.id_research_id].append(site)

        site_evidence_links = SiteArchEvidence.objects.filter(
            id_site_id__in=site_ids
        ).select_related('id_archaeological_evidence')
        site_evidence_map = defaultdict(list)
        for relation in site_evidence_links:
            evidence = relation.id_archaeological_evidence
            if evidence:
                site_evidence_map[relation.id_site_id].append(evidence)

        direct_evidence_links = ArchEvResearch.objects.filter(
            id_research__in=research_ids
        ).select_related('id_archaeological_evidence')
        direct_evidence_map = defaultdict(list)
        for relation in direct_evidence_links:
            evidence = relation.id_archaeological_evidence
            if evidence:
                direct_evidence_map[relation.id_research].append(evidence)

        catalog_entries = []
        for research in researches:
            sites_payload = []
            for site in site_map.get(research.id, []):
                sites_payload.append({
                    'site': site,
                    'evidences': site_evidence_map.get(site.id, []),
                })

            catalog_entries.append({
                'research': research,
                'sites': sites_payload,
                'direct_evidences': direct_evidence_map.get(research.id, []),
            })

        context['catalog_entries'] = catalog_entries
        return context


class UserResearchListView(LoginRequiredMixin, ListView):
    model = Research
    template_name = 'frontend/user_research.html'  # <app>/<model>_<viewtype>.html
    context_object_name = 'researches'
    paginate_by = 5

    def get_queryset(self):
        user = get_object_or_404(User, username=self.kwargs.get('username'))
        return Research.objects.filter(submitted_by=user).order_by('-year')


class ResearchCreateView(LoginRequiredMixin, CreateView):
    model = Research
    form_class = ResearchForm
    template_name = 'frontend/research_form.html'

    def form_valid(self, form):
        form.instance.submitted_by = self.request.user

        # === Handle main author ===
        is_self_author = self.request.POST.get('is_self_author')
        if is_self_author == 'yes':
            # User is the main author - create/get Author and link to current user
            author = get_or_create_author_for_user(self.request.user)
        else:
            # Search for user or create new one
            user_id = self.request.POST.get('author_user_id')
            author_id = self.request.POST.get('author_id')
            
            if user_id:
                # User found - get or create Author for this user
                user = User.objects.get(pk=user_id)
                affiliation = self.request.POST.get('author_affiliation', '')
                orcid = self.request.POST.get('author_orcid', '')
                author = get_or_create_author_for_user(user, affiliation=affiliation, orcid=orcid)
            elif author_id:
                # Existing Author selected
                author = Author.objects.filter(pk=author_id).first()
                if not author:
                    form.add_error(None, 'Selected author not found')
                    return self.form_invalid(form)
            else:
                # Create new user and author
                author_name = self.request.POST.get('author_name')
                author_surname = self.request.POST.get('author_surname')
                author_email = self.request.POST.get('author_email')
                affiliation = self.request.POST.get('author_affiliation', '')
                orcid = self.request.POST.get('author_orcid', '')
                
                if not author_name or not author_surname or not author_email:
                    form.add_error(None, 'Name, surname, and email are required for new author')
                    return self.form_invalid(form)
                
                # Check if user already exists
                existing_user = User.objects.filter(email=author_email).first()
                if existing_user:
                    author = get_or_create_author_for_user(existing_user, affiliation=affiliation, orcid=orcid)
                else:
                    author = create_user_and_author(
                        author_name, author_surname, author_email, 
                        affiliation=affiliation, orcid=orcid
                    )

        form.instance.author = author

        # === Handle shapefile → geometry ===
        shapefile = self.request.FILES.get('shapefile')
        if shapefile:
            try:
                geometry = extract_geometry_from_shapefile(shapefile)
                form.instance.geometry = geometry
            except ValidationError as e:
                form.add_error('shapefile', e)
                return self.form_invalid(form)

        # === Save research ===
        self.object = form.save()

        # === Add to ResearchAuthor table (using get_or_create to avoid duplicates) ===
        ResearchAuthor.objects.get_or_create(id_research=self.object, id_author=author)

        # === Handle co-authors ===
        index = 0
        while True:
            co_user_id = self.request.POST.get(f'coauthor_user_id_{index}')
            co_id = self.request.POST.get(f'coauthor_id_{index}')
            
            if co_user_id:
                # User found - get or create Author for this user
                co_user = User.objects.filter(pk=co_user_id).first()
                if co_user:
                    co_affiliation = self.request.POST.get(f'coauthor_affiliation_{index}', '')
                    co_orcid = self.request.POST.get(f'coauthor_orcid_{index}', '')
                    co = get_or_create_author_for_user(co_user, affiliation=co_affiliation, orcid=co_orcid)
                    ResearchAuthor.objects.get_or_create(id_research=self.object, id_author=co)
            elif co_id:
                # Existing Author selected
                co = Author.objects.filter(pk=co_id).first()
                if co:
                    ResearchAuthor.objects.get_or_create(id_research=self.object, id_author=co)
            else:
                # Check if new co-author fields are provided
                name = self.request.POST.get(f'coauthor_name_{index}')
                surname = self.request.POST.get(f'coauthor_surname_{index}')
                email = self.request.POST.get(f'coauthor_email_{index}')

                if name and surname and email:
                    # Check if user exists
                    existing_user = User.objects.filter(email=email).first()
                    if existing_user:
                        co_affiliation = self.request.POST.get(f'coauthor_affiliation_{index}', '')
                        co_orcid = self.request.POST.get(f'coauthor_orcid_{index}', '')
                        co = get_or_create_author_for_user(existing_user, affiliation=co_affiliation, orcid=co_orcid)
                    else:
                        # Create new user and author
                        co_affiliation = self.request.POST.get(f'coauthor_affiliation_{index}', '')
                        co_orcid = self.request.POST.get(f'coauthor_orcid_{index}', '')
                        co = create_user_and_author(
                            name, surname, email,
                            affiliation=co_affiliation, orcid=co_orcid
                        )
                    ResearchAuthor.objects.get_or_create(id_research=self.object, id_author=co)
                else:
                    break
            index += 1

        return render(self.request, 'frontend/research_success.html', {'research': self.object})


class ResearchDetailView(LoginRequiredMixin, DetailView):
    model = Research
    template_name = 'frontend/research_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        research = self.object

        # Get unique sites linked to this research (avoid duplicates)
        site_ids = SiteResearch.objects.filter(id_research=research).values_list('id_site_id', flat=True).distinct()
        unique_sites = Site.objects.filter(id__in=site_ids)
        
        # Get authors for this research (distinct to avoid duplicates)
        author_ids = ResearchAuthor.objects.filter(id_research=research).values_list('id_author_id', flat=True).distinct()
        authors = Author.objects.filter(id__in=author_ids)
        
        # For each site, get its related data (similar to public view)
        sites_with_details = []
        for site in unique_sites:
            # Get evidence IDs for this site
            site_evidence_ids_list = SiteArchEvidence.objects.filter(
                id_site_id=site.id
            ).values_list('id_archaeological_evidence_id', flat=True)
            site_evidences_list = ArchaeologicalEvidence.objects.filter(id__in=site_evidence_ids_list)
            
            site_data = {
                'site': site,
                'toponymy': SiteToponymy.objects.filter(id_site=site).first(),
                'interpretation': Interpretation.objects.filter(id_site=site).first(),
                'investigation': SiteInvestigation.objects.filter(id_site=site).select_related('id_investigation').first(),
                'bibliography': SiteBibliography.objects.filter(id_site=site).select_related('id_bibliography').first(),
                'sources': SiteSources.objects.filter(id_site=site).select_related('id_sources').first(),
                'related_doc': SiteRelatedDocumentation.objects.filter(id_site=site).first(),
                'evidences': site_evidences_list,
            }
            sites_with_details.append(site_data)

        # Evidences linked directly to research (not linked to a site)
        direct_evidence_ids = ArchEvResearch.objects.filter(
            id_research=research.id
        ).values_list('id_archaeological_evidence_id', flat=True)
        direct_evidences = ArchaeologicalEvidence.objects.filter(id__in=direct_evidence_ids)
        
        # For each evidence, get its related data
        evidences_with_details = []
        for evidence in direct_evidences:
            evidence_data = {
                'evidence': evidence,
                'bibliography': ArchEvBiblio.objects.filter(id_archaeological_evidence=evidence).select_related('id_bibliography').first(),
                'sources': ArchEvSources.objects.filter(id_archaeological_evidence=evidence).select_related('id_sources').first(),
                'related_doc': ArchEvRelatedDoc.objects.filter(id_archaeological_evidence=evidence).first(),
            }
            evidences_with_details.append(evidence_data)

        context['sites_with_details'] = sites_with_details
        context['evidences_with_details'] = evidences_with_details
        context['authors'] = authors
        
        # Create Folium map for research geometry
        map_html = None
        if research.geometry:
            map_html = create_folium_map(
                research.geometry, 
                research_title=research.title or "Research Area"
            )
        context['map_html'] = map_html
        context['research_owner'] = research.submitted_by if research.submitted_by else None
        
        return context


from .forms import ResearchForm  # assicurati che sia importato


class ResearchUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Research
    form_class = ResearchForm
    template_name = 'frontend/research_form.html'

    def get_success_url(self):
        return reverse_lazy('user-researches', kwargs={'username': self.request.user.username})

    def get_initial(self):
        initial = super().get_initial()
        research = self.get_object()
        # All model fields are automatically prefilled by ModelForm
        # This just ensures geometry and other fields are available
        initial['title'] = research.title
        initial['year'] = research.year
        initial['keywords'] = research.keywords
        initial['abstract'] = research.abstract
        initial['type'] = research.type
        initial['geometry'] = research.geometry
        return initial

    def form_valid(self, form):
        form.instance.submitted_by = self.request.user
        return super().form_valid(form)

    def test_func(self):
        """
        Allow admin to update any research, or user to update their own research
        """
        research = self.get_object()
        return self.request.user.is_staff or self.request.user == research.submitted_by


class ResearchDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Research
    template_name = 'frontend/research_confirm_delete.html'

    def get_success_url(self):
        return reverse_lazy('user-researches', kwargs={'username': self.request.user.username})

    def test_func(self):
        """
        Allow admin to update any research, or user to update their own research
        """
        research = self.get_object()
        return self.request.user.is_staff or self.request.user == research.submitted_by


def load_typologies(request):
    functional_class_id = request.GET.get('functional_class')
    typologies = Typology.objects.filter(id_functional_class=functional_class_id).values('id', 'desc_typology')
    return JsonResponse(list(typologies), safe=False)


def load_typology_details(request):
    typology_id = request.GET.get('typology')
    details = TypologyDetail.objects.filter(id_typology=typology_id).values('id', 'desc_typology_detail')
    return JsonResponse(list(details), safe=False)


# frontend/views.py
def load_provinces(request):
    codice_regione = request.GET.get('region')
    if not codice_regione:
        return JsonResponse([], safe=False)

    # Forza codice_regione come stringa per confrontarla con un campo text
    provinces = Province.objects.filter(codice_regione=int(codice_regione)).values('id', 'sigla_provincia',
                                                                                   'denominazione_provincia')
    return JsonResponse(list(provinces), safe=False)


def load_municipalities(request):
    id_province = request.GET.get("province")
    if not id_province:
        return JsonResponse([], safe=False)

    municipalities = Municipality.objects.filter(id_province=id_province).values("id", "denominazione_comune")
    return JsonResponse(list(municipalities), safe=False)


@csrf_exempt
def preview_shapefile(request):
    if request.method == 'POST' and request.FILES.get('shapefile'):
        try:
            geometry_text = extract_geometry_from_shapefile(request.FILES['shapefile'])
            return JsonResponse({'geometry': geometry_text})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)


from .models import SiteToponymy, Interpretation


def search_authors(request):
    """
    Search for authors/users by surname (priority), then username, then email.
    Searches directly in User model (auth_user table), then in Author model.
    """
    query = request.GET.get('q', '').strip()
    results = []
    if query and len(query) >= 3:  # Minimum 3 characters
        from users.models import Profile
        from django.db.models import Q
        
        # Get all user IDs that match any criteria to avoid duplicates
        matched_user_ids = set()
        matched_author_emails = set()
        
        # 1. Search by surname through Profile (highest priority)
        profile_surname_matches = Profile.objects.filter(
            surname__icontains=query
        ).select_related('user').distinct()
        surname_user_ids = {p.user.id for p in profile_surname_matches}
        matched_user_ids.update(surname_user_ids)
        
        # 2. Search by username in User model (medium priority)
        user_username_matches = User.objects.filter(
            username__icontains=query
        ).exclude(id__in=matched_user_ids).distinct()
        username_user_ids = {u.id for u in user_username_matches}
        matched_user_ids.update(username_user_ids)
        
        # 3. Search by email in User model (lowest priority)
        user_email_matches = User.objects.filter(
            email__icontains=query
        ).exclude(id__in=matched_user_ids).distinct()
        email_user_ids = {u.id for u in user_email_matches}
        matched_user_ids.update(email_user_ids)
        
        # Process surname matches (highest priority)
        surname_results = []
        for profile in profile_surname_matches[:10]:
            user = profile.user
            matched_author_emails.add(user.email.lower() if user.email else '')
            
            # Check if user has an author record
            author = Author.objects.filter(user=user).first()
            
            surname_results.append({
                'type': 'user',
                'user_id': user.id,
                'username': user.username,
                'id': str(author.id) if author else None,
                'name': profile.name or user.first_name or '',
                'surname': profile.surname or user.last_name or '',
                'email': user.email or '',
                'affiliation': profile.affiliation or '',
                'orcid': profile.orcid or '',
                'has_author': author is not None,
                'match_type': 'surname'
            })
        
        # Process username matches (medium priority)
        username_results = []
        remaining_slots = 10 - len(surname_results)
        if remaining_slots > 0:
            for user in user_username_matches[:remaining_slots]:
                matched_author_emails.add(user.email.lower() if user.email else '')
                
                try:
                    profile = user.profile
                    # Check if user has an author record
                    author = Author.objects.filter(user=user).first()
                    
                    username_results.append({
                        'type': 'user',
                        'user_id': user.id,
                        'username': user.username,
                        'id': str(author.id) if author else None,
                        'name': profile.name or user.first_name or '',
                        'surname': profile.surname or user.last_name or '',
                        'email': user.email or '',
                        'affiliation': profile.affiliation or '',
                        'orcid': profile.orcid or '',
                        'has_author': author is not None,
                        'match_type': 'username'
                    })
                except Profile.DoesNotExist:
                    # User without profile - use User fields directly
                    author = Author.objects.filter(user=user).first()
                    
                    username_results.append({
                        'type': 'user',
                        'user_id': user.id,
                        'username': user.username,
                        'id': str(author.id) if author else None,
                        'name': user.first_name or '',
                        'surname': user.last_name or '',
                        'email': user.email or '',
                        'affiliation': '',
                        'orcid': '',
                        'has_author': author is not None,
                        'match_type': 'username'
                    })
        
        # Process email matches (lowest priority)
        email_results = []
        remaining_slots = 10 - len(surname_results) - len(username_results)
        if remaining_slots > 0:
            for user in user_email_matches[:remaining_slots]:
                matched_author_emails.add(user.email.lower() if user.email else '')
                
                # Check if user has an author record
                author = Author.objects.filter(user=user).first()
                
                # Try to get profile, but don't fail if it doesn't exist
                try:
                    profile = user.profile
                    name = profile.name or user.first_name or ''
                    surname = profile.surname or user.last_name or ''
                    affiliation = profile.affiliation or ''
                    orcid = profile.orcid or ''
                except (Profile.DoesNotExist, AttributeError):
                    # User without profile - use User fields directly
                    name = user.first_name or ''
                    surname = user.last_name or ''
                    affiliation = ''
                    orcid = ''
                
                email_results.append({
                    'type': 'user',
                    'user_id': user.id,
                    'username': user.username,
                    'id': str(author.id) if author else None,
                    'name': name,
                    'surname': surname,
                    'email': user.email or '',
                    'affiliation': affiliation,
                    'orcid': orcid,
                    'has_author': author is not None,
                    'match_type': 'email'
                })
        
        # Combine results in priority order
        results.extend(surname_results)
        results.extend(username_results)
        results.extend(email_results)
        
        # Also search in existing Author model (for authors not linked to users)
        # Exclude authors whose users we've already shown
        remaining_slots = 10 - len(results)
        if remaining_slots > 0:
            author_surname_matches = Author.objects.filter(
                surname__icontains=query,
                user__isnull=True  # Only authors without linked users
            ).distinct()[:remaining_slots]
            
            for author in author_surname_matches:
                results.append({
                    'type': 'author',
                    'id': str(author.id),
                    'name': author.name or '',
                    'surname': author.surname or '',
                    'email': author.contact_email or '',
                    'affiliation': author.affiliation or '',
                    'orcid': author.orcid or '',
                    'has_author': True,
                    'match_type': 'surname'
                })
            
            remaining_slots = 10 - len(results)
            if remaining_slots > 0:
                author_email_matches = Author.objects.filter(
                    contact_email__icontains=query,
                    user__isnull=True  # Only authors without linked users
                ).exclude(
                    id__in=[int(a['id']) for a in results if a.get('type') == 'author' and a.get('id')]
                ).distinct()[:remaining_slots]
                
                for author in author_email_matches:
                    results.append({
                        'type': 'author',
                        'id': str(author.id),
                        'name': author.name or '',
                        'surname': author.surname or '',
                        'email': author.contact_email or '',
                        'affiliation': author.affiliation or '',
                        'orcid': author.orcid or '',
                        'has_author': True,
                        'match_type': 'email'
                    })
    
    return JsonResponse(results[:10], safe=False)


class SiteCreateView(LoginRequiredMixin, CreateView):
    model = Site
    form_class = SiteForm
    template_name = 'frontend/site_form.html'

    def get_success_url(self):
        research_id = self.request.GET.get('research_id')
        if research_id:
            return reverse('research-detail', args=[research_id])
        return reverse('evidence_list')  # fallback if no research_id

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['chronologies'] = Chronology.objects.all()
        context['source_types'] = SourcesType.objects.all()
        context['image_types'] = ImageType.objects.all()
        context['image_scales'] = ImageScale.objects.all()
        return context

    def form_valid(self, form):

        # Optional: build geometry from lat/lon
        lat = form.cleaned_data.get('lat')
        lon = form.cleaned_data.get('lon')
        if lat and lon:
            form.instance.geometry = (float(lon), float(lat))

        response = super().form_valid(form)  # Save the Site instance
        site = self.object

        # Save SiteToponymy
        ancient_name = form.cleaned_data.get('ancient_place_name')
        contemporary_name = form.cleaned_data.get('contemporary_place_name')

        if ancient_name or contemporary_name:
            SiteToponymy.objects.create(
                id_site=site,
                ancient_place_name=ancient_name,
                contemporary_place_name=contemporary_name
            )

        # Save Interpretation
        functional_class = form.cleaned_data.get('functional_class')
        typology = form.cleaned_data.get('typology')
        typology_detail = form.cleaned_data.get('typology_detail')
        chronology = form.cleaned_data.get('chronology')
        certainty = form.cleaned_data.get('chronology_certainty_level') or 1

        if functional_class or typology or typology_detail or chronology:
            Interpretation.objects.create(
                id_site=site,
                id_functional_class=functional_class,
                id_typology=typology,
                id_typology_detail=typology_detail,
                id_chronology=chronology,
                chronology_certainty_level=certainty
            )

        # Save SiteResearch relationship
        research_id = self.request.GET.get('research_id')
        if research_id:
            try:
                research = Research.objects.get(pk=research_id)
                SiteResearch.objects.create(id_site=site, id_research=research)
            except Research.DoesNotExist:
                pass

        # Save Investigation
        project_name = form.cleaned_data.get('project_name')
        periodo = form.cleaned_data.get('periodo')
        investigation_type = form.cleaned_data.get('investigation_type')

        if project_name and periodo and investigation_type:
            investigation, created = Investigation.objects.update_or_create(
                project_name=project_name,
                defaults={
                    'period': periodo,
                    'id_investigation_type': investigation_type
                }
            )
            # Associate the investigation with the site
            SiteInvestigation.objects.update_or_create(
                id_site=site,
                id_investigation=investigation
            )

        # Save multiple bibliographies
        # Collect all bibliography fields from POST data
        biblio_index = 0
        while True:
            title = self.request.POST.get(f'biblio_title_{biblio_index}')
            author = self.request.POST.get(f'biblio_author_{biblio_index}')
            year = self.request.POST.get(f'biblio_year_{biblio_index}')
            doi = self.request.POST.get(f'biblio_doi_{biblio_index}')
            tipo = self.request.POST.get(f'biblio_tipo_{biblio_index}')
            
            # Break if no more bibliography entries
            if title is None:
                break
            
            # Only save if at least one field is filled
            if title or author or year or doi or tipo:
                bibliography = Bibliography.objects.create(
                    title=title or '',
                    author=author or '',
                    year=int(year) if year else None,
                    doi=doi or '',
                    tipo=tipo or ''
                )
                SiteBibliography.objects.create(
                    id_site=site,
                    id_bibliography=bibliography
                )
            
            biblio_index += 1

        # Save multiple sources
        source_index = 0
        while True:
            source_name = self.request.POST.get(f'source_name_{source_index}')
            if source_name is None:
                break
            
            # Only save if at least one field is filled
            chronology_id = self.request.POST.get(f'source_chronology_{source_index}')
            source_type_id = self.request.POST.get(f'source_type_{source_index}')
            
            if source_name or chronology_id or source_type_id:
                source = Sources.objects.create(
                    name=source_name or '',
                    id_chronology_id=chronology_id if chronology_id else None,
                    id_sources_typology_id=source_type_id if source_type_id else None
                )
                SiteSources.objects.create(
                    id_site=site,
                    id_sources=source
                )
            
            source_index += 1

        # Save multiple related documentations
        doc_index = 0
        while True:
            doc_name = self.request.POST.get(f'doc_name_{doc_index}')
            if doc_name is None:
                break
            
            # Only save if at least one field is filled
            doc_author = self.request.POST.get(f'doc_author_{doc_index}')
            doc_year = self.request.POST.get(f'doc_year_{doc_index}')
            
            if doc_name or doc_author or doc_year:
                SiteRelatedDocumentation.objects.create(
                    id_site=site,
                    name=doc_name or '',
                    author=doc_author or '',
                    year=int(doc_year) if doc_year else None
                )
            
            doc_index += 1

        # Save multiple images
        image_index = 0
        while True:
            image_type_id = self.request.POST.get(f'image_type_{image_index}')
            if image_type_id is None:
                break
            
            # Collect all image fields
            image_scale_id = self.request.POST.get(f'image_scale_{image_index}')
            file_name = self.request.POST.get(f'image_file_name_{image_index}')
            acquisition_date = self.request.POST.get(f'image_acquisition_date_{image_index}')
            desc_image = self.request.POST.get(f'image_desc_{image_index}')
            format_field = self.request.POST.get(f'image_format_{image_index}')
            projection = self.request.POST.get(f'image_projection_{image_index}')
            spatial_resolution = self.request.POST.get(f'image_spatial_resolution_{image_index}')
            author = self.request.POST.get(f'image_author_{image_index}')
            upload_type_img = self.request.POST.get(f'image_upload_type_{image_index}', 'url')
            
            # Handle image source URL or file upload
            source_url = None
            if upload_type_img == 'url':
                source_url = self.request.POST.get(f'image_source_url_{image_index}')
            else:
                # File upload - save to media folder
                image_file = self.request.FILES.get(f'image_file_{image_index}')
                if image_file:
                    # Validate file is actually an image
                    if hasattr(image_file, 'content_type') and str(image_file.content_type).startswith('image/'):
                        source_url = save_uploaded_image(image_file, subfolder='site_images')
            
            key_words = self.request.POST.get(f'image_key_words_{image_index}')
            
            # Only save if at least one field is filled
            if any([image_type_id, image_scale_id, file_name, acquisition_date, desc_image, 
                    format_field, projection, spatial_resolution, author, source_url, key_words]):
                Image.objects.create(
                    id_site=site,
                    file_name=file_name or '',
                    acquisition_date=acquisition_date if acquisition_date else None,
                    desc_image=desc_image or '',
                    id_image_scale=image_scale_id if image_scale_id else None,
                    id_image_type=image_type_id if image_type_id else None,
                    format=format_field or '',
                    projection=projection or '',
                    spatial_resolution=spatial_resolution or '',
                    author=author or '',
                    source_url=source_url or '',
                    key_words=key_words or ''
                )
            
            image_index += 1

        return response


class SiteListView(LoginRequiredMixin, ListView):
    """
    Display a list of sites, optionally filtered by research_id query parameter.
    Usage: /sites/?research_id=<id>
    """
    model = Site
    template_name = 'frontend/site_list.html'
    context_object_name = 'sites'

    def get_queryset(self):
        queryset = Site.objects.all()
        research_id = self.request.GET.get('research_id')
        if research_id:
            queryset = queryset.filter(siteresearch__id_research=research_id)
        return queryset


class SiteDetailView(DetailView):
    model = Site
    template_name = 'frontend/site_detail.html'
    context_object_name = 'site'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        site = self.object
        context['site_toponymy'] = SiteToponymy.objects.filter(id_site=site.id).first()
        context['interpretation'] = Interpretation.objects.filter(id_site=site.id).first()
        site_evidence_links = SiteArchEvidence.objects.filter(
            id_site=site
        ).select_related('id_archaeological_evidence')
        context['site_evidences'] = [link.id_archaeological_evidence for link in site_evidence_links]
        site_research_links = SiteResearch.objects.filter(id_site=site).select_related('id_research')
        context['site_researches'] = [link.id_research for link in site_research_links]
        context['site_images'] = Image.objects.filter(id_site=site)
        context['site_investigation'] = SiteInvestigation.objects.filter(id_site=site).select_related('id_investigation').first()
        site_biblios = SiteBibliography.objects.filter(id_site=site).select_related('id_bibliography')
        context['site_bibliographies'] = [sb.id_bibliography for sb in site_biblios]
        site_sources = SiteSources.objects.filter(id_site=site).select_related('id_sources')
        context['site_sources'] = [ss.id_sources for ss in site_sources]
        context['site_docs'] = SiteRelatedDocumentation.objects.filter(id_site=site)
        return context


class SiteUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Site
    form_class = SiteForm
    template_name = 'frontend/site_form.html'

    def get_success_url(self):
        research_id = self.request.GET.get('research_id')
        if research_id:
            return reverse('research-detail', args=[research_id])
        return reverse('evidence_list')  # fallback if no research_id

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        site = self.get_object()
        
        # Context data for dropdown options
        context['chronologies'] = Chronology.objects.all()
        context['source_types'] = SourcesType.objects.all()
        context['image_types'] = ImageType.objects.all()
        context['image_scales'] = ImageScale.objects.all()
        
        # Get all bibliographies for this site
        site_biblios = SiteBibliography.objects.filter(id_site=site).select_related('id_bibliography')
        bibliographies = [sb.id_bibliography for sb in site_biblios]
        context['existing_bibliographies'] = bibliographies
        
        # Get all sources for this site
        site_sources = SiteSources.objects.filter(id_site=site).select_related('id_sources')
        sources = [ss.id_sources for ss in site_sources]
        context['existing_sources'] = sources
        
        # Get all related documentations for this site
        docs = SiteRelatedDocumentation.objects.filter(id_site=site)
        context['existing_docs'] = docs
        
        # Get all images for this site
        images = Image.objects.filter(id_site=site)
        context['existing_images'] = images
        
        return context

    def get_initial(self):
        initial = super().get_initial()
        site = self.get_object()

        # Site model fields
        initial['site_name'] = site.site_name
        initial['site_environment_relationship'] = site.site_environment_relationship
        initial['additional_topography'] = site.additional_topography
        initial['elevation'] = site.elevation
        initial['id_country'] = site.id_country
        initial['id_region'] = site.id_region
        initial['id_province'] = site.id_province
        initial['id_municipality'] = site.id_municipality
        initial['id_physiography'] = site.id_physiography
        initial['id_base_map'] = site.id_base_map
        initial['id_positioning_mode'] = site.id_positioning_mode
        initial['id_positional_accuracy'] = site.id_positional_accuracy
        initial['id_first_discovery_method'] = site.id_first_discovery_method
        initial['locality_name'] = site.locality_name
        initial['lat'] = site.lat
        initial['lon'] = site.lon
        initial['geometry'] = site.geometry
        initial['description'] = site.description
        initial['notes'] = site.notes

        # SiteToponymy
        try:
            toponymy = SiteToponymy.objects.get(id_site=site.id)
            initial['ancient_place_name'] = toponymy.ancient_place_name
            initial['contemporary_place_name'] = toponymy.contemporary_place_name
        except SiteToponymy.DoesNotExist:
            pass

        # Interpretation
        try:
            interp = Interpretation.objects.get(id_site=site.id)
            initial['functional_class'] = interp.id_functional_class
            initial['typology'] = interp.id_typology
            initial['typology_detail'] = interp.id_typology_detail
            initial['chronology'] = interp.id_chronology
            initial['chronology_certainty_level'] = interp.chronology_certainty_level
        except Interpretation.DoesNotExist:
            pass

        # Investigation
        site_investigation = SiteInvestigation.objects.filter(id_site=site.id).first()
        if site_investigation and site_investigation.id_investigation:
            investigation = site_investigation.id_investigation
            initial['project_name'] = investigation.project_name
            initial['periodo'] = investigation.period
            initial['investigation_type'] = investigation.id_investigation_type

        # SiteBibliography - get first if multiple exist
        site_biblio = SiteBibliography.objects.select_related('id_bibliography').filter(id_site=site.id).first()
        if site_biblio:
            biblio = site_biblio.id_bibliography  # Access the related Bibliography
            initial['title'] = biblio.title
            initial['author'] = biblio.author
            initial['year'] = biblio.year
            initial['doi'] = biblio.doi
            initial['tipo'] = biblio.tipo

        # SiteSources - get first if multiple exist
        site_sources = SiteSources.objects.select_related('id_sources').filter(id_site=site.id).first()
        if site_sources:
            source = site_sources.id_sources
            initial['name'] = source.name
            initial['documentation_chronology'] = source.id_chronology
            initial['source_type'] = source.id_sources_typology

        # SiteRelatedDocumentation - get first if multiple exist
        site_doc = SiteRelatedDocumentation.objects.filter(id_site=site.id).first()
        if site_doc:
            initial['documentation_name'] = site_doc.name
            initial['documentation_author'] = site_doc.author
            initial['documentation_year'] = site_doc.year

        # Image - get first if multiple exist
        image = Image.objects.filter(id_site=site.id).first()
        if image:
            initial['image_type'] = image.id_image_type
            initial['image_scale'] = image.id_image_scale

        return initial

    def form_valid(self, form):
        lat = form.cleaned_data.get('lat')
        lon = form.cleaned_data.get('lon')
        if lat and lon:
            form.instance.geometry = (float(lon), float(lat))

        response = super().form_valid(form)
        site = self.object

        # Update SiteToponymy
        SiteToponymy.objects.update_or_create(
            id_site=site,
            defaults={
                'ancient_place_name': form.cleaned_data.get('ancient_place_name'),
                'contemporary_place_name': form.cleaned_data.get('contemporary_place_name')
            }
        )

        # Update Interpretation
        if form.cleaned_data.get('functional_class'):
            Interpretation.objects.update_or_create(
                id_site=site,
                defaults={
                    'id_functional_class': form.cleaned_data.get('functional_class'),
                    'id_typology': form.cleaned_data.get('typology'),
                    'id_typology_detail': form.cleaned_data.get('typology_detail'),
                    'id_chronology': form.cleaned_data.get('chronology'),
                    'chronology_certainty_level': form.cleaned_data.get('chronology_certainty_level') or 1
                }
            )
        # Update SiteResearch relationship
        research_id = self.request.GET.get('research_id')
        if research_id:
            try:
                research = Research.objects.get(pk=research_id)
                SiteResearch.objects.update_or_create(
                    id_site=site,
                    id_research=research
                )
            except Research.DoesNotExist:
                pass

        # Update Investigation
        project_name = form.cleaned_data.get('project_name')
        periodo = form.cleaned_data.get('periodo')
        investigation_type = form.cleaned_data.get('investigation_type')

        # Delete all old investigations for this site first
        SiteInvestigation.objects.filter(id_site=site).delete()

        if project_name and periodo and investigation_type:
            investigation, created = Investigation.objects.update_or_create(
                project_name = project_name,
                defaults={
                    'period': periodo,
                    'id_investigation_type': investigation_type
                }
            )
            # Associate the investigation with the site
            SiteInvestigation.objects.create(
                id_site=site,
                id_investigation=investigation
            )

        # Update site bibliographies - remove all old ones and create new ones
        # First, delete existing bibliographies for this site
        SiteBibliography.objects.filter(id_site=site).delete()
        
        # Now save all bibliographies from the form
        biblio_index = 0
        while True:
            title = self.request.POST.get(f'biblio_title_{biblio_index}')
            author = self.request.POST.get(f'biblio_author_{biblio_index}')
            year = self.request.POST.get(f'biblio_year_{biblio_index}')
            doi = self.request.POST.get(f'biblio_doi_{biblio_index}')
            tipo = self.request.POST.get(f'biblio_tipo_{biblio_index}')
            
            # Break if no more bibliography entries
            if title is None:
                break
            
            # Only save if at least one field is filled
            if title or author or year or doi or tipo:
                bibliography = Bibliography.objects.create(
                    title=title or '',
                    author=author or '',
                    year=int(year) if year else None,
                    doi=doi or '',
                    tipo=tipo or ''
                )
                SiteBibliography.objects.create(
                    id_site=site,
                    id_bibliography=bibliography
                )
            
            biblio_index += 1

        # Update site sources - remove all old ones and create new ones
        # First, delete existing sources for this site
        SiteSources.objects.filter(id_site=site).delete()
        
        # Now save all sources from the form
        source_index = 0
        while True:
            source_name = self.request.POST.get(f'source_name_{source_index}')
            if source_name is None:
                break
            
            # Collect all source fields
            chronology_id = self.request.POST.get(f'source_chronology_{source_index}')
            source_type_id = self.request.POST.get(f'source_type_{source_index}')

            if source_name or chronology_id or source_type_id:
                source = Sources.objects.create(
                    name=source_name or '',
                    id_chronology_id=chronology_id if chronology_id else None,
                    id_sources_typology_id=source_type_id if source_type_id else None
                )
                SiteSources.objects.create(
                    id_site=site,
                    id_sources=source
                )
            
            source_index += 1

        # Update site related documentation - remove all old ones and create new ones
        # First, delete existing docs for this site
        SiteRelatedDocumentation.objects.filter(id_site=site).delete()
        
        # Now save all docs from the form
        doc_index = 0
        while True:
            doc_name = self.request.POST.get(f'doc_name_{doc_index}')
            if doc_name is None:
                break
            
            # Only save if at least one field is filled
            doc_author = self.request.POST.get(f'doc_author_{doc_index}')
            doc_year = self.request.POST.get(f'doc_year_{doc_index}')
            
            if doc_name or doc_author or doc_year:
                SiteRelatedDocumentation.objects.create(
                    id_site=site,
                    name=doc_name or '',
                    author=doc_author or '',
                    year=int(doc_year) if doc_year else None
                )
            
            doc_index += 1

        # Update site related images - remove all old ones and create new ones
        # First, delete existing images for this site
        Image.objects.filter(id_site=site).delete()
        
        # Now save all images from the form
        image_index = 0
        while True:
            image_type_id = self.request.POST.get(f'image_type_{image_index}')
            if image_type_id is None:
                break
            
            # Collect all image fields
            image_scale_id = self.request.POST.get(f'image_scale_{image_index}')
            file_name = self.request.POST.get(f'image_file_name_{image_index}')
            acquisition_date = self.request.POST.get(f'image_acquisition_date_{image_index}')
            desc_image = self.request.POST.get(f'image_desc_{image_index}')
            format_field = self.request.POST.get(f'image_format_{image_index}')
            projection = self.request.POST.get(f'image_projection_{image_index}')
            spatial_resolution = self.request.POST.get(f'image_spatial_resolution_{image_index}')
            author = self.request.POST.get(f'image_author_{image_index}')
            upload_type_img = self.request.POST.get(f'image_upload_type_{image_index}', 'url')
            
            # Handle image source URL or file upload
            source_url = None
            if upload_type_img == 'url':
                source_url = self.request.POST.get(f'image_source_url_{image_index}')
            else:
                # File upload - save to media folder
                image_file = self.request.FILES.get(f'image_file_{image_index}')
                if image_file:
                    # Validate file is actually an image
                    if hasattr(image_file, 'content_type') and str(image_file.content_type).startswith('image/'):
                        source_url = save_uploaded_image(image_file, subfolder='site_images')
            
            key_words = self.request.POST.get(f'image_key_words_{image_index}')
            
            # Only save if at least one field is filled
            if any([image_type_id, image_scale_id, file_name, acquisition_date, desc_image, 
                    format_field, projection, spatial_resolution, author, source_url, key_words]):
                Image.objects.create(
                    id_site=site,
                    file_name=file_name or '',
                    acquisition_date=acquisition_date if acquisition_date else None,
                    desc_image=desc_image or '',
                    id_image_scale=image_scale_id if image_scale_id else None,
                    id_image_type=image_type_id if image_type_id else None,
                    format=format_field or '',
                    projection=projection or '',
                    spatial_resolution=spatial_resolution or '',
                    author=author or '',
                    source_url=source_url or '',
                    key_words=key_words or ''
                )
            
            image_index += 1

        return response

    def test_func(self):
        """
        Allow admin to update any site, or user to update sites linked to their research.
        If no research is linked, allow admin or authenticated users.
        """
        site = self.get_object()
        # Admins can update any site
        if self.request.user.is_staff:
            return True
        # Check if user owns the research associated with this site
        site_research = SiteResearch.objects.filter(id_site=site).first()
        if site_research and site_research.id_research:
            return self.request.user == site_research.id_research.submitted_by
        # If no research linked, allow authenticated users
        return self.request.user.is_authenticated


class SiteDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Site
    template_name = 'frontend/site_confirm_delete.html'

    def test_func(self):
        """
        Allow admin to delete any site, or user to delete sites linked to their research.
        If no research is linked, allow admin or authenticated users.
        """
        site = self.get_object()
        # Admins can delete any site
        if self.request.user.is_staff:
            return True
        # Check if user owns the research associated with this site
        site_research = SiteResearch.objects.filter(id_site=site).first()
        if site_research and site_research.id_research:
            return self.request.user == site_research.id_research.submitted_by
        # If no research linked, allow authenticated users
        return self.request.user.is_authenticated

    def get_success_url(self):
        # Get the research ID through the SiteResearch relationship
        site = self.object
        site_research = site.siteresearch_set.first()
        if site_research:
            return reverse('research-detail', args=[site_research.id_research.id])
        return reverse('site_list')  # fallback if no research is linked


class EvidenceCreateView(LoginRequiredMixin, CreateView):
    model = ArchaeologicalEvidence
    form_class = ArchaeologicalEvidenceForm
    template_name = 'frontend/evidence_form.html'

    def get_success_url(self):
        research_id = self.request.GET.get('research_id')
        if research_id:
            return reverse('research-detail', args=[research_id])
        return reverse('evidence_list')  # fallback if no research_id

    def form_valid(self, form):
        response = super().form_valid(form)
        arch_ev = self.object

        # Save relation with Research or Site
        research_id = self.request.GET.get('research_id')
        site_id = self.request.GET.get('site_id')

        if research_id:
            try:
                research = Research.objects.get(pk=research_id)
                ArchEvResearch.objects.update_or_create(
                    id_archaeological_evidence=arch_ev,
                    defaults={'id_research': research.id}
                )
            except Research.DoesNotExist:
                pass

        if site_id:
            try:
                site = Site.objects.get(pk=site_id)
                SiteArchEvidence.objects.update_or_create(
                    id_site=site,
                    id_archaeological_evidence=arch_ev
                )
            except Site.DoesNotExist:
                pass

        # Save multiple bibliographies
        # Collect all bibliography fields from POST data
        biblio_index = 0
        while True:
            title = self.request.POST.get(f'ev_biblio_title_{biblio_index}')
            author = self.request.POST.get(f'ev_biblio_author_{biblio_index}')
            year = self.request.POST.get(f'ev_biblio_year_{biblio_index}')
            doi = self.request.POST.get(f'ev_biblio_doi_{biblio_index}')
            tipo = self.request.POST.get(f'ev_biblio_tipo_{biblio_index}')
            
            # Break if no more bibliography entries
            if title is None:
                break
            
            # Only save if at least one field is filled
            if title or author or year or doi or tipo:
                bibliography = Bibliography.objects.create(
                    title=title or '',
                    author=author or '',
                    year=int(year) if year else None,
                    doi=doi or '',
                    tipo=tipo or ''
                )
                ArchEvBiblio.objects.create(
                    id_archaeological_evidence=arch_ev,
                    id_bibliography=bibliography
                )
            
            biblio_index += 1

        # Save sources - using multi-entry pattern from form
        ev_source_index = 0
        while True:
            source_name = self.request.POST.get(f'ev_source_name_{ev_source_index}')
            if source_name is None:
                break
            id_chronology = self.request.POST.get(f'ev_source_chronology_{ev_source_index}')
            id_source_type = self.request.POST.get(f'ev_source_type_{ev_source_index}')
            if source_name or id_chronology or id_source_type:
                source = Sources.objects.create(
                    name=source_name or '',
                    id_chronology_id=id_chronology if id_chronology else None,
                    id_sources_typology_id=id_source_type if id_source_type else None
                )
                ArchEvSources.objects.create(
                    id_archaeological_evidence=arch_ev,
                    id_sources=source
                )
            ev_source_index += 1

        # Save multiple Related Docs - using multi-entry pattern
        ev_doc_index = 0
        while True:
            doc_name = self.request.POST.get(f'ev_doc_name_{ev_doc_index}')
            if doc_name is None:
                break
            doc_author = self.request.POST.get(f'ev_doc_author_{ev_doc_index}')
            doc_year = self.request.POST.get(f'ev_doc_year_{ev_doc_index}')
            if doc_name or doc_author or doc_year:
                ArchEvRelatedDoc.objects.create(
                    id_archaeological_evidence=arch_ev,
                    name=doc_name or '',
                    author=doc_author or '',
                    year=int(doc_year) if doc_year else None
                )
            ev_doc_index += 1

        # Save multiple Images - using multi-entry pattern
        from .models import Image
        ev_image_index = 0
        while True:
            file_name = self.request.POST.get(f'ev_image_file_name_{ev_image_index}')
            if file_name is None:
                break
            
            # Get all image fields
            image_type_id = self.request.POST.get(f'ev_image_type_{ev_image_index}')
            image_scale_id = self.request.POST.get(f'ev_image_scale_{ev_image_index}')
            acquisition_date = self.request.POST.get(f'ev_image_acquisition_date_{ev_image_index}')
            desc_image = self.request.POST.get(f'ev_image_desc_{ev_image_index}')
            format_val = self.request.POST.get(f'ev_image_format_{ev_image_index}')
            projection = self.request.POST.get(f'ev_image_projection_{ev_image_index}')
            spatial_resolution = self.request.POST.get(f'ev_image_spatial_resolution_{ev_image_index}')
            author = self.request.POST.get(f'ev_image_author_{ev_image_index}')
            key_words = self.request.POST.get(f'ev_image_key_words_{ev_image_index}')
            upload_type = self.request.POST.get(f'ev_image_upload_type_{ev_image_index}', 'url')
            
            # Handle URL or file upload
            source_url = None
            if upload_type == 'url':
                source_url = self.request.POST.get(f'ev_image_source_url_{ev_image_index}')
            else:
                # Handle file upload - save to media folder
                file_key = f'ev_image_file_{ev_image_index}'
                if file_key in self.request.FILES:
                    uploaded_file = self.request.FILES[file_key]
                    # Validate file type and save
                    if hasattr(uploaded_file, 'content_type') and str(uploaded_file.content_type).startswith('image/'):
                        source_url = save_uploaded_image(uploaded_file, subfolder='evidence_images')
            
            # Only save if at least one significant field is filled
            if file_name or image_type_id or desc_image or source_url:
                Image.objects.create(
                    id_archaeological_evidence=arch_ev,
                    file_name=file_name or '',
                    id_image_type=image_type_id if image_type_id else None,
                    id_image_scale=image_scale_id if image_scale_id else None,
                    acquisition_date=acquisition_date if acquisition_date else None,
                    desc_image=desc_image or '',
                    format=format_val or '',
                    projection=projection or '',
                    spatial_resolution=spatial_resolution or '',
                    author=author or '',
                    source_url=source_url or '',
                    key_words=key_words or ''
                )
            
            ev_image_index += 1

        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Options for dropdowns
        context['chronologies'] = Chronology.objects.all()
        context['source_types'] = SourcesType.objects.all()
        context['image_types'] = ImageType.objects.all()
        context['image_scales'] = ImageScale.objects.all()
        return context


class EvidenceListView(LoginRequiredMixin, ListView):
    model = ArchaeologicalEvidence
    template_name = 'frontend/evidence_list.html'
    context_object_name = 'evidences'

    def get_queryset(self):
        queryset = ArchaeologicalEvidence.objects.all()
        research_id = self.request.GET.get('research_id')
        if research_id:
            queryset = queryset.filter(archaeologicalevidenceresearch__id_research=research_id)
        return queryset

class EvidenceDetailView(DetailView):
    model = ArchaeologicalEvidence
    template_name = 'frontend/evidence_detail.html'
    context_object_name = 'evidence'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        evidence = self.object
        context['arch_ev_biblio'] = ArchEvBiblio.objects.filter(id_archaeological_evidence=evidence.id).first()
        context['arch_ev_sources'] = ArchEvSources.objects.filter(id_archaeological_evidence=evidence.id).first()
        context['arch_ev_related_doc'] = ArchEvRelatedDoc.objects.filter(id_archaeological_evidence=evidence.id).first()
        site_links = SiteArchEvidence.objects.filter(
            id_archaeological_evidence=evidence
        ).select_related('id_site')
        context['sites'] = [link.id_site for link in site_links]
        direct_research_ids = ArchEvResearch.objects.filter(
            id_archaeological_evidence=evidence
        ).values_list('id_research', flat=True)
        research_ids = set(direct_research_ids)
        if site_links:
            site_ids = [link.id_site_id for link in site_links]
            via_sites = SiteResearch.objects.filter(id_site_id__in=site_ids).values_list('id_research_id', flat=True)
            research_ids.update(via_sites)
        context['researches'] = Research.objects.filter(id__in=research_ids) if research_ids else []
        context['evidence_images'] = Image.objects.filter(id_archaeological_evidence=evidence)
        return context

class EvidenceUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = ArchaeologicalEvidence
    form_class = ArchaeologicalEvidenceForm
    template_name = 'frontend/evidence_form.html'

    def get_success_url(self):
        research_id = self.request.GET.get('research_id')
        if research_id:
            return reverse('research-detail', args=[research_id])
        return reverse('evidence_list')  # fallback if no research_id

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        evidence = self.get_object()
        # Get all bibliographies for this evidence
        arch_ev_biblios = ArchEvBiblio.objects.filter(id_archaeological_evidence=evidence).select_related('id_bibliography')
        bibliographies = [ab.id_bibliography for ab in arch_ev_biblios]
        context['existing_bibliographies'] = bibliographies
        # Get existing sources
        ev_sources = ArchEvSources.objects.filter(id_archaeological_evidence=evidence).select_related('id_sources')
        context['existing_sources'] = [ev.id_sources for ev in ev_sources]
        # Get existing docs
        ev_docs = ArchEvRelatedDoc.objects.filter(id_archaeological_evidence=evidence)
        context['existing_docs'] = list(ev_docs)
        # Get existing images
        from .models import Image
        existing_images = Image.objects.filter(id_archaeological_evidence=evidence)
        context['existing_images'] = list(existing_images)
        # Options for dropdowns
        context['chronologies'] = Chronology.objects.all()
        context['source_types'] = SourcesType.objects.all()
        context['image_types'] = ImageType.objects.all()
        context['image_scales'] = ImageScale.objects.all()
        return context

    def get_initial(self):
        initial = super().get_initial()
        evidence = self.get_object()

        # Model fields
        initial['evidence_name'] = evidence.evidence_name
        initial['description'] = evidence.description
        initial['id_country'] = evidence.id_country
        initial['id_region'] = evidence.id_region
        initial['id_province'] = evidence.id_province
        initial['id_municipality'] = evidence.id_municipality
        initial['archaeological_evidence_typology'] = evidence.id_archaeological_evidence_typology
        initial['chronology'] = evidence.id_chronology
        initial['positioning_mode'] = evidence.id_positioning_mode
        initial['positional_accuracy'] = evidence.id_positional_accuracy
        initial['physiography'] = evidence.id_physiography
        initial['first_discovery_method'] = evidence.id_first_discovery_method
        initial['notes'] = evidence.notes

        # Investigation fields
        if evidence.id_investigation:
            initial['project_name'] = evidence.id_investigation.project_name
            initial['periodo'] = evidence.id_investigation.period
            initial['investigation_type'] = evidence.id_investigation.id_investigation_type

        # Related bibliography
        biblio = getattr(evidence.archevbiblio_set.first(), 'id_bibliography', None)
        if biblio:
            initial['title'] = biblio.title
            initial['author'] = biblio.author
            initial['year'] = biblio.year
            initial['doi'] = biblio.doi
            initial['type'] = biblio.tipo

        # Sources
        source = getattr(evidence.archevsources_set.first(), 'id_sources', None)
        if source:
            initial['name'] = source.name
            initial['documentation_chronology'] = source.id_chronology
            initial['source_type'] = source.id_sources_typology

        # Related doc
        related_doc = evidence.archevrelateddoc_set.first()
        if related_doc:
            initial['documentation_name'] = related_doc.name
            initial['documentation_author'] = related_doc.author
            initial['documentation_year'] = related_doc.year

        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        arch_ev = self.object

        # Save/update Investigation
        project_name = form.cleaned_data.get('project_name')
        periodo = form.cleaned_data.get('periodo')
        investigation_type = form.cleaned_data.get('investigation_type')
        if project_name and periodo and investigation_type:
            investigation, _ = Investigation.objects.update_or_create(
                project_name=project_name,
                defaults={
                    'period': periodo,
                    'id_investigation_type': investigation_type
                }
            )
            arch_ev.id_investigation = investigation
            arch_ev.save()

        # Save/update Multiple Bibliographies - remove all old ones and create new ones
        # First, delete existing bibliographies for this evidence
        ArchEvBiblio.objects.filter(id_archaeological_evidence=arch_ev).delete()
        
        # Now save all bibliographies from the form
        biblio_index = 0
        while True:
            title = self.request.POST.get(f'ev_biblio_title_{biblio_index}')
            author = self.request.POST.get(f'ev_biblio_author_{biblio_index}')
            year = self.request.POST.get(f'ev_biblio_year_{biblio_index}')
            doi = self.request.POST.get(f'ev_biblio_doi_{biblio_index}')
            tipo = self.request.POST.get(f'ev_biblio_tipo_{biblio_index}')
            
            # Break if no more bibliography entries
            if title is None:
                break
            
            # Only save if at least one field is filled
            if title or author or year or doi or tipo:
                bibliography = Bibliography.objects.create(
                    title=title or '',
                    author=author or '',
                    year=int(year) if year else None,
                    doi=doi or '',
                    tipo=tipo or ''
                )
                ArchEvBiblio.objects.create(
                    id_archaeological_evidence=arch_ev,
                    id_bibliography=bibliography
                )
            
            biblio_index += 1

        # Save/update Multiple Sources - remove all old and create new ones
        ArchEvSources.objects.filter(id_archaeological_evidence=arch_ev).delete()
        ev_source_index = 0
        while True:
            source_name = self.request.POST.get(f'ev_source_name_{ev_source_index}')
            if source_name is None:
                break
            id_chronology = self.request.POST.get(f'ev_source_chronology_{ev_source_index}')
            id_source_type = self.request.POST.get(f'ev_source_type_{ev_source_index}')
            if source_name or id_chronology or id_source_type:
                source = Sources.objects.create(
                    name=source_name or '',
                    id_chronology_id=id_chronology if id_chronology else None,
                    id_sources_typology_id=id_source_type if id_source_type else None
                )
                ArchEvSources.objects.create(
                    id_archaeological_evidence=arch_ev,
                    id_sources=source
                )
            ev_source_index += 1

        # Save/update Multiple Related Docs - remove all old and create new ones
        ArchEvRelatedDoc.objects.filter(id_archaeological_evidence=arch_ev).delete()
        ev_doc_index = 0
        while True:
            doc_name = self.request.POST.get(f'ev_doc_name_{ev_doc_index}')
            if doc_name is None:
                break
            doc_author = self.request.POST.get(f'ev_doc_author_{ev_doc_index}')
            doc_year = self.request.POST.get(f'ev_doc_year_{ev_doc_index}')
            if doc_name or doc_author or doc_year:
                ArchEvRelatedDoc.objects.create(
                    id_archaeological_evidence=arch_ev,
                    name=doc_name or '',
                    author=doc_author or '',
                    year=int(doc_year) if doc_year else None
                )
            ev_doc_index += 1

        # Save/update Multiple Images - remove all old and create new ones
        from .models import Image
        Image.objects.filter(id_archaeological_evidence=arch_ev).delete()
        ev_image_index = 0
        while True:
            file_name = self.request.POST.get(f'ev_image_file_name_{ev_image_index}')
            if file_name is None:
                break
            
            # Get all image fields
            image_type_id = self.request.POST.get(f'ev_image_type_{ev_image_index}')
            image_scale_id = self.request.POST.get(f'ev_image_scale_{ev_image_index}')
            acquisition_date = self.request.POST.get(f'ev_image_acquisition_date_{ev_image_index}')
            desc_image = self.request.POST.get(f'ev_image_desc_{ev_image_index}')
            format_val = self.request.POST.get(f'ev_image_format_{ev_image_index}')
            projection = self.request.POST.get(f'ev_image_projection_{ev_image_index}')
            spatial_resolution = self.request.POST.get(f'ev_image_spatial_resolution_{ev_image_index}')
            author = self.request.POST.get(f'ev_image_author_{ev_image_index}')
            key_words = self.request.POST.get(f'ev_image_key_words_{ev_image_index}')
            upload_type = self.request.POST.get(f'ev_image_upload_type_{ev_image_index}', 'url')
            
            # Handle URL or file upload
            source_url = None
            if upload_type == 'url':
                source_url = self.request.POST.get(f'ev_image_source_url_{ev_image_index}')
            else:
                # Handle file upload - save to media folder
                file_key = f'ev_image_file_{ev_image_index}'
                if file_key in self.request.FILES:
                    uploaded_file = self.request.FILES[file_key]
                    # Validate file type and save
                    if hasattr(uploaded_file, 'content_type') and str(uploaded_file.content_type).startswith('image/'):
                        source_url = save_uploaded_image(uploaded_file, subfolder='evidence_images')
            
            # Only save if at least one significant field is filled
            if file_name or image_type_id or desc_image or source_url:
                Image.objects.create(
                    id_archaeological_evidence=arch_ev,
                    file_name=file_name or '',
                    id_image_type=image_type_id if image_type_id else None,
                    id_image_scale=image_scale_id if image_scale_id else None,
                    acquisition_date=acquisition_date if acquisition_date else None,
                    desc_image=desc_image or '',
                    format=format_val or '',
                    projection=projection or '',
                    spatial_resolution=spatial_resolution or '',
                    author=author or '',
                    source_url=source_url or '',
                    key_words=key_words or ''
                )
            
            ev_image_index += 1

        return response

    def test_func(self):
        """
        Allow admin to update any evidence, or user to update evidence linked to their research.
        If no research is linked, allow admin or authenticated users.
        """
        evidence = self.get_object()
        # Admins can update any evidence
        if self.request.user.is_staff:
            return True
        # Check if user owns the research associated with this evidence
        arch_ev_research = ArchEvResearch.objects.filter(id_archaeological_evidence=evidence).first()
        if arch_ev_research and arch_ev_research.id_research:
            try:
                research = Research.objects.get(pk=arch_ev_research.id_research)
                return self.request.user == research.submitted_by
            except Research.DoesNotExist:
                pass
        # If no research linked, allow authenticated users
        return self.request.user.is_authenticated

class EvidenceDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = ArchaeologicalEvidence
    template_name = 'frontend/evidence_confirm_delete.html'

    def get_success_url(self):
        """
        Try to redirect to the research detail page if evidence is linked to a research.
        Otherwise, redirect to evidence list.
        """
        evidence = self.object
        arch_ev_research = ArchEvResearch.objects.filter(id_archaeological_evidence=evidence).first()
        if arch_ev_research and arch_ev_research.id_research:
            try:
                research = Research.objects.get(pk=arch_ev_research.id_research)
                return reverse('research-detail', args=[research.id])
            except Research.DoesNotExist:
                pass
        return reverse('evidence_list')

    def test_func(self):
        """
        Allow admin to delete any evidence, or user to delete evidence linked to their research.
        If no research is linked, allow admin or authenticated users.
        """
        evidence = self.get_object()
        # Admins can delete any evidence
        if self.request.user.is_staff:
            return True
        # Check if user owns the research associated with this evidence
        arch_ev_research = ArchEvResearch.objects.filter(id_archaeological_evidence=evidence).first()
        if arch_ev_research and arch_ev_research.id_research:
            try:
                research = Research.objects.get(pk=arch_ev_research.id_research)
                return self.request.user == research.submitted_by
            except Research.DoesNotExist:
                pass
        # If no research linked, allow authenticated users
        return self.request.user.is_authenticated


from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import connection
from django.core.paginator import Paginator
from django.http import Http404


def is_staff(user):
    return user.is_authenticated and user.is_staff



@login_required
def search_users_autocomplete(request):
    """
    AJAX endpoint for autocomplete user search in research author selection.
    Searches by surname, username, or email.
    """
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    # Search users by surname, username, or email
    users = User.objects.filter(
        models.Q(last_name__icontains=query) |
        models.Q(username__icontains=query) |
        models.Q(email__icontains=query)
    ).select_related('profile')[:10]
    
    results = []
    for user in users:
        # Get user profile info if available
        affiliation = ''
        orcid = ''
        
        if hasattr(user, 'profile'):
            affiliation = getattr(user.profile, 'affiliation', '') or ''
            orcid = getattr(user.profile, 'orcid', '') or ''
        
        # Check if user has an author record
        author = Author.objects.filter(user=user).first()
        author_id = author.id if author else None
        
        if author:
            # Use author data if available
            affiliation = author.affiliation or affiliation
            orcid = author.orcid or orcid
        
        results.append({
            'user_id': user.id,
            'author_id': author_id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': f"{user.first_name} {user.last_name}",
            'affiliation': affiliation,
            'orcid': orcid,
        })
    
    return JsonResponse({'results': results})


@login_required
@user_passes_test(is_staff)
def database_browser(request):
    """
    Staff-only view to browse all database tables and their content
    Shows related data for foreign keys instead of just IDs
    """
    # Get all table names from the database
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        tables = [row[0] for row in cursor.fetchall()]
    
    # Get the selected table (from query parameter)
    selected_table = request.GET.get('table', None)
    page_number = request.GET.get('page', 1)
    
    table_data = None
    columns = None
    paginator = None
    page_obj = None
    col_names = None
    total_rows = 0
    foreign_keys_info = {}
    display_columns = {}
    related_data_cache = {}
    
    if selected_table and selected_table in tables:
        from psycopg2 import sql
        
        # Get column names and data types
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = %s
                ORDER BY ordinal_position;
            """, [selected_table])
            columns = cursor.fetchall()
        
        # Get foreign key relationships
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    kcu.column_name AS fk_column,
                    ccu.table_name AS referenced_table,
                    ccu.column_name AS referenced_column
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_name = %s
                    AND tc.table_schema = 'public';
            """, [selected_table])
            fk_relations = cursor.fetchall()
            
            # Build foreign keys info dictionary
            for fk_col, ref_table, ref_col in fk_relations:
                foreign_keys_info[fk_col] = {
                    'referenced_table': ref_table,
                    'referenced_column': ref_col
                }
        
        # For each foreign key, determine which column to display from the referenced table
        # Try common patterns: name, title, description, etc.
        display_columns = {}
        for fk_col, fk_info in foreign_keys_info.items():
            ref_table = fk_info['referenced_table']
            with connection.cursor() as cursor:
                # Try to find a display column (name, title, description, etc.)
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                    AND column_name IN ('name', 'title', 'description', 'denominazione_regione', 
                                        'denominazione_provincia', 'denominazione_comune', 
                                        'site_name', 'desc_positioning_mode', 'desc_physiography',
                                        'desc_base_map', 'desc_first_discovery_method', 'desc_investigation_type',
                                        'chronological_period', 'name_country', 'username', 'surname')
                    ORDER BY CASE column_name
                        WHEN 'name' THEN 1
                        WHEN 'title' THEN 2
                        WHEN 'site_name' THEN 3
                        WHEN 'denominazione_regione' THEN 4
                        WHEN 'denominazione_provincia' THEN 5
                        WHEN 'denominazione_comune' THEN 6
                        ELSE 10
                    END
                    LIMIT 1;
                """, [ref_table])
                result = cursor.fetchone()
                if result:
                    display_columns[fk_col] = result[0]
                else:
                    # Fallback: use the first text/varchar column
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = %s
                        AND data_type IN ('text', 'character varying', 'varchar', 'char')
                        ORDER BY ordinal_position
                        LIMIT 1;
                    """, [ref_table])
                    result = cursor.fetchone()
                    if result:
                        display_columns[fk_col] = result[0]
                    else:
                        # Last resort: use the referenced column itself
                        display_columns[fk_col] = fk_info['referenced_column']
        
        # Get row count
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(selected_table))
            )
            total_rows = cursor.fetchone()[0]
        
        # Build query with LEFT JOINs for foreign keys
        offset = (int(page_number) - 1) * 100
        
        # Start building the SELECT clause
        select_parts = [sql.SQL("{}.*").format(sql.Identifier(selected_table))]
        join_parts = []
        
        # Add JOINs for each foreign key
        for fk_col, fk_info in foreign_keys_info.items():
            ref_table = fk_info['referenced_table']
            ref_col = fk_info['referenced_column']
            display_col = display_columns.get(fk_col, ref_col)
            alias = f"fk_{fk_col}"
            display_alias = f"{fk_col}_display"
            
            # Add display column to SELECT
            select_parts.append(
                sql.SQL("{}.{} AS {}").format(
                    sql.Identifier(alias),
                    sql.Identifier(display_col),
                    sql.Identifier(display_alias)
                )
            )
            
            # Add JOIN
            join_parts.append(
                sql.SQL("LEFT JOIN {} AS {} ON {}.{} = {}.{}").format(
                    sql.Identifier(ref_table),
                    sql.Identifier(alias),
                    sql.Identifier(selected_table),
                    sql.Identifier(fk_col),
                    sql.Identifier(alias),
                    sql.Identifier(ref_col)
                )
            )
        
        # Build final query
        query = sql.SQL("SELECT {} FROM {} {} LIMIT 100 OFFSET %s").format(
            sql.SQL(", ").join(select_parts),
            sql.Identifier(selected_table),
            sql.SQL(" ").join(join_parts) if join_parts else sql.SQL("")
        )
        
        # Execute query
        with connection.cursor() as cursor:
            cursor.execute(query, [offset])
            table_data = cursor.fetchall()
            
            # Get column names for display
            col_names = [desc[0] for desc in cursor.description]
        
        # Process table data to combine foreign key IDs with their display values
        processed_data = []
        for row in table_data:
            processed_row = []
            row_dict = dict(zip(col_names, row))
            
            for col_name in col_names:
                if col_name.endswith('_display'):
                    # Skip display columns, they'll be shown with their IDs
                    continue
                
                value = row_dict.get(col_name)
                display_value = row_dict.get(f"{col_name}_display")
                
                if col_name in foreign_keys_info:
                    # This is a foreign key column
                    processed_row.append({
                        'value': value,
                        'display': display_value,  # Can be None if FK is NULL or join failed
                        'is_fk': True,
                        'fk_table': foreign_keys_info[col_name]['referenced_table']
                    })
                else:
                    # Regular column
                    processed_row.append({
                        'value': value,
                        'display': None,
                        'is_fk': False
                    })
            
            processed_data.append(processed_row)
        
        # Filter column names to exclude _display columns
        display_col_names = [col for col in col_names if not col.endswith('_display')]
        
        # Create paginator
        paginator = Paginator(range(total_rows), 100)
        page_obj = paginator.get_page(page_number)
    else:
        processed_data = None
        display_col_names = None
    
    context = {
        'tables': tables,
        'selected_table': selected_table,
        'table_data': processed_data,
        'columns': columns,
        'col_names': display_col_names,
        'page_obj': page_obj,
        'total_rows': total_rows,
        'foreign_keys_info': foreign_keys_info,
        'display_columns': display_columns,
    }
    
    return render(request, 'frontend/database_browser.html', context)


# ==================== AUDIT LOGGING VIEWS ====================

class AdminOnlyMixin(UserPassesTestMixin):
    """Mixin to restrict access to admin users only"""
    def test_func(self):
        return self.request.user.is_staff
    
    def handle_no_permission(self):
        from django.contrib.auth.decorators import login_required
        from django.shortcuts import redirect
        from django.contrib import messages
        messages.error(self.request, "You do not have permission to access this page. Admin access required.")
        return redirect('home')


class AuditLogListView(LoginRequiredMixin, AdminOnlyMixin, ListView):
    """
    Display audit logs for admin users.
    Shows all operations performed by users in the system.
    """
    paginate_by = 50
    template_name = 'frontend/audit_log_list.html'
    context_object_name = 'logs'
    
    def get_queryset(self):
        from .audit_models import AuditLog
        queryset = AuditLog.objects.all().select_related('user')
        
        # Filter by operation type
        operation = self.request.GET.get('operation')
        if operation and operation in ['CREATE', 'UPDATE', 'DELETE', 'VIEW']:
            queryset = queryset.filter(operation=operation)
        
        # Filter by model name
        model_name = self.request.GET.get('model')
        if model_name:
            queryset = queryset.filter(model_name__icontains=model_name)
        
        # Filter by username
        username = self.request.GET.get('user')
        if username:
            queryset = queryset.filter(user__username__icontains=username)
        
        # Date filter - last N days
        days = self.request.GET.get('days', '30')
        if days.isdigit():
            from datetime import timedelta
            from django.utils import timezone
            since = timezone.now() - timedelta(days=int(days))
            queryset = queryset.filter(timestamp__gte=since)
        
        return queryset.order_by('-timestamp')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .audit_models import AuditLog
        
        # Add statistics
        all_logs = AuditLog.objects.all()
        context['total_logs'] = all_logs.count()
        context['create_count'] = all_logs.filter(operation='CREATE').count()
        context['update_count'] = all_logs.filter(operation='UPDATE').count()
        context['delete_count'] = all_logs.filter(operation='DELETE').count()
        
        # Add filter values
        context['selected_operation'] = self.request.GET.get('operation', '')
        context['selected_model'] = self.request.GET.get('model', '')
        context['selected_user'] = self.request.GET.get('user', '')
        context['selected_days'] = self.request.GET.get('days', '30')
        
        # Add available models
        context['models'] = sorted(set(all_logs.values_list('model_name', flat=True)))
        context['users'] = User.objects.filter(is_active=True).order_by('username')
        
        return context


def audit_log_export(request):
    """Export audit logs as CSV for admin users"""
    from django.contrib.auth.decorators import user_passes_test
    from django.http import HttpResponse
    import csv
    from .audit_models import AuditLog
    
    # Check if user is staff
    if not request.user.is_staff:
        from django.contrib import messages
        messages.error(request, "You do not have permission to export logs.")
        return redirect('home')
    
    # Get filtered logs
    queryset = AuditLog.objects.all().select_related('user')
    
    operation = request.GET.get('operation')
    if operation and operation in ['CREATE', 'UPDATE', 'DELETE', 'VIEW']:
        queryset = queryset.filter(operation=operation)
    
    model_name = request.GET.get('model')
    if model_name:
        queryset = queryset.filter(model_name__icontains=model_name)
    
    username = request.GET.get('user')
    if username:
        queryset = queryset.filter(user__username__icontains=username)
    
    days = request.GET.get('days', '30')
    if days.isdigit():
        from datetime import timedelta
        from django.utils import timezone
        since = timezone.now() - timedelta(days=int(days))
        queryset = queryset.filter(timestamp__gte=since)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="audit_logs.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'User', 'Operation', 'Model', 'Object ID', 'Object', 'Changes', 'IP Address'])
    
    for log in queryset.order_by('-timestamp'):
        writer.writerow([
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            log.user.username if log.user else 'Anonymous',
            log.operation,
            log.model_name,
            log.object_id,
            log.object_str,
            log.get_changes_display,
            log.ip_address or 'N/A',
        ])
    
    return response

