from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import date
from .services_cid import converter_cid10_para_cid11

class Usuario(AbstractUser):
    # --- 1. CAMPOS DE CONTROLE (RESTAURADOS) ---
    mudar_senha = models.BooleanField(default=False, verbose_name="Forçar Troca de Senha")
    email_verificado = models.BooleanField(default=False, verbose_name="Email Verificado")

    # --- 2. CAMPOS PROFISSIONAIS (NOVOS) ---
    TIPO_PROFISSIONAL_CHOICES = [
        ('MED', 'Médico'),
        ('ENF', 'Enfermeiro'),
        ('NUT', 'Nutricionista'),
        ('FAR', 'Farmacêutico'),
    ]

    TIPO_REGISTRO_CHOICES = [
        ('CRM', 'CRM'),
        ('COREN', 'COREN'),
        ('CRN', 'CRN'),
        ('CRF', 'CRF'),
    ]

    tipo_profissional = models.CharField(
        max_length=3,
        choices=TIPO_PROFISSIONAL_CHOICES,
        null=True,
        blank=True,
        verbose_name="Tipo Profissional"
    )

    tipo_registro = models.CharField(
        max_length=10,
        choices=TIPO_REGISTRO_CHOICES,
        null=True,
        blank=True,
        verbose_name="Conselho (Ex: CRM)"
    )

    registro_profissional = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name="Número do Conselho"
    )

    drt = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name="DRT / Matrícula"
    )

    # --- 3. MÉTODOS AUXILIARES ---
    @property
    def assinatura_completa(self):
        """Retorna uma string formatada para assinatura em documentos/PDFs"""
        nome = self.get_full_name() or self.username
        detalhes = []

        # Adiciona Conselho se tiver
        if self.tipo_registro and self.registro_profissional:
            detalhes.append(f"{self.tipo_registro}: {self.registro_profissional}")

        # Adiciona DRT se tiver (opcional na assinatura, mas disponível)
        if self.drt:
            detalhes.append(f"Matrícula: {self.drt}")

        if detalhes:
            return f"{nome} | {' - '.join(detalhes)}"
        return nome

    def __str__(self):
        return self.assinatura_completa


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
    siresp = models.CharField(max_length=20, null=True, blank=True, verbose_name="Número CROSS / SIRESP")

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


class AtendimentoMultidisciplinar(models.Model):
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='atendimentos_multi')
    profissional = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)
    data_atendimento = models.DateTimeField(auto_now_add=True)

    # Antropometria
    peso = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Peso (kg)")
    altura = models.DecimalField(max_digits=3, decimal_places=2, verbose_name="Altura (m)")
    imc = models.DecimalField(max_digits=4, decimal_places=2, verbose_name="IMC", blank=True, null=True)
    circunferencia_abdominal = models.DecimalField(max_digits=5, decimal_places=2,
                                                   verbose_name="Circunferência Abdominal (cm)")

    # Fatores de Risco / Comorbidades
    # --- NOVOS CAMPOS: DIABETES ---
    tem_diabetes = models.BooleanField(default=False)
    TIPO_DIABETES_CHOICES = [
        ('1', 'Tipo 1'),
        ('2', 'Tipo 2'),
        ('G', 'Gestacional'),
    ]
    tipo_diabetes = models.CharField(max_length=1, choices=TIPO_DIABETES_CHOICES, blank=True, null=True)

    # --- NOVOS CAMPOS: TABAGISMO ---
    fumante = models.BooleanField(default=False)
    macos_por_dia = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    anos_fumando = models.IntegerField(blank=True, null=True)
    carga_tabagica = models.DecimalField(max_digits=6, decimal_places=1, blank=True, null=True,
                                         verbose_name="Anos-Maço")

    # --- NOVOS CAMPOS: LESÃO DE ÓRGÃO-ALVO (Checkboxes) ---
    tem_lesao_orgao = models.BooleanField(default=False)
    loa_coracao = models.BooleanField(default=False, verbose_name="Coração (HVE/IAM)")
    loa_cerebro = models.BooleanField(default=False, verbose_name="Cérebro (AVC/AIT)")
    loa_rins = models.BooleanField(default=False, verbose_name="Rins (Doença Renal)")
    loa_arterias = models.BooleanField(default=False, verbose_name="Artérias Periféricas")
    loa_olhos = models.BooleanField(default=False, verbose_name="Retinopatia")

    # Observações gerais da equipe (Enfermagem/Farmácia)
    observacoes = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        # 1. Calcula IMC (Garante conversão para float)
        if self.peso and self.altura:
            self.imc = float(self.peso) / (float(self.altura) ** 2)

        # 2. Calcula Carga Tabágica (Maços x Anos)
        # CORREÇÃO: Converter AMBOS para float antes de multiplicar
        if self.fumante and self.macos_por_dia and self.anos_fumando:
            try:
                maços = float(self.macos_por_dia)
                anos = float(self.anos_fumando)
                self.carga_tabagica = maços * anos
            except ValueError:
                # Se houver erro de conversão, assume 0
                self.carga_tabagica = 0
        else:
            self.carga_tabagica = 0

        super().save(*args, **kwargs)

    # --- Calculadora PREVENT (AHA/DBH 2025) ---
class AvaliacaoPrevent(models.Model):
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE)
    data_avaliacao = models.DateTimeField(auto_now_add=True)

    # Dados Biomédicos (Puxados ou Inseridos)
    idade = models.IntegerField()
    sexo = models.CharField(max_length=1)  # M ou F
    colesterol_total = models.IntegerField(verbose_name="Colesterol Total (mg/dL)")
    hdl = models.IntegerField(verbose_name="HDL (mg/dL)")
    pressao_sistolica = models.IntegerField(verbose_name="PAS (mmHg)")
    em_tratamento_has = models.BooleanField(default=True, verbose_name="Em tto Anti-hipertensivo?")
    tem_diabetes = models.BooleanField(default=False)
    fumante = models.BooleanField(default=False)
    tfg = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="eGFR (ml/min)")

    # Resultados do Cálculo
    risco_10_anos = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Risco 10 Anos (%)")
    risco_30_anos = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Risco 30 Anos (%)")

    class Meta:
        verbose_name = "Avaliação PREVENT"

    def __str__(self):
        return f"Multi - {self.paciente.nome} - {self.data_atendimento}"


class TriagemHipertensao(models.Model):
    paciente = models.ForeignKey('Paciente', on_delete=models.CASCADE, related_name='triagens_has')

    # CORREÇÃO AQUI: Trocado 'Profissional' por 'Usuario'
    profissional = models.ForeignKey('Usuario', on_delete=models.SET_NULL, null=True)

    data_triagem = models.DateTimeField(default=timezone.now)

    # Entradas de Dados (Inputs)
    pa_sistolica_1 = models.IntegerField(verbose_name="PAS 1")
    pa_diastolica_1 = models.IntegerField(verbose_name="PAD 1")
    pa_sistolica_2 = models.IntegerField(verbose_name="PAS 2")
    pa_diastolica_2 = models.IntegerField(verbose_name="PAD 2")
    pa_sistolica_3 = models.IntegerField(verbose_name="PAS 3")
    pa_diastolica_3 = models.IntegerField(verbose_name="PAD 3")

    # Médias Calculadas
    media_sistolica = models.DecimalField(max_digits=5, decimal_places=1, blank=True)
    media_diastolica = models.DecimalField(max_digits=5, decimal_places=1, blank=True)

    qtd_antihipertensivos = models.IntegerField(default=0)
    risco_loa_presente = models.BooleanField(default=False)

    ESTADOS_DESFECHO = [
        ('ELEGIVEL', 'Elegível'),
        ('CONTRARREFERENCIA', 'Não Elegível')
    ]
    status_elegibilidade = models.CharField(max_length=20, choices=ESTADOS_DESFECHO)
    motivo_desfecho = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        self.media_sistolica = (self.pa_sistolica_1 + self.pa_sistolica_2 + self.pa_sistolica_3) / 3
        self.media_diastolica = (self.pa_diastolica_1 + self.pa_diastolica_2 + self.pa_diastolica_3) / 3
        super().save(*args, **kwargs)


# --- MODELO 2: ATENDIMENTO MÉDICO ---
class AtendimentoMedico(models.Model):
    paciente = models.ForeignKey('Paciente', on_delete=models.CASCADE)

    # CORREÇÃO AQUI: Trocado 'Profissional' por 'Usuario'
    medico = models.ForeignKey('Usuario', on_delete=models.SET_NULL, null=True)

    data_atendimento = models.DateTimeField(default=timezone.now)
    score_prevent_valor = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Score Prevent (%)")

    # SOAP
    subjetivo = models.TextField(verbose_name="S - Subjetivo")
    objetivo = models.TextField(verbose_name="O - Objetivo")
    avaliacao = models.TextField(verbose_name="A - Avaliação")
    plano = models.TextField(verbose_name="P - Plano")

    # Diagnósticos
    cid10_1 = models.CharField(max_length=10, verbose_name="CID-10 Principal")
    cid10_2 = models.CharField(max_length=10, blank=True, null=True)
    cid10_3 = models.CharField(max_length=10, blank=True, null=True)
    cid11_correspondente = models.CharField(max_length=200, blank=True)

    def save(self, *args, **kwargs):
        # Importação local para evitar Ciclo de Importação
        from .services_cid import converter_cid10_para_cid11
        if self.cid10_1:
            self.cid11_correspondente = converter_cid10_para_cid11(self.cid10_1)
        super().save(*args, **kwargs)

# --- MODELO 3: PRESCRIÇÃO ---
class PrescricaoMedica(models.Model):
    atendimento = models.OneToOneField(AtendimentoMedico, on_delete=models.CASCADE, related_name='prescricao')
    data_prescricao = models.DateTimeField(auto_now_add=True)
    observacoes_gerais = models.TextField(blank=True)


class ItemPrescricao(models.Model):
    TIPO_USO = [('CONTINUO', 'Uso Contínuo'), ('TEMPORARIO', 'Uso Temporário'), ('CONTROLADO', 'Controle Especial')]
    prescricao = models.ForeignKey(PrescricaoMedica, on_delete=models.CASCADE, related_name='itens')
    medicamento_nome = models.CharField(max_length=200)
    concentracao = models.CharField(max_length=100)
    posologia = models.TextField()
    quantidade = models.CharField(max_length=50)
    tipo = models.CharField(max_length=20, choices=TIPO_USO, default='CONTINUO')