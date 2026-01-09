from django import forms
from .models import Paciente, Usuario


class PacienteForm(forms.ModelForm):
    class Meta:
        model = Paciente
        fields = '__all__'

    def clean_cpf(self):
        cpf = self.cleaned_data['cpf']
        return cpf.replace('.', '').replace('-', '')

class UsuarioForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(),
        required=False,
        label="Nova Senha (deixe em branco para manter)"
    )

    class Meta:
        model = Usuario
        fields = [
            'first_name',
            'last_name',
            'email',
            'mudar_senha',           # <--- RESTAURADO
            'drt',                   # <--- MANTIDO
            'tipo_profissional',     # <--- MANTIDO
            'tipo_registro',         # <--- MANTIDO
            'registro_profissional', # <--- MANTIDO
            'is_active'
        ]

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user
