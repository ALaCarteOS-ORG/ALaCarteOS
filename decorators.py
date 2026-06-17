from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def user_in_group(group_name):
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            # Dacă userul este Admin (Superuser), are voie peste tot
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Verificăm dacă userul face parte din grupul cerut
            if request.user.groups.filter(name=group_name).exists():
                return view_func(request, *args, **kwargs)
            else:
                raise PermissionDenied  # Sau redirect('/pagina-eroare')
        return _wrapped_view
    return decorator