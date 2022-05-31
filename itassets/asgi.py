from channels.routing import ProtocolTypeRouter
import dotenv
from django.core.asgi import get_asgi_application
import os
from pathlib import Path

# These lines are required for interoperability between local and container environments.
d = Path(__file__).resolve().parents[1]
dot_env = os.path.join(str(d), '.env')
if os.path.exists(dot_env):
    dotenv.read_dotenv(dot_env)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'itassets.settings')
django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
})
