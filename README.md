# SHAReLAND Project

SHAReLAND is a Django-based web platform designed for the collection, documentation, and visualization of archaeological data. It supports the collaborative management of research projects, archaeological sites, and evidences, offering a structured and multilingual interface for scientific data entry and spatial referencing.

## Features

* User authentication and profile management
* Project-based research creation with detailed metadata
* Management of archaeological sites:

  * Georeferenced using coordinates or polygon shapefiles
  * Linked to investigation data, bibliographies, and sources
* Management of archaeological evidences:

  * Descriptive, spatial, and contextual data
  * Linked to both research and sites
* Interactive 2D and 3D map visualization (Leaflet / Cesium)
* Import of shapefiles and direct drawing of geometries on map
* AJAX-based dynamic form inputs for region/province/municipality
* Multilingual interface (Italian/English)

## Technologies

* **Backend**: Django 5.2, Python 3.12, PostgreSQL with PostGIS
* **Frontend**: HTML5, Bootstrap 5, Leaflet.js, JavaScript
* **GIS Tools**: Shapefile upload, WKT geometry fields, centroid calculation

## Project Structure

```
├── django_project/
│   ├── frontend/           # Main application (models, views, forms, templates)
│   ├── users/              # User registration and profiles
│   ├── templates/          # Shared and app-specific templates
│   ├── static/             # CSS, JS, media
│   ├── media/              # Uploaded files and shapefiles
│   └── manage.py           # Django CLI
├── requirements.txt
└── README.md
```

## Setup Instructions

1. **Clone the repo**:

   ```bash
   git clone https://github.com/your-org/shareland.git
   cd shareland
   ```

2. **Create virtual environment**:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure PostgreSQL/PostGIS**:

   * Ensure a PostgreSQL database with PostGIS extension is created
   * Update `settings.py` with your DB credentials

5. **Run migrations**:

   ```bash
   python manage.py migrate
   ```

6. **Create a superuser**:

   ```bash
   python manage.py createsuperuser
   ```

7. **Run the development server**:

   ```bash
   python manage.py runserver
   ```

## Contribution Guidelines

* Fork the repository and create feature branches
* Follow Django best practices and PEP8 style
* Open pull requests for review and merge

## License

This project is released under the MIT License.

## Contact

For more information, contact the development team at: [ergin.mehmeti@logos-ri.eu](mailto:ergin.mehmti@logos-ri.eu)
