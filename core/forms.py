from django import forms
from .models import Paciente, Usuario, TriagemHipertensao, AtendimentoMedico

class PacienteForm(forms.ModelForm):
    class Meta:
        model = Paciente
        fields = '__all__'
        widgets = {
            'data_nascimento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'data_insercao': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

class UsuarioForm(forms.ModelForm):
    # Campo opcional para definir senha ao criar/editar
    password = forms.CharField(widget=forms.PasswordInput(), required=False, label="Senha")

    class Meta:
        model = Usuario
        # Listamos apenas os campos que realmente existem no modelo atualizado
        fields = [
            'first_name',
            'last_name',
            'username',              # Necessário para o login
            'email',
            'mudar_senha',
            'drt',
            'tipo_profissional',
            'tipo_registro',
            'registro_profissional',
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

class TriagemHASForm(forms.ModelForm):
    class Meta:
        model = TriagemHipertensao
        fields = [
            'pa_sistolica_1', 'pa_diastolica_1',
            'pa_sistolica_2', 'pa_diastolica_2',
            'pa_sistolica_3', 'pa_diastolica_3',
            'qtd_antihipertensivos', 'risco_loa_presente'
        ]
        widgets = {
            'pa_sistolica_1': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'PAS 1'}),
            'pa_diastolica_1': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'PAD 1'}),
            'pa_sistolica_2': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'PAS 2'}),
            'pa_diastolica_2': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'PAD 2'}),
            'pa_sistolica_3': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'PAS 3'}),
            'pa_diastolica_3': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'PAD 3'}),
            'qtd_antihipertensivos': forms.NumberInput(attrs={'class': 'form-control'}),
            'risco_loa_presente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class AtendimentoMedicoForm(forms.ModelForm):
    class Meta:
        model = AtendimentoMedico
        fields = [
            'subjetivo', 'objetivo', 'avaliacao', 'plano',
            'cid10_1', 'cid10_2', 'cid10_3'
        ]
        widgets = {
            'subjetivo': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Queixa principal, HMA, Revisão de Sistemas...'}),
            'objetivo': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Exame físico, Sinais Vitais, Resultados de Exames...'}),
            'avaliacao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Hipóteses diagnósticas e Raciocínio Clínico...'}),
            'plano': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Conduta, Orientações, Solicitações...'}),
            'cid10_1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: I10 (Obrigatório)'}),
            'cid10_2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: E11'}),
            'cid10_3': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Z00'}),
        }