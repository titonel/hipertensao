import os
import base64
import requests
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.staticfiles import finders
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.db.models import Q, Avg, Count, F, ExpressionWrapper, fields
from django.http import JsonResponse, HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.conf import settings
from datetime import datetime, date, timedelta
from .models import Paciente, Medicamento, Afericao, Usuario, AtendimentoMultidisciplinar, AvaliacaoPrevent, AtendimentoMedico, TriagemHipertensao
from .forms import PacienteForm, UsuarioForm, AtendimentoMedicoForm, TriagemHASForm, AtendimentoMedicoForm

# Função auxiliar para idade
def calcular_idade(nascimento):
    hoje = date.today()
    return hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))

# Função auxiliar para converter imagem em Base64
def get_base64_image(filename):
    """Lê o arquivo físico e retorna o código Base64"""
    # Monta o caminho manualmente
    path = os.path.join(settings.BASE_DIR, 'core', 'static', 'img', filename)

    # Debug no terminal
    if not os.path.exists(path):
        print(f"ERRO B64: Arquivo não existe: {path}")
        return None

    try:
        with open(path, "rb") as image_file:
            # Lê binário, converte para b64, decodifica para string utf-8
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            print(f"SUCESSO B64: Imagem {filename} carregada ({len(encoded_string)} bytes)")
            return encoded_string
    except Exception as e:
        print(f"ERRO B64 ao ler arquivo: {e}")
        return None


def prescricao_medica_view(request, atendimento_id):
    atendimento = get_object_or_404(AtendimentoMedico, id=atendimento_id)

    # Tenta pegar a prescrição existente ou cria uma nova vazia
    prescricao, created = PrescricaoMedica.objects.get_or_create(atendimento=atendimento)

    # Fábrica de Formsets: Permite editar os Itens vinculados à Prescrição
    ItemPrescricaoFormSet = inlineformset_factory(
        PrescricaoMedica,
        ItemPrescricao,
        fields=('medicamento_nome', 'concentracao', 'posologia', 'quantidade', 'tipo'),
        extra=1,  # Mostra 1 linha vazia para adicionar
        can_delete=True
    )

    if request.method == 'POST':
        formset = ItemPrescricaoFormSet(request.POST, instance=prescricao)
        if formset.is_valid():
            formset.save()
            # Redireciona para gerar o PDF ou volta para lista
            return redirect('detalhe_paciente', paciente_id=atendimento.paciente.id)
    else:
        formset = ItemPrescricaoFormSet(instance=prescricao)

    # Separação visual para o Template (Opcional, se quiser renderizar em tabelas separadas)
    # No template você pode iterar e verificar: {% if form.instance.tipo == 'CONTROLADO' %}

    context = {
        'atendimento': atendimento,
        'paciente': atendimento.paciente,
        'formset': formset,
    }

    return render(request, 'atendimento/prescricao_form.html', context)

def login_view(request):
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not user.is_active:
                messages.error(request, 'Usuário inativo.')
            else:
                login(request, user)
                if user.mudar_senha:
                    return redirect('trocar_senha')
                return redirect('index')
        else:
            messages.error(request, 'E-mail ou senha inválidos.')
    return render(request, 'login.html')

# Função utilitária para lidar com imagens estáticas no PDF - ROBUSTA para Windows/Linux/Dev/Prod
def link_callback(uri, rel):
    """
    Abordagem 'Nuclear': Identifica o arquivo pelo nome e força o caminho absoluto.
    Isso elimina qualquer erro de barra invertida, url relativa ou static_url.
    """
    # Pega apenas o nome do arquivo (ex: 'header.png' de '/static/img/header.png')
    filename = os.path.basename(uri)

    # Lista de arquivos conhecidos que precisamos garantir
    imagens_sistema = ['header.png', 'footer.png']

    path = None

    # 1. Se for uma das nossas imagens de layout, forçamos o caminho fixo
    if filename in imagens_sistema:
        path = os.path.join(settings.BASE_DIR, 'core', 'static', 'img', filename)

    # 2. Se não for, tentamos a lógica padrão para MEDIA (uploads do paciente, se houver)
    elif settings.MEDIA_URL in uri:
        media_name = uri.split(settings.MEDIA_URL)[-1]
        path = os.path.join(settings.MEDIA_ROOT, media_name)

    # 3. Se ainda não achou, tenta montar o caminho estático genérico
    else:
        path = os.path.join(settings.BASE_DIR, 'core', 'static', 'img', filename)

    # Verifica se existe
    if path and os.path.isfile(path):
        return path
    else:
        print(f"DEBUG PDF: Arquivo não encontrado no disco: {path}")
        return uri


def realizar_atendimento_medico(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)

    # Busca o último score prevent calculado (ex: na triagem ou pré-consulta)
    # Supondo que você tenha salvo isso em algum lugar, ou calculamos na hora
    ultimo_score = 12.5  # VALOR EXEMPLO (Risco Intermediário) - Substituir por busca no banco

    if request.method == 'POST':
        form = AtendimentoMedicoForm(request.POST)
        if form.is_valid():
            atendimento = form.save(commit=False)
            atendimento.paciente = paciente
            atendimento.medico = request.user  # Usuário logado
            atendimento.score_prevent_valor = ultimo_score
            atendimento.save()  # O save() já chama a conversão de CID

            # REDIRECIONAMENTO PARA PRESCRIÇÃO
            return redirect('prescricao_medica', atendimento_id=atendimento.id)
    else:
        form = AtendimentoMedicoForm()

    # Prepara dados visuais do risco
    # Logica visual replicada aqui para o template (ou usar método do model se tiver instância)
    classe_risco = ""
    texto_risco = ""
    if ultimo_score < 5:
        classe_risco, texto_risco = "bg-success text-white", "Baixo Risco"
    elif ultimo_score < 7.5:
        classe_risco, texto_risco = "bg-warning text-dark", "Risco Limítrofe"
    elif ultimo_score < 20:
        classe_risco, texto_risco = "orange-bg text-white", "Risco Intermediário"  # Definir CSS orange-bg
    else:
        classe_risco, texto_risco = "bg-danger text-white", "Alto Risco"

    context = {
        'paciente': paciente,
        'form': form,
        'prevent_score': ultimo_score,
        'risco_css': classe_risco,
        'risco_texto': texto_risco,
        'cids_comuns': ['I10', 'E11', 'I50', 'I20']  # Para autocomplete no front
    }

    return render(request, 'atendimento/ficha_medica.html', context)

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def trocar_senha(request):
    if request.method == 'POST':
        nova = request.POST.get('nova_senha')
        conf = request.POST.get('confirmacao')
        if nova == conf and len(nova) >= 6:
            request.user.set_password(nova)
            request.user.mudar_senha = False
            request.user.save()
            update_session_auth_hash(request, request.user)  # Mantém logado
            messages.success(request, 'Senha alterada com sucesso!')
            return redirect('index')
        else:
            messages.error(request, 'Senhas não conferem ou muito curtas.')
    return render(request, 'trocar_senha.html')


# --- Dashboard ---

@login_required
def index(request):
    if request.user.mudar_senha: return redirect('trocar_senha')
    return render(request, 'index.html')

@login_required
def dashboard_clinico(request):
    # Busca municípios distintos para montar o filtro
    municipios = Paciente.objects.values_list('municipio', flat=True).distinct().order_by('municipio')
    return render(request, 'indices.html', {'municipios': municipios})

@login_required
def api_dashboard(request):
    # Filtro de Municípios (Multi-select)
    cidades_selecionadas = request.GET.getlist('municipios[]')

    # QuerySet Base
    pacientes = Paciente.objects.filter(ativo=True)

    if cidades_selecionadas:
        pacientes = pacientes.filter(municipio__in=cidades_selecionadas)

    total_pacientes = pacientes.count()

    # --- AFERIÇÕES NO MÊS ---
    hoje = datetime.now()
    # Filtra aferições apenas dos pacientes do queryset filtrado
    total_afericoes = Afericao.objects.filter(
        data_afericao__month=hoje.month,
        data_afericao__year=hoje.year,
        paciente__in=pacientes
    ).count()

    # --- CONTROLE DA PA (Amostra dos pacientes filtrados) ---
    controlados = 0
    nao_controlados = 0
    sem_dados = 0

    # Nota: Em produção com muitos dados, isso deve ser otimizado via SQL/Annotate
    for p in pacientes:
        ultima = p.afericoes.first()  # Já ordenado no Model
        if not ultima:
            sem_dados += 1
        elif ultima.pressao_sistolica < 140 and ultima.pressao_diastolica < 90:
            controlados += 1
        else:
            nao_controlados += 1

    # --- DISTRIBUIÇÃO POR SEXO ---
    sexo_stats = pacientes.values('sexo').annotate(total=Count('sexo'))
    sexo_data = {'M': 0, 'F': 0}
    for item in sexo_stats:
        sexo_data[item['sexo']] = item['total']

    # --- DISTRIBUIÇÃO POR MUNICÍPIO ---
    mun_stats = pacientes.values('municipio').annotate(total=Count('municipio')).order_by('-total')
    mun_labels = [m['municipio'] for m in mun_stats]
    mun_data = [m['total'] for m in mun_stats]

    # --- DISTRIBUIÇÃO POR IDADE E TEMPO MÉDIO ---
    faixas_etarias = {'<40': 0, '40-59': 0, '60-79': 0, '80+': 0}
    soma_dias_lc = 0

    data_atual = date.today()

    for p in pacientes:
        # Cálculo Idade
        idade = 0
        if p.data_nascimento:
            idade = data_atual.year - p.data_nascimento.year - (
                        (data_atual.month, data_atual.day) < (p.data_nascimento.month, p.data_nascimento.day))

        if idade < 40:
            faixas_etarias['<40'] += 1
        elif idade < 60:
            faixas_etarias['40-59'] += 1
        elif idade < 80:
            faixas_etarias['60-79'] += 1
        else:
            faixas_etarias['80+'] += 1

        # Cálculo Tempo de Permanência (em meses)
        if p.data_insercao:
            delta = data_atual - p.data_insercao
            soma_dias_lc += delta.days

    tempo_medio_meses = 0
    if total_pacientes > 0:
        tempo_medio_meses = round((soma_dias_lc / total_pacientes) / 30, 1)

    return JsonResponse({
        'kpi_pacientes': total_pacientes,
        'kpi_afericoes': total_afericoes,
        'kpi_tempo_medio': tempo_medio_meses,
        'controle_pa': [controlados, nao_controlados, sem_dados],
        'sexo_dist': [sexo_data['M'], sexo_data['F']],
        'idade_labels': list(faixas_etarias.keys()),
        'idade_data': list(faixas_etarias.values()),
        'mun_labels': mun_labels,
        'mun_data': mun_data
    })

# --- Pacientes ---

@login_required
def gestao_pacientes(request):
    pacientes = Paciente.objects.all().order_by('nome')
    return render(request, 'pacientes.html', {'pacientes': pacientes})


@login_required
def salvar_paciente(request):
    if request.method == 'POST':
        pid = request.POST.get('paciente_id')
        data = request.POST.copy()

        # Tratamento de CPF
        if 'cpf' in data: data['cpf'] = data['cpf'].replace('.', '').replace('-', '')

        if pid:
            instance = get_object_or_404(Paciente, id=pid)
            form = PacienteForm(data, instance=instance)
        else:
            form = PacienteForm(data)

        if form.is_valid():
            form.save()
            messages.success(request, 'Paciente salvo!')
        else:
            messages.error(request, f'Erro: {form.errors}')

    return redirect('gestao_pacientes')


@login_required
def api_paciente(request, id):
    p = get_object_or_404(Paciente, id=id)
    return JsonResponse({
        'id': p.id,
        'nome': p.nome,
        'cpf': p.cpf,
        'sexo': p.sexo,
        'etnia': p.etnia,
        'data_nascimento': p.data_nascimento,
        'data_insercao': p.data_insercao,
        'municipio': p.municipio,
        'telefone': p.telefone,
        'ativo': p.ativo
    })


# --- Atendimento ---

@login_required
def atendimento(request):
    paciente = None
    historico = []

    # Listas para o Gráfico
    grafico_data = {
        'labels': [],
        'sys': [],
        'dia': [],
        'pam': [],  # Pressão Média
        'imc': []
    }

    # Agrupamento de medicamentos (Lógica anterior mantida)
    meds_db = Medicamento.objects.filter(ativo=True).order_by('classe', 'principio_ativo')
    meds_agrupados = {}
    for m in meds_db:
        if m.classe not in meds_agrupados: meds_agrupados[m.classe] = []
        meds_agrupados[m.classe].append(m)

    ordem_classes = ['IECA', 'BRA', 'Diurético Tiazídico', 'Bloq. Canal de Cálcio (Diidropiridínico)',
                     'Diurético de Alça', 'Betabloqueador', 'Diurético Poupador de K+',
                     'Agonista Central', 'Vasodilatador Direto']

    pid = request.GET.get('id')
    termo = request.POST.get('busca_termo')

    if pid:
        paciente = get_object_or_404(Paciente, id=pid)
    elif request.method == 'POST' and termo:
        paciente = Paciente.objects.filter(Q(cpf=termo) | Q(nome__icontains=termo)).first()

    if paciente:
        # Busca as últimas 20 aferições para o gráfico ficar mais rico que a tabela
        qs_historico = paciente.afericoes.all().order_by('-data_afericao')[:20]
        historico = qs_historico  # A tabela usa esse queryset (do mais novo pro mais antigo)

        # Para o gráfico, precisamos da ordem cronológica (do mais antigo pro mais novo)
        dados_cronologicos = reversed(qs_historico)

        for a in dados_cronologicos:
            # Formata data para dia/mês
            grafico_data['labels'].append(a.data_afericao.strftime("%d/%m"))
            grafico_data['sys'].append(a.pressao_sistolica)
            grafico_data['dia'].append(a.pressao_diastolica)

            # Cálculo da PAM (Pressão Arterial Média) aprox: PAD + (PAS-PAD)/3
            pam = round(a.pressao_diastolica + (a.pressao_sistolica - a.pressao_diastolica) / 3, 1)
            grafico_data['pam'].append(pam)

            # IMC (pode ser None no banco, tratar para 0 ou null pro JS ignorar)
            grafico_data['imc'].append(float(a.imc) if a.imc else None)

    return render(request, 'atendimento.html', {
        'paciente': paciente,
        'historico': historico,
        'meds_agrupados': meds_agrupados,
        'ordem_classes': ordem_classes,
        'grafico_data': grafico_data  # Enviando os dados processados
    })


@login_required
def atendimento_hub(request):
    """
    Tela inicial do Atendimento (PEP).
    1. Busca o paciente.
    2. Se encontrar, mostra os 3 cartões de opção (Médico, Multi, Nutrição).
    """
    paciente = None
    erro = None

    if request.method == 'POST':
        termo = request.POST.get('busca_termo')
        # Tenta buscar por CPF ou Nome
        pacientes = Paciente.objects.filter(cpf=termo) | Paciente.objects.filter(nome__icontains=termo)

        if pacientes.exists():
            paciente = pacientes.first()  # Pega o primeiro encontrado
        else:
            erro = "Paciente não encontrado."

    return render(request, 'atendimento_hub.html', {'paciente': paciente, 'erro': erro})


@login_required
def atendimento_multidisciplinar(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    idade = calcular_idade(paciente.data_nascimento)

    # Busca a última PA registrada para a decisão clínica
    ultima_afericao = paciente.afericoes.first()  # Model ordena por -data_afericao

    if request.method == 'POST':
        # 1. Coleta dados do formulário
        peso = request.POST.get('peso').replace(',', '.')
        altura = request.POST.get('altura').replace(',', '.')
        circunf = request.POST.get('circunf').replace(',', '.')

        # Booleanos e Checkboxes
        tem_diabetes = True if request.POST.get('diabetes') == 'on' else False
        fumante = True if request.POST.get('fumante') == 'on' else False

        # Lesões de Órgão Alvo (LOA)
        loa_coracao = True if request.POST.get('loa_coracao') == 'on' else False
        loa_cerebro = True if request.POST.get('loa_cerebro') == 'on' else False
        loa_rins = True if request.POST.get('loa_rins') == 'on' else False
        loa_arterias = True if request.POST.get('loa_arterias') == 'on' else False
        loa_olhos = True if request.POST.get('loa_olhos') == 'on' else False

        tem_loa = any([loa_coracao, loa_cerebro, loa_rins, loa_arterias, loa_olhos,
                       request.POST.get('tem_loa') == 'on'])

        # 2. Salva o Atendimento no Banco
        AtendimentoMultidisciplinar.objects.create(
            paciente=paciente,
            profissional=request.user,
            peso=peso,
            altura=altura,
            circunferencia_abdominal=circunf,
            tem_diabetes=tem_diabetes,
            tipo_diabetes=request.POST.get('tipo_diabetes'),
            fumante=fumante,
            macos_por_dia=float(request.POST.get('macos').replace(',', '.')) if request.POST.get('macos') else 0,
            anos_fumando=int(request.POST.get('anos_fumando')) if request.POST.get('anos_fumando') else 0,
            tem_lesao_orgao=tem_loa,
            loa_coracao=loa_coracao,
            loa_cerebro=loa_cerebro,
            loa_rins=loa_rins,
            loa_arterias=loa_arterias,
            loa_olhos=loa_olhos,
            observacoes=request.POST.get('obs')
        )

        # 3. LÓGICA DE DECISÃO AUTOMÁTICA (Diretriz 2025)
        eligible = False
        motivo_ineligivel = ""

        if not ultima_afericao:
            # Se não tem PA medida, assume elegível por precaução ou trata erro
            messages.warning(request, "Atenção: Paciente sem aferição de PA recente.")
            eligible = True
        else:
            pas = ultima_afericao.pressao_sistolica
            pad = ultima_afericao.pressao_diastolica

            # Estágio 2 ou 3 (PAS >= 140 OU PAD >= 90)
            is_estagio_2_plus = (pas >= 140) or (pad >= 90)

            # Estágio 1 (PAS 130-139 OU PAD 80-89)
            is_estagio_1 = (130 <= pas < 140) or (80 <= pad < 90)

            # Critérios de Inclusão AME:
            # 1. HAS Estágio 2 ou 3 (independente de risco)
            # 2. HAS Estágio 1 COM Alto Risco (Diabetes, LOA ou DRC)

            has_alto_risco = tem_diabetes or tem_loa or loa_rins

            if is_estagio_2_plus:
                eligible = True
            elif is_estagio_1 and has_alto_risco:
                eligible = True
            else:
                eligible = False
                if is_estagio_1:
                    motivo_ineligivel = "PA limítrofe ou Estágio 1 sem alto risco cardiovascular."
                else:
                    motivo_ineligivel = "Hipertensão controlada ou PA normal."

        # 4. Redirecionamento Baseado na Decisão
        if eligible:
            messages.success(request, "Paciente ELEGÍVEL. Gerando Kit de Exames...")
            return redirect('gerar_kit_exames', paciente_id=paciente.id)
        else:
            # Salva o motivo na sessão temporária ou passa via GET (simplificado aqui via sessão)
            request.session['motivo_contrarreferencia'] = motivo_ineligivel
            messages.warning(request, "Paciente NÃO ELEGÍVEL. Gerando Contrarreferência...")
            return redirect('gerar_contrarreferencia_triagem', paciente_id=paciente.id)

    return render(request, 'atendimento_multidisciplinar.html', {
        'paciente': paciente,
        'idade': idade
    })


@login_required
def gerar_kit_exames(request, paciente_id):
    """Gera o Kit de Exames atualizado (Diretriz 2025) para pacientes elegíveis"""
    paciente = get_object_or_404(Paciente, id=paciente_id)
    idade = calcular_idade(paciente.data_nascimento)
    header_b64 = get_base64_image('header.png')

    context = {
        'paciente': paciente,
        'idade': idade,
        'usuario': request.user,
        'data_hoje': date.today(),
        'header_b64': header_b64,
    }

    template_path = 'pdf_kit_exames.html'  # Vamos criar este arquivo
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="kit_exames_{paciente.nome}.pdf"'

    template = get_template(template_path)
    html = template.render(context)
    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse(f'Erro PDF: {pisa_status.err}')
    return response


@login_required
def gerar_contrarreferencia_triagem(request, paciente_id):
    """Gera Contrarreferência imediata para pacientes não elegíveis na triagem"""
    paciente = get_object_or_404(Paciente, id=paciente_id)
    motivo = request.session.get('motivo_contrarreferencia', 'Critérios de elegibilidade não atingidos.')

    header_b64 = get_base64_image('header.png')
    footer_b64 = get_base64_image('footer.png')

    context = {
        'paciente': paciente,
        'usuario': request.user,
        'hoje': date.today(),
        'motivo': motivo,
        'header_b64': header_b64,
        'footer_b64': footer_b64,
    }

    template_path = 'pdf_contrarreferencia_triagem.html'  # Vamos criar este arquivo
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="contrarreferencia_{paciente.nome}.pdf"'

    template = get_template(template_path)
    html = template.render(context)
    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse(f'Erro PDF: {pisa_status.err}')
    return response

@login_required
def registrar_afericao(request):
    if request.method == 'POST':
        paciente = get_object_or_404(Paciente, id=request.POST.get('paciente_id'))

        afericao = Afericao(
            paciente=paciente,
            usuario=request.user,
            pressao_sistolica=request.POST.get('sistolica'),
            pressao_diastolica=request.POST.get('diastolica'),
            frequencia_cardiaca=request.POST.get('fc') or None,
            observacao=request.POST.get('obs')
        )

        peso = request.POST.get('peso', '').replace(',', '.')
        altura = request.POST.get('altura', '').replace(',', '.')

        if peso: afericao.peso = peso
        if altura:
            afericao.altura = altura
            paciente.altura_ultima = altura
            paciente.save()

        if peso and altura:
            try:
                afericao.imc = round(float(peso) / (float(altura) ** 2), 2)
            except:
                pass

        afericao.save()

        meds_ids = request.POST.getlist('medicamentos')
        if meds_ids:
            afericao.medicamentos.set(meds_ids)

        messages.success(request, 'Aferição registrada!')
        return redirect(f'/atendimento/?id={paciente.id}')
    return redirect('index')

@login_required
def gerar_alta(request, id):
    paciente = get_object_or_404(Paciente, id=id)

    # 1. Atualiza Status
    try:
        paciente.ativo = False
        paciente.data_alta = date.today()
        paciente.save()
    except Exception as e:
        print(f"Erro ao salvar: {e}")

    # 2. Carrega imagens na memória (Convertendo para Base64)
    header_b64 = get_base64_image('header.png')
    footer_b64 = get_base64_image('footer.png')

    # 3. Prepara Contexto
    ultima_afericao = paciente.afericoes.order_by('-data_afericao').first()
    medicamentos = ultima_afericao.medicamentos.all() if ultima_afericao else []

    context = {
        'paciente': paciente,
        'medicamentos': medicamentos,
        'hoje': date.today(),
        'usuario': request.user,
        'ultima_pa': f"{ultima_afericao.pressao_sistolica}x{ultima_afericao.pressao_diastolica}" if ultima_afericao else 'N/A',
        'ultimo_imc': ultima_afericao.imc if ultima_afericao else 'N/A',

        # Passa os códigos Base64
        'header_b64': header_b64,
        'footer_b64': footer_b64,
    }

    # 4. Gera PDF
    template_path = 'pdf_alta.html'
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="alta_{paciente.nome}.pdf"'

    template = get_template(template_path)
    html = template.render(context)

    # ATENÇÃO: Removemos o link_callback pois as imagens já estão embutidas
    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse(f'Erro ao gerar PDF: {pisa_status.err}')

    return response


@login_required
def gerar_pedido_exames(request, paciente_id):
    """
    Gera PDF de 4 páginas com pedidos de exames do protocolo.
    """
    paciente = get_object_or_404(Paciente, id=paciente_id)
    idade = calcular_idade(paciente.data_nascimento)

    # Carrega imagem do header em Base64 (Reutilizando a função que criamos antes)
    header_b64 = get_base64_image('header.png')

    # Contexto para o template
    context = {
        'paciente': paciente,
        'idade': idade,
        'usuario': request.user,
        'data_hoje': date.today(),
        'header_b64': header_b64,
    }

    # Renderização do PDF
    template_path = 'pdf_pedidos_exames.html'
    response = HttpResponse(content_type='application/pdf')
    # O arquivo será baixado com este nome:
    response['Content-Disposition'] = f'attachment; filename="pedidos_{paciente.nome}.pdf"'

    template = get_template(template_path)
    html = template.render(context)

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse(f'Erro ao gerar PDF: {pisa_status.err}')

    return response



# --- Gestão de Usuários e Medicamentos ---
@login_required
def gestao_usuarios(request):
    """
    Lista usuários e processa o formulário de cadastro (Modal).
    """
    # 1. LÓGICA DE SALVAR (POST)
    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Usuário cadastrado com sucesso!")
                return redirect('gestao_usuarios')  # Recarrega a página limpa
            except Exception as e:
                messages.error(request, f"Erro ao salvar: {e}")
        else:
            # Se o formulário for inválido (ex: usuário já existe, email inválido)
            # Mostraremos o erro no topo da tela via Messages
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Erro no campo '{field}': {error}")

    # 2. LÓGICA DE LISTAGEM (GET)
    users = Usuario.objects.all().order_by('first_name')

    return render(request, 'gestao_usuarios.html', {'users': users})


@login_required
def salvar_usuario(request):
    if request.method == 'POST':
        uid = request.POST.get('usuario_id')
        drt = request.POST.get('drt')
        email = request.POST.get('email')
        nome = request.POST.get('nome')

        if uid:
            u = get_object_or_404(Usuario, id=uid)
        else:
            if Usuario.objects.filter(email=email).exists():
                messages.error(request, 'Email já existe.')
                return redirect('gestao_usuarios')
            u = Usuario.objects.create_user(username=email, email=email, password=drt)
            u.mudar_senha = True  # Novo usuário deve trocar senha

        u.first_name = nome
        u.drt = drt
        u.is_active = True if request.POST.get('ativo') else False
        u.mudar_senha = True if request.POST.get('mudar_senha') else False
        u.save()
        messages.success(request, 'Usuário salvo!')
    return redirect('gestao_usuarios')


@login_required
def gestao_medicamentos(request):
    # Busca todos os medicamentos para a lista
    medicamentos = Medicamento.objects.all().order_by('classe', 'principio_ativo')

    # Busca todas as classes únicas já cadastradas no banco (carregadas pelo setup_db)
    # Isso garante que o dropdown tenha exatamente as opções da Diretriz
    classes_disponiveis = Medicamento.objects.values_list('classe', flat=True).distinct().order_by('classe')

    return render(request, 'gestao_medicamentos.html', {
        'medicamentos': medicamentos,
        'classes_disponiveis': classes_disponiveis  # Enviamos essa lista para o HTML
    })


@login_required
def salvar_medicamento(request):
    if request.method == 'POST':
        med_id = request.POST.get('medicamento_id')

        # Se vier um ID, edita. Se não, cria novo.
        if med_id:
            m = get_object_or_404(Medicamento, id=med_id)
        else:
            m = Medicamento()

        m.classe = request.POST.get('classe')
        m.principio_ativo = request.POST.get('principio_ativo')
        m.dose_padrao = request.POST.get('dose_padrao')
        m.nomes_comerciais = request.POST.get('nomes_comerciais')
        m.ativo = True if request.POST.get('ativo') else False

        try:
            m.save()
            messages.success(request, 'Medicamento salvo com sucesso!')
        except Exception as e:
            messages.error(request, f'Erro ao salvar: {e}')

    return redirect('gestao_medicamentos')

@login_required
def api_usuario(request, id):
    u = get_object_or_404(Usuario, id=id)
    return JsonResponse({
        'id': u.id,
        'nome': u.first_name,
        'email': u.email,
        'drt': u.drt,
        'ativo': u.is_active,
        'mudar_senha': u.mudar_senha
    })


@login_required
def atendimento_prevent(request, paciente_id):
    """
    Calculadora PREVENT (AHA) - 2ª Consulta.
    """
    paciente = get_object_or_404(Paciente, id=paciente_id)
    idade = calcular_idade(paciente.data_nascimento)

    # Busca dados prévios para facilitar o preenchimento
    ultimo_multi = paciente.atendimentos_multi.last()
    ultima_afericao = paciente.afericoes.order_by('-data_afericao').first()

    if request.method == 'POST':
        # Salva o resultado do cálculo
        try:
            AvaliacaoPrevent.objects.create(
                paciente=paciente,
                idade=idade,
                sexo=paciente.sexo,

                # Dados clínicos
                colesterol_total=request.POST.get('col_total'),
                hdl=request.POST.get('hdl'),
                pressao_sistolica=request.POST.get('pas'),
                tfg=request.POST.get('tfg').replace(',', '.'),

                # Booleanos (Checkboxes)
                em_tratamento_has=True if request.POST.get('em_tto') == 'on' else False,
                tem_diabetes=True if request.POST.get('diabetes') == 'on' else False,
                fumante=True if request.POST.get('fumante') == 'on' else False,

                # Resultados Calculados (Vêm do JavaScript nos inputs hidden)
                risco_10_anos=request.POST.get('risco_10').replace(',', '.'),
                risco_30_anos=request.POST.get('risco_30').replace(',', '.')
            )
            return redirect('atendimento_hub')

        except Exception as e:
            # Se der erro (ex: campo vazio), imprime no console para debug
            print(f"Erro ao salvar PREVENT: {e}")

    context = {
        'paciente': paciente,
        'idade': idade,
        # Pré-preenchimento inteligente
        'pre_diabetes': ultimo_multi.tem_diabetes if ultimo_multi else False,
        'pre_fumante': ultimo_multi.fumante if ultimo_multi else False,
        'pre_pas': ultima_afericao.pressao_sistolica if ultima_afericao else ''
    }
    return render(request, 'atendimento_prevent.html', context)

@login_required
def monitoramento_busca(request):
    """
    Tela inicial do Monitoramento: Busca de Paciente.
    """
    erro = None
    if request.method == 'POST':
        termo = request.POST.get('busca_termo')

        # Busca por Nome, CPF ou SIRESP (Agora o campo existe!)
        pacientes = Paciente.objects.filter(
            nome__icontains=termo
        ) | Paciente.objects.filter(
            cpf=termo
        ) | Paciente.objects.filter(
            siresp=termo
        )

        # CORREÇÃO AQUI: A variável correta é 'pacientes' (português), não 'patients'
        if pacientes.exists():
            # Redireciona para o primeiro encontrado
            return redirect('monitoramento_painel', paciente_id=pacientes.first().id)
        else:
            erro = "Paciente não encontrado com esses dados."

    return render(request, 'monitoramento_busca.html', {'erro': erro})


@login_required
def monitoramento_painel(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)

    # 1. Contadores Internos
    # Assumindo que você tem relação inversa ou models definidos
    qtd_multi = AtendimentoMultidisciplinar.objects.filter(paciente=paciente).count()
    # qtd_medico = AtendimentoMedico.objects.filter(paciente=paciente).count() # (Descomente quando criar o model Médico)
    qtd_medico = 0  # Placeholder enquanto não cria o médico

    # 2. Integração API Laboratório
    exames_lista = []
    erro_api = None

    # Limpa CPF (remove pontos e traços)
    cpf_limpo = paciente.cpf.replace('.', '').replace('-', '')

    url_api = f"http://172.15.0.152:5897/api/laboratorio/{cpf_limpo}"

    try:
        # Tenta conectar com timeout de 5 segundos para não travar o sistema
        response = requests.get(url_api, timeout=5)

        if response.status_code == 200:
            dados_brutos = response.json()

            # Itera sobre a lista de exames retornada
            for item in dados_brutos:
                # O item deve ser uma lista onde item[2] é data, item[5] exame, item[7] status

                # A. Tratamento da Data (Linha 2)
                try:
                    raw_timestamp = item[2]  # "2025-01-13T14:30:00.000Z"
                    data_part, hora_part = raw_timestamp.split('T')
                    hora_part = hora_part.split('.')[0]  # Remove milissegundos

                    # Conversão GMT para GMT-3 (Subtrair 3 horas)
                    dt_obj = datetime.strptime(f"{data_part} {hora_part}", "%Y-%m-%d %H:%M:%S")
                    dt_local = dt_obj - timedelta(hours=3)

                    data_final = dt_local.strftime("%d/%m/%Y")
                    hora_final = dt_local.strftime("%H:%M")
                except:
                    data_final = "--/--/----"
                    hora_final = "--:--"

                # B. Tratamento do Status (Linha 7)
                status_raw = item[7]
                status_cor = "bg-success" if status_raw == "LIBERADO" else "bg-danger"

                # Monta o objeto para o template
                exame = {
                    'data': data_final,
                    'hora': hora_final,
                    'nome_exame': item[5],  # Linha 5
                    'status_texto': status_raw,
                    'status_cor': status_cor
                }
                exames_lista.append(exame)
        else:
            erro_api = f"API retornou status {response.status_code}"

    except requests.exceptions.RequestException:
        erro_api = "Sistema de Laboratório indisponível (Erro de Conexão)"
    except Exception as e:
        erro_api = f"Erro ao processar dados: {str(e)}"

    context = {
        'paciente': paciente,
        'qtd_multi': qtd_multi,
        'qtd_medico': qtd_medico,
        'exames': exames_lista,
        'erro_api': erro_api
    }
    return render(request, 'monitoramento_painel.html', context)


def prescricao_medica(request, atendimento_id):
    atendimento = get_object_or_404(AtendimentoMedico, id=atendimento_id)
    medicamentos_db = Medicamento.objects.all()  # Otimizar com .values() para JSON no front

    if request.method == 'POST':
        # Cria a prescrição vinculada ao atendimento
        prescricao = Prescricao.objects.create(
            atendimento=atendimento,
            observacoes_gerais=request.POST.get('observacoes_gerais')
        )

        # O front-end enviará os itens como um JSON stringificado
        itens_json = request.POST.get('itens_prescricao_json')
        if itens_json:
            lista_itens = json.loads(itens_json)
            for item in lista_itens:
                med_obj = Medicamento.objects.get(id=item['id_medicamento'])
                ItemPrescricao.objects.create(
                    prescricao=prescricao,
                    medicamento=med_obj,
                    posologia=item['posologia'],
                    quantidade=item['quantidade'],
                    uso_continuo=item.get('uso_continuo', False)
                )

        return redirect('visualizar_impressao_receita', prescricao_id=prescricao.id)

    context = {
        'atendimento': atendimento,
        'paciente': atendimento.paciente,
        'medicamentos': medicamentos_db
    }
    return render(request, 'atendimento/prescricao_form.html', context)


def visualizar_impressao_receita(request, prescricao_id):
    """
    Separa os itens em listas distintas para gerar PDFs separados se necessário.
    """
    prescricao = get_object_or_404(Prescricao, id=prescricao_id)
    itens = prescricao.itens.all()

    receita_simples = []
    receita_controle = []

    for item in itens:
        if item.medicamento.tipo_receita == 'SIMPLES':
            receita_simples.append(item)
        else:
            receita_controle.append(item)

    context = {
        'prescricao': prescricao,
        'paciente': prescricao.atendimento.paciente,
        'receita_simples': receita_simples,
        'receita_controle': receita_controle,
        'hoje': timezone.now()
    }
    return render(request, 'atendimento/impressao_receita.html', context)