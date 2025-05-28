import sys
import os

# Set up Django environment
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'household_project'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "household_project.settings")

from django.core.wsgi import get_wsgi_application
from vercel_wsgi import handle_request

application = get_wsgi_application()

def handler(request, context):
    return handle_request(application, request, context)
