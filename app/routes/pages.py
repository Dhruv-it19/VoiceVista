"""Page routes for rendering HTML templates."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Add url_for to template context for Flask compatibility
def url_for(endpoint: str, **values):
    """Flask-style url_for for templates."""
    routes = {
        'static': '/static',
        'main': '/main',
        'index': '/',
        'process': '/process',
        'process_youtube': '/process_youtube',
        'get_translated_videos': '/get_translated_videos',
    }

    base_url = routes.get(endpoint, '/')

    # Handle static files
    if endpoint == 'static' and 'filename' in values:
        return f"/static/{values['filename']}"

    # Handle download with filename
    if endpoint == 'download_file' and 'filename' in values:
        return f"/download/{values['filename']}"

    return base_url

templates.env.globals['url_for'] = url_for

LANGUAGES = {
    'en': 'English',
    'hi': 'Hindi',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'gu': 'Gujarati',
    'ur': 'Urdu',
    'bn': 'Bengali',
    'ta': 'Tamil',
    'mr': 'Marathi',
    'kn': 'Kannada',
}


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Landing page."""
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )


@router.get("/main", response_class=HTMLResponse)
async def main_page(request: Request):
    """Video translation interface."""
    return templates.TemplateResponse(
        request=request,
        name="main.html",
        context={"languages": LANGUAGES}
    )
