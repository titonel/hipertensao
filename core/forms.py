from django import forms
from .models import Paciente, Afericao, Medicamento, Usuario


class PacienteForm(forms.ModelForm):
    class Meta:
        model = Paciente
        fields = '__all__'

    def clean_cpf(self):
        cpf = self.cleaned_data['cpf']
        return cpf.replace('.', '').replace('-', '')


class UsuarioForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['first_name', 'email', 'drt', 'is_active', 'mudar_senha']