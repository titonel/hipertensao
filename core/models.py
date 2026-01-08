from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import date


class Usuario(AbstractUser):
    # Django já tem: username, password, is_active, first_name
    email = models.EmailField('E-mail', unique=True)
    drt = models.CharField('DRT', max_length=8)
    mudar_senha = models.BooleanField(default=False)
    email_verificado = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'  # Login será pelo E-mail
    REQUIRED_FIELDS = ['username', 'drt']

    def __str__(self):
        return self.get_full_name() or self.username


class Medicamento(models.Model):
    classe = models.CharField(max_length=100)
    principio_ativo = models.CharField(max_length=100, unique=True)
    dose_padrao = models.CharField(max_length=50)
    nomes_comerciais = models.CharField(max_length=255, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['classe', 'principio_ativo']

    def __str__(self):
        return f"{self.principio_ativo} ({self.dose_padrao})"


class Paciente(models.Model):
    SEXO_CHOICES = [('M', 'Masculino'), ('F', 'Feminino')]
    ETNIA_CHOICES = [
        ('Branca', 'Branca'), ('Parda', 'Parda'),
        ('Negra', 'Negra'), ('Indígena', 'Indígena')
    ]

    nome = models.CharField(max_length=100)
    cpf = models.CharField(max_length=14, unique=True)
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES)
    etnia = models.CharField(max_length=20, choices=ETNIA_CHOICES)
    data_nascimento = models.DateField()
    data_insercao = models.DateField(default=date.today)
    data_alta = models.DateField(null=True, blank=True)

    municipio = models.CharField(max_length=100, default='Caraguatatuba')
    telefone = models.CharField(max_length=20, blank=True)
    ativo = models.BooleanField(default=True)

    # Memória da última altura
    altura_ultima = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return self.nome

    @property
    def idade(self):
        if not self.data_nascimento: return 0
        hoje = date.today()
        return hoje.year - self.data_nascimento.year - (
                    (hoje.month, hoje.day) < (self.data_nascimento.month, self.data_nascimento.day))


class Afericao(models.Model):
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='afericoes')
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT)
    data_afericao = models.DateTimeField(auto_now_add=True)

    pressao_sistolica = models.IntegerField()
    pressao_diastolica = models.IntegerField()
    frequencia_cardiaca = models.IntegerField(null=True, blank=True)

    peso = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    altura = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    imc = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    observacao = models.TextField(blank=True)
    medicamentos = models.ManyToManyField(Medicamento, blank=True)

    class Meta:
        ordering = ['-data_afericao']