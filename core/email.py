from djoser import email
from django.contrib.auth.tokens import default_token_generator
from djoser import utils
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site


class PasswordResetEmail(email.PasswordResetEmail):
    template_name = 'email/password_reset_email.html'
    
    def get_context_data(self):
        # Obtenemos el contexto base de Djoser
        context = super().get_context_data()
        
        # Agregamos variables personalizadas
        user = context.get('user')
        context.update({
            'user': user,
            'domain': context.get('domain'),
            'protocol': context.get('protocol', 'https'),
            'url': context.get('url'),
            'from_email': settings.DEFAULT_FROM_EMAIL,
        })
        
        return context


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