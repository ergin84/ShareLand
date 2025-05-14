from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.shortcuts import render, get_object_or_404
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
from .models import Research, Author, Typology, TypologyDetail, ResearchAuthor, Province, \
    Municipality, SiteResearch, Investigation, SiteBibliography, Sources, SiteSources, Image, \
    Bibliography
from django.urls import reverse_lazy, reverse
from django.contrib.staticfiles.views import serve

from .forms import ResearchForm, SiteForm, EvidenceForm, Site, ArchaeologicalEvidence


def home(request):

    return render(request, 'frontend/home.html')


def getfile(request):
    return serve(request, 'File')


class ResearchListView(ListView):
    model = Research
    template_name = 'frontend/research_list.html'  # <app>/<model>_<viewtype>.html
    context_object_name = 'researches'
    ordering = ['-year']
    paginate_by = 5

    def get_queryset(self):
        return Research.objects.all().order_by('-year')


class UserResearchListView(ListView):
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
            author = Author.objects.filter(contact_email=self.request.user.email).first()
            if author:
                updated = False
                if not author.name:
                    author.name = self.request.user.first_name
                    updated = True
                if not author.surname:
                    author.surname = self.request.user.last_name
                    updated = True
                if not author.id_anagraphic:
                    author.id_anagraphic = self.request.user.id
                    updated = True
                if updated:
                    author.save()
            else:
                author = Author.objects.create(
                    name=self.request.user.first_name,
                    surname=self.request.user.last_name,
                    contact_email=self.request.user.email,
                    affiliation='',
                    orcid='',
                    id_anagraphic=self.request.user.id
                )
        else:
            author_id = self.request.POST.get('author_id')
            if author_id:
                author = Author.objects.filter(pk=author_id).first()
            else:
                author_name = self.request.POST.get('author_name')
                author_surname = self.request.POST.get('author_surname')
                affiliation = self.request.POST.get('affiliation')
                orcid = self.request.POST.get('orcid')
                contact_email = self.request.POST.get('contact_email')

                author = Author.objects.filter(
                    name=author_name,
                    surname=author_surname,
                    contact_email=contact_email
                ).first()

                if not author:
                    author = Author.objects.create(
                        name=author_name,
                        surname=author_surname,
                        affiliation=affiliation,
                        orcid=orcid,
                        contact_email=contact_email,
                        id_anagraphic=None
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

        # === Add to ResearchAuthor table ===
        ResearchAuthor.objects.create(id_research=self.object, id_author=author)

        # === Handle co-authors ===
        index = 0
        while True:
            co_id = self.request.POST.get(f'coauthor_id_{index}')
            if co_id:
                co = Author.objects.filter(pk=co_id).first()
                if co:
                    ResearchAuthor.objects.get_or_create(id_research=self.object, id_author=co)
            else:
                name = self.request.POST.get(f'coauthor_name_{index}')
                surname = self.request.POST.get(f'coauthor_surname_{index}')
                email = self.request.POST.get(f'coauthor_email_{index}')

                if name and surname and email:
                    co = Author.objects.filter(name=name, surname=surname, contact_email=email).first()
                    if not co:
                        co = Author.objects.create(
                            name=name,
                            surname=surname,
                            contact_email=email,
                            affiliation=self.request.POST.get(f'coauthor_affiliation_{index}', ''),
                            orcid=self.request.POST.get(f'coauthor_orcid_{index}', '')
                        )
                    ResearchAuthor.objects.get_or_create(id_research=self.object, id_author=co)
                else:
                    break
            index += 1

        return render(self.request, 'frontend/research_success.html', {'research': self.object})


class ResearchDetailView(DetailView):
    model = Research
    template_name = 'frontend/research_detail.html'


from .forms import ResearchForm  # assicurati che sia importato


class ResearchUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Research
    form_class = ResearchForm
    template_name = 'frontend/research_form.html'

    def get_success_url(self):
        return reverse_lazy('user-researches', kwargs={'username': self.request.user.username})

    def form_valid(self, form):
        form.instance.submitted_by = self.request.user
        return super().form_valid(form)

    def test_func(self):
        research = self.get_object()
        return self.request.user == research.submitted_by


class ResearchDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Research
    success_url = '/'
    template_name = 'frontend/research_confirm_delete.html'

    def test_func(self):
        research = self.get_object()
        if self.request.user == research.submitted_by:
            return True
        return False



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
    query = request.GET.get('q', '')
    results = []
    if query:
        authors = Author.objects.filter(surname__icontains=query)[:10]
        results = [
            {
                'id': author.id,
                'name': author.name,
                'surname': author.surname,
                'email': author.contact_email,
                'affiliation': author.affiliation,
                'orcid': author.orcid
            }
            for author in authors
        ]
    return JsonResponse(results, safe=False)

class SiteCreateView(LoginRequiredMixin, CreateView):
    model = Site
    form_class = SiteForm
    template_name = 'frontend/site_form.html'
    success_url = reverse_lazy('site_list')

    def form_valid(self, form):
        # Optional: build geometry from lat/lon
        lat = form.cleaned_data.get('lat')
        lon = form.cleaned_data.get('lon')
        if lat and lon:
            form.instance.geometry = (float(lon), float(lat))

        response = super().form_valid(form)  # Save the Site instance
        site = self.object  # Now it's guaranteed to be saved

        # Save SiteToponymy
        ancient_name = form.cleaned_data.get('ancient_place_name')
        contemporary_name = form.cleaned_data.get('contemporary_place_name')

        if ancient_name or contemporary_name:
            SiteToponymy.objects.create(
                id_site=site.id,
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
            Investigation.objects.create(
                id_site=site.id,
                project_name=project_name,
                period=periodo,
                id_investigation_type=investigation_type
            )

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


class SiteDetailView(LoginRequiredMixin, DetailView):
    model = Site
    template_name = 'frontend/site_detail.html'
    context_object_name = 'site'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        site = self.object
        context['site_toponymy'] = SiteToponymy.objects.filter(id_site=site.id).first()
        context['interpretation'] = Interpretation.objects.filter(id_site=site.id).first()
        return context


class SiteUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Site
    form_class = SiteForm
    template_name = 'frontend/site_form.html'
    success_url = reverse_lazy('site_list')

    def get_initial(self):
        initial = super().get_initial()
        site = self.get_object()

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
        try:
            investigation = Investigation.objects.get(id_site=site.id)
            initial['project_name'] = investigation.project_name
            initial['periodo'] = investigation.period
            initial['investigation_type'] = investigation.id_investigation_type
        except Investigation.DoesNotExist:
            pass

        return initial


    def form_valid(self, form):
        lat = form.cleaned_data.get('lat')
        lon = form.cleaned_data.get('lon')
        if lat and lon:
            form.instance.geometry = (float(lon), float(lat))

        response = super().form_valid(form)
        site = self.object

        SiteToponymy.objects.update_or_create(
            id_site=site.id,
            defaults={
                'ancient_place_name': form.cleaned_data.get('ancient_place_name'),
                'contemporary_place_name': form.cleaned_data.get('contemporary_place_name')
            }
        )

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

        # Save Investigation
        project_name = form.cleaned_data.get('project_name')
        periodo = form.cleaned_data.get('periodo')
        investigation_type = form.cleaned_data.get('investigation_type')

        if project_name and periodo and investigation_type:
            Investigation.objects.update_or_create(
                id_site=site.id,
                defaults={
                    'project_name': project_name,
                    'period': periodo,
                    'id_investigation_type': investigation_type
                }
            )

        # Save site bibliography
        title = form.cleaned_data.get('title')
        author= form.cleaned_data.get('author')
        year = form.cleaned_data.get('year')
        doi = form.cleaned_data.get('doi')
        type = form.cleaned_data.get('type')

        if title or author or year or doi or type:
            bibliography, created=Bibliography.objects.update_or_create(
                defaults={
                    'title': title,
                    'author': author,
                    'year': year,
                    'doi': doi,
                    'type': type
                }
            )
            # Associate the bibliography with the site
            SiteBibliography.objects.update_or_create(
                id_site=site.id,
                id_bibliography=bibliography.id
            )

        # Save site sources and relate to a site
        name = form.cleaned_data.get('name')
        id_chronology = form.cleaned_data.get('documentation_chronology')
        id_source_type = form.cleaned_data.get('source_type')

        if name or id_chronology or id_source_type:
            source, created=Sources.objects.update_or_create(
                name=name,
                defaults={
                    'id_chronology': id_chronology.id,
                    'id_sources_typology': id_source_type.id
                }
            )
            # Associate the source with the site
            SiteSources.objects.update_or_create(
                id_site=site.id,
                id_sources=source.id
            )

        # Save site related documentation
        name = form.cleaned_data.get('name')
        author = form.cleaned_data.get('author')
        year = form.cleaned_data.get('year')

        if name or author or year:
            SiteBibliography.objects.update_or_create(
                id_site=site.id,
                defaults={
                    'name': name,
                    'author': author,
                    'year': year
                }
            )

        # Save site related images
        image_type = form.cleaned_data.get('image_type')
        image_scale = form.cleaned_data.get('image_scale')

        if image_type or image_scale:
            Image.objects.update_or_create(
                id_site=site.id,
                defaults={
                    'id_image_type': image_type.id,
                    'id_image_scale': image_scale.id
                }
            )

        return response



    def test_func(self):
        return True


class SiteDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Site
    template_name = 'frontend/site_confirm_delete.html'

    def test_func(self):
        return True

    def get_success_url(self):
        # Get the research ID through the SiteResearch relationship
        site = self.object
        site_research = site.siteresearch_set.first()
        if site_research:
            return reverse('research-detail', args=[site_research.id_research.id])
        return reverse('site_list')  # fallback if no research is linked



class EvidenceCreateView(LoginRequiredMixin, CreateView):
    model = ArchaeologicalEvidence
    form_class = EvidenceForm
    template_name = 'frontend/evidence_form.html'
    success_url = reverse_lazy('evidence_list')  # oppure ritorna alla ricerca