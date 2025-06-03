from djoser import email
from djoser import utils
from djoser.conf import settings
from django.contrib.auth.tokens import default_token_generator


class PasswordResetEmail(email.PasswordResetEmail):
    template_name = 'core/PasswordResetEmail.html'

    def get_context_data(self):
        context = super().get_context_data()
        
        user = context.get("user")
        context["uid"] = utils.encode_uid(user.pk)
        context["token"] = default_token_generator.make_token(user)
        # Cambiamos la URL para que apunte al frontend de Vercel
        context["url"] = f"password-reset/confirm/{context['uid']}/{context['token']}"
        context["frontend_url"] = f"https://unidental-frontend.vercel.app/password-reset/confirm/{context['uid']}/{context['token']}"
        
        return context 