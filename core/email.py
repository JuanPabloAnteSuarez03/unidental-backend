from djoser import email
from django.contrib.auth.tokens import default_token_generator
from djoser import utils
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site


class PasswordResetEmail(email.PasswordResetEmail):
    template_name = 'email/password_reset_email.html'
    subject_template_name = 'email/password_reset_subject.txt'
    
    def get_context_data(self):
        # Obtenemos el contexto base de Djoser que ya tiene todo configurado
        context = super().get_context_data()
        
        # Agregamos nuestras variables adicionales
        context['from_email'] = settings.DEFAULT_FROM_EMAIL
        
        return context
    
    def get_subject(self):
        # Usar directamente nuestro subject personalizado
        return "UNIDENTAL - Reinicio de Contraseña"


class PasswordResetEmailPlainText(email.BaseEmailMessage):
    template_name = 'email/password_reset_email.txt'
    
    def __init__(self, request, context):
        super().__init__(request, context)
        
    def get_context_data(self):
        context = super().get_context_data()
        user = context.get('user')
        
        context.update({
            'user': user,
            'domain': context.get('domain'),
            'protocol': context.get('protocol', 'https'),
            'url': context.get('url'),
            'from_email': settings.DEFAULT_FROM_EMAIL,
        })
        
        return context 