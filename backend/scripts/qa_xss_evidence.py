"""One-off evidence dump for QA (run from backend/)."""
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client

from library.models import Book, BookTranslation

User = get_user_model()
User.objects.filter(username='xssdemo').delete()
Book.objects.filter(slug='xss-demo-book').delete()
User.objects.create_user('xssdemo', 'x@x.com', 'Str0ng-Passw0rd!')
book = Book.objects.create(
    author_name='X',
    slug='xss-demo-book',
    is_published=True,
    rights_status='licensed',
    pdf_generation_status='ready',
    audio_generation_status='ready',
)
BookTranslation.objects.create(
    book=book,
    language='uz',
    title='XSS',
    body='<script>alert(1)</script>\n\nPlain <b>bold</b> and Tom & Jerry.',
)
client = Client()
client.login(username='xssdemo', password='Str0ng-Passw0rd!')
response = client.get(f'/library/{book.slug}/read/')
html = response.content.decode()
start = html.find('id="book-source"')
region = html[start : start + 900]
print('STATUS', response.status_code)
print('--- book-source region ---')
print(region)
print('--- checks ---')
print('live script present?', '<script>alert(1)</script>' in region)
print('escaped script?', '&lt;script&gt;' in region)
print('escaped b?', '&lt;b&gt;bold&lt;/b&gt;' in region)
print('escaped amp?', 'Tom &amp; Jerry' in region)
