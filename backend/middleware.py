import json
import logging
import secrets


logger = logging.getLogger("backend.request")

SENSITIVE_KEYS = {
    "password",
    "pass",
    "pwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
}


class PostRequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST":
            payload = self._extract_payload(request)
            logger.info(
                "POST request path=%s content_type=%s payload=%s",
                request.path,
                request.content_type,
                payload,
            )

        return self.get_response(request)

    def _extract_payload(self, request):
        content_type = (request.content_type or "").lower()

        if "application/json" in content_type:
            body = request.body.decode("utf-8", errors="replace")
            if not body:
                return {}
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                return body
            return self._mask_sensitive(parsed)

        if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            data = {}
            for key in request.POST.keys():
                values = request.POST.getlist(key)
                value = values if len(values) > 1 else request.POST.get(key)
                data[key] = value
            return self._mask_sensitive(data)

        return request.body.decode("utf-8", errors="replace")

    def _mask_sensitive(self, value):
        if isinstance(value, dict):
            masked = {}
            for key, item in value.items():
                if str(key).lower() in SENSITIVE_KEYS:
                    masked[key] = "***"
                else:
                    masked[key] = self._mask_sensitive(item)
            return masked

        if isinstance(value, list):
            return [self._mask_sensitive(item) for item in value]

        return value


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)
        response = self.get_response(request)
        csp = self._build_csp_value(request)
        if csp:
            response["Content-Security-Policy"] = csp
        return response

    def _build_csp_value(self, request):
        from django.conf import settings

        policy = getattr(settings, "CONTENT_SECURITY_POLICY", None)
        if not isinstance(policy, dict) or not policy:
            return ""

        directives = []
        for key, value in policy.items():
            if isinstance(value, (list, tuple)):
                rendered_value = " ".join(str(item) for item in value if item)
            else:
                rendered_value = str(value).strip()

            rendered_value = rendered_value.replace("{nonce}", f"'nonce-{request.csp_nonce}'")

            if not key or not rendered_value:
                continue

            directives.append(f"{key} {rendered_value}")

        return "; ".join(directives)
