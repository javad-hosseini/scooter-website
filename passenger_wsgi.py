import os
import sys

# Support running either from ~/mahta-cycle/ or directly inside ~/mahta-cycle/scooter_website/
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SUB_PROJECT = os.path.join(CURRENT_DIR, 'scooter_website')

if os.path.isdir(SUB_PROJECT):
    PROJECT_DIR = SUB_PROJECT
else:
    PROJECT_DIR = CURRENT_DIR

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
