"""Template context for Django → React SPA navigation."""

from .spa_urls import spa_library_home_url


def spa_urls(request):
    return {'spa_library_url': spa_library_home_url()}
