from django import forms
from .models import Research, Site, ArchaeologicalEvidence, FunctionalClass, Typology, TypologyDetail, Chronology, \
    InvestigationType, SourcesType, ImageType, ImageScale
from django.contrib.gis.geos import Point

class ResearchForm(forms.ModelForm):
    class Meta:
        model = Research
        fields = ['title', 'year', 'keywords', 'abstract', 'type', 'geometry']
        widgets = {

            'geometry': forms.TextInput(attrs={
                'id': 'geometry',
                'readonly': 'readonly',
                'rows': 4,
                'class': 'form-control'
            })
        }

    def clean_geometry(self):
        geometry = self.cleaned_data.get('geometry')
        if geometry and not geometry.startswith('(('):
            raise forms.ValidationError("Il campo geometria deve essere nel formato ((x,y),(x,y),...)")
        return geometry

CHRONOLOGY_CERTAINTY_CHOICES = [
    (1, 'Incerta'),
    (2, 'Probabile'),
    (3, 'Certa')
]

class SiteForm(forms.ModelForm):
    # Fields from SiteToponymy
    ancient_place_name = forms.CharField(
        max_length=255,
        required=False,
        label="Antichi")

    contemporary_place_name = forms.CharField(
        max_length=255,
        required=False,
        label="Contemporanei")

    functional_class = forms.ModelChoiceField(
        queryset=FunctionalClass.objects.all(),
        required=True,
        label="Classe Funzionale"
    )
    typology = forms.ModelChoiceField(
        queryset=Typology.objects.none(),
        required=False,
        label="Tipologia"
    )
    typology_detail = forms.ModelChoiceField(
        queryset=TypologyDetail.objects.none(),
        required=False,
        label="Sottotipologia"
    )
    chronology = forms.ModelChoiceField(
        queryset=Chronology.objects.all(),
        required=True,
        label="Cronologia"
    )

    chronology_certainty_level = forms.ChoiceField(
        choices=CHRONOLOGY_CERTAINTY_CHOICES,
        required=False,
        label="Grado di certezza della cronologia proposta",
    )

    project_name = forms.CharField(
        max_length=255,
        required=False,
        label="Nome del progetto")

    investigation_type = forms.ModelChoiceField(
        queryset=InvestigationType.objects.all(),
        required=False,
        label="Tipo di indagine")

    periodo = forms.CharField(
        max_length=255,
        required=False,
        label="Periodo")

    title = forms.CharField(
        max_length=255,
        required=False,
        label="Titolo")

    author = forms.CharField(
        max_length=255,
        required=False,
        label="Autore")

    year = forms.IntegerField(
        required=False,
        label="Anno")

    doi = forms.CharField(
        max_length=255,
        required=False,
        label="DOI")

    types = forms.CharField(
        max_length=255,
        required=False,
        label="Tipo")

    name = forms.CharField(
        max_length=255,
        required=False,
        label="Name")

    documentation_chronology = forms.ModelChoiceField(
        queryset=Chronology.objects.all(),
        required=False,
        label="Cronologia")

    source_type = forms.ModelChoiceField(
        queryset=SourcesType.objects.all(),
        required=False,
        label="Tipologia di fonte")

    documentation_name = forms.CharField(
        max_length=255,
        required=False,
        label="Nome")

    documentation_author = forms.CharField(
        max_length=255,
        required=False,
        label="Autore")

    documentation_year = forms.IntegerField(
        required=False,
        label="Anno")

    image_type = forms.ModelChoiceField(
        queryset=ImageType.objects.all(),
        required=False,
        label="Tipologia"
    )

    image_scale = forms.ModelChoiceField(
        queryset=ImageScale.objects.all(),
        required=False,
        label="Scala"
    )






    class Meta:
        model = Site
        fields = [
            'site_name', 'site_environment_relationship', 'additional_topography',
            'elevation', 'locality_name', 'lat', 'lon', 'geometry',
            'id_country', 'id_region', 'id_province', 'id_municipality',
            'id_physiography', 'id_base_map', 'id_positioning_mode',
            'id_positional_accuracy', 'id_first_discovery_method', 'description', 'notes'
        ]
        labels = {
            'site_name': 'Nome del sito',
            'site_environment_relationship': 'Raporto sito-ambiente',
            'additional_topography': 'Riferimenti topografici',
            'elevation': 'Quota',
            'locality_name': 'Locality Name',
            'lat': 'Latitude',
            'lon': 'Longitude',
            'geometry': 'Geometry',
            'id_country': 'Paese',
            'id_region': 'Regione',
            'id_province': 'Provincia',
            'id_municipality': 'Comune',
            'id_physiography': 'Fisiografia',
            'id_base_map': 'Base Cartografica',
            'id_positioning_mode': 'Modalità di Posizionamento',
            'id_positional_accuracy': 'Qualità del Posizionamento',
            'id_first_discovery_method': 'Mdalità di rinvenimento (prima scoperta)',
            'description': 'Descrizione',
            'notes': 'Note',
        }

        widgets = {
            'geometry': forms.Textarea(attrs={
                'readonly': 'readonly',
                'rows': 4,
                'class': 'form-control'
            })
        }

    def clean_geometry(self):
        geometry = self.cleaned_data.get('geometry')
        lat = self.cleaned_data.get('lat')
        lon = self.cleaned_data.get('lon')

        if geometry and geometry.strip() != '':
            return geometry  # Already a valid WKT string

        if lat is not None and lon is not None:
            return (float(lon), float(lat))  # Note: GeoDjango uses (x, y) = (lon, lat)

        return None

    def __init__(self, *args, **kwargs):
        super(SiteForm, self).__init__(*args, **kwargs)

        # Style all fields
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

        # Dynamic Typology options depending on Functional Class selected
        if 'functional_class' in self.data:
            try:
                functional_class_id = int(self.data.get('functional_class'))
                self.fields['typology'].queryset = Typology.objects.filter(id_functional_class=functional_class_id)
            except (ValueError, TypeError):
                self.fields['typology'].queryset = Typology.objects.none()

        # Dynamic TypologyDetail options depending on Typology selected
        if 'typology' in self.data:
            try:
                typology_id = int(self.data.get('typology'))
                self.fields['typology_detail'].queryset = TypologyDetail.objects.filter(id_typology=typology_id)
            except (ValueError, TypeError):
                self.fields['typology_detail'].queryset = Typology.objects.none()

class EvidenceForm(forms.ModelForm):
    class Meta:
        model = ArchaeologicalEvidence
        fields = '__all__'
