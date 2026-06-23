from django.test import SimpleTestCase
from django.conf import settings
import os

class GlobalAjaxFilesExistTests(SimpleTestCase):
    def test_base_includes_global_ajax_script(self):
        base_path = os.path.join(settings.BASE_DIR, 'baysoko', 'templates', 'base.html')
        self.assertTrue(os.path.exists(base_path), f"base.html not found at {base_path}")
        with open(base_path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn("{% static 'js/global-ajax-handler.js' %}", content)

    def test_static_js_exists(self):
        js_path = os.path.join(settings.BASE_DIR, 'static', 'js', 'global-ajax-handler.js')
        self.assertTrue(os.path.exists(js_path), f"global-ajax-handler.js not found at {js_path}")
