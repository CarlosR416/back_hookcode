"""
Custom middleware components for language negotiation and response formatting.
"""

from django.utils import translation


class SmartLocaleMiddleware:
    """
    Middleware that ensures seamless bilingual resolution:
    1. Query param: ?lang=es or ?language=es
    2. Header: X-Language (e.g., 'es')
    3. Standard Accept-Language header (e.g. 'es', 'es-ES', 'es-419')
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Check query parameter
        lang = request.GET.get("lang") or request.GET.get("language")

        # 2. Check custom header
        if not lang:
            lang = request.headers.get("X-Language")

        # 3. Check Accept-Language header
        if not lang:
            accept_lang = request.headers.get("Accept-Language", "")
            if accept_lang:
                # e.g. "es-ES,es;q=0.9,en;q=0.8" -> "es"
                primary = accept_lang.split(",")[0].split(";")[0].strip()
                lang = primary.split("-")[0]

        if lang and lang.lower() in ["es", "en"]:
            selected_lang = lang.lower()
            translation.activate(selected_lang)
            request.LANGUAGE_CODE = selected_lang

        response = self.get_response(request)

        if hasattr(request, "LANGUAGE_CODE"):
            response.headers["Content-Language"] = request.LANGUAGE_CODE

        return response
