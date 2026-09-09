# apps/core/middleware.py

class DisableCachingMiddleware:
    """
    Forces no-cache headers on ALL responses, overriding any
    default Cache-Control injected upstream by the hosting
    stack (LiteSpeed/CloudLinux/Passenger default caching).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        # اگه ETag هم از یه‌جایی تزریق شده، حذفش کن
        if 'ETag' in response:
            del response['ETag']
        return response
