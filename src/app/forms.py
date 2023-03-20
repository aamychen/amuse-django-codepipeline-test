from django.contrib.auth import forms, get_user_model


class PasswordResetForm(forms.PasswordResetForm):
    def get_users(self, email):
        active_users = get_user_model()._default_manager.filter(
            email__iexact=email, is_active=True
        )
        return active_users
