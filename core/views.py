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
from django.forms import inlineformset_factory  # Faltava este import
from operator import attrgetter # Para ordenar listas combinadas

# Imports dos Models e Forms
from .models import (
    Paciente, Medicamento, Afericao, Usuario, AtendimentoMultidisciplinar,
    AvaliacaoPrevent, AtendimentoMedico, TriagemHipertensao, PrescricaoMedica, ItemPrescricao
)
from .forms import (
    PacienteForm, UsuarioForm, AtendimentoMedicoForm, TriagemHASForm
)

# IMPORTE CORRETO DOS DECORADORES DE SEGURANÇA
from .decorators import admin_only, multi_only, medico_only, health_team


# --- Funções Auxiliares ---

def calcular_idade(nascimento):
    if not nascimento: return 0
    hoje = date.today()
    return hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))


def get_base64_image(filename):
    path = os.path.join(settings.BASE_DIR, 'core', 'static', 'img', filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"ERRO B64: {e}")
        return None


# --- Autenticação ---

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
            update_session_auth_hash(request, request.user)
            messages.success(request, 'Senha alterada com sucesso!')
            return redirect('index')
        else:
            messages.error(request, 'Senhas não conferem ou muito curtas.')
    return render(request, 'trocar_senha.html')


@login_required
def index(request):
    if request.user.mudar_senha: return redirect('trocar_senha')
    return render(request, 'index.html')


# --- Dashboard (APENAS ADMIN) ---

@login_required
@admin_only  # <--- Proteção
def dashboard_clinico(request):
    municipios = Paciente.objects.values_list('municipio', flat=True).distinct().order_by('municipio')
    # Atenção: Renomeamos indices.html para dashboard.html
    return render(request, 'dashboard.html', {'municipios': municipios})


@login_required
@admin_only  # <--- Proteção
def api_dashboard(request):
    cidades_selecionadas = request.GET.getlist('municipios[]')
    pacientes = Paciente.objects.filter(ativo=True)

    if cidades_selecionadas:
        pacientes = pacientes.filter(municipio__in=cidades_selecionadas)

    total_pacientes = pacientes.count()
    hoje = datetime.now()
    total_afericoes = Afericao.objects.filter(
        data_afericao__month=hoje.month,
        data_afericao__year=hoje.year,
        paciente__in=pacientes
    ).count()

    controlados = 0
    nao_controlados = 0
    sem_dados = 0

    for p in pacientes:
        ultima = p.afericoes.first()
        if not ultima:
            sem_dados += 1
        elif ultima.pressao_sistolica < 140 and ultima.pressao_diastolica < 90:
            controlados += 1
        else:
            nao_controlados += 1

    sexo_stats = pacientes.values('sexo').annotate(total=Count('sexo'))
    sexo_data = {'M': 0, 'F': 0}
    for item in sexo_stats:
        sexo_data[item['sexo']] = item['total']

    mun_stats = pacientes.values('municipio').annotate(total=Count('municipio')).order_by('-total')
    mun_labels = [m['municipio'] for m in mun_stats]
    mun_data = [m['total'] for m in mun_stats]

    faixas_etarias = {'<40': 0, '40-59': 0, '60-79': 0, '80+': 0}
    soma_dias_lc = 0
    data_atual = date.today()

    for p in pacientes:
        idade = calcular_idade(p.data_nascimento)
        if idade < 40:
            faixas_etarias['<40'] += 1
        elif idade < 60:
            faixas_etarias['40-59'] += 1
        elif idade < 80:
            faixas_etarias['60-79'] += 1
        else:
            faixas_etarias['80+'] += 1

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


@login_required
@health_team
def gestao_pacientes(request):
    termo = request.GET.get('busca')

    if termo:
        # Filtra por Nome, CPF ou SIRESP (CROSS)
        pacientes = Paciente.objects.filter(
            Q(nome__icontains=termo) |
            Q(cpf__icontains=termo) |
            Q(siresp__icontains=termo)  # <--- Adicionado busca por CROSS
        ).order_by('nome')
    else:
        pacientes = Paciente.objects.all().order_by('nome')

    return render(request, 'pacientes.html', {'pacientes': pacientes})


@login_required
@multi_only
def salvar_paciente(request):
    if request.method == 'POST':
        pid = request.POST.get('paciente_id')
        data = request.POST.copy()
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
@multi_only
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


# --- Prontuário / Atendimento (TODOS) ---

@login_required
def atendimento_hub(request):
    # Acesso liberado para todos os logados (Médicos, Multi, Admin)
    paciente = None
    erro = None
    if request.method == 'POST':
        termo = request.POST.get('busca_termo')
        pacientes = Paciente.objects.filter(cpf=termo) | Paciente.objects.filter(nome__icontains=termo)
        if pacientes.exists():
            paciente = pacientes.first()
        else:
            erro = "Paciente não encontrado."
    return render(request, 'atendimento_hub.html', {'paciente': paciente, 'erro': erro})


@login_required
def atendimento_multidisciplinar(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    idade = calcular_idade(paciente.data_nascimento)
    ultima_afericao = paciente.afericoes.first()

    if request.method == 'POST':
        peso = request.POST.get('peso').replace(',', '.')
        altura = request.POST.get('altura').replace(',', '.')
        circunf = request.POST.get('circunf').replace(',', '.')

        tem_diabetes = True if request.POST.get('diabetes') == 'on' else False
        fumante = True if request.POST.get('fumante') == 'on' else False

        loa_coracao = True if request.POST.get('loa_coracao') == 'on' else False
        loa_cerebro = True if request.POST.get('loa_cerebro') == 'on' else False
        loa_rins = True if request.POST.get('loa_rins') == 'on' else False
        loa_arterias = True if request.POST.get('loa_arterias') == 'on' else False
        loa_olhos = True if request.POST.get('loa_olhos') == 'on' else False
        tem_loa = any(
            [loa_coracao, loa_cerebro, loa_rins, loa_arterias, loa_olhos, request.POST.get('tem_loa') == 'on'])

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

        eligible = False
        if not ultima_afericao:
            eligible = True
        else:
            pas = ultima_afericao.pressao_sistolica
            pad = ultima_afericao.pressao_diastolica
            is_estagio_2_plus = (pas >= 140) or (pad >= 90)
            is_estagio_1 = (130 <= pas < 140) or (80 <= pad < 90)
            has_alto_risco = tem_diabetes or tem_loa or loa_rins

            if is_estagio_2_plus or (is_estagio_1 and has_alto_risco):
                eligible = True

        if eligible:
            messages.success(request, "Paciente ELEGÍVEL. Gerando Kit de Exames...")
            return redirect('gerar_kit_exames', paciente_id=paciente.id)
        else:
            return redirect('gerar_contrarreferencia_triagem', paciente_id=paciente.id)

    return render(request, 'atendimento/ficha_enf_aval_inicial.html', {'paciente': paciente, 'idade': idade})


@login_required
def atendimento_prevent(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    idade = calcular_idade(paciente.data_nascimento)
    ultimo_multi = paciente.atendimentos_multi.last()
    ultima_afericao = paciente.afericoes.order_by('-data_afericao').first()

    if request.method == 'POST':
        try:
            AvaliacaoPrevent.objects.create(
                paciente=paciente,
                idade=idade,
                sexo=paciente.sexo,
                colesterol_total=request.POST.get('col_total'),
                hdl=request.POST.get('hdl'),
                pressao_sistolica=request.POST.get('pas'),
                tfg=request.POST.get('tfg').replace(',', '.'),
                em_tratamento_has=True if request.POST.get('em_tto') == 'on' else False,
                tem_diabetes=True if request.POST.get('diabetes') == 'on' else False,
                fumante=True if request.POST.get('fumante') == 'on' else False,
                risco_10_anos=request.POST.get('risco_10').replace(',', '.'),
                risco_30_anos=request.POST.get('risco_30').replace(',', '.')
            )
            return redirect('atendimento_hub')
        except Exception as e:
            print(f"Erro: {e}")

    context = {
        'paciente': paciente,
        'idade': idade,
        'pre_diabetes': ultimo_multi.tem_diabetes if ultimo_multi else False,
        'pre_fumante': ultimo_multi.fumante if ultimo_multi else False,
        'pre_pas': ultima_afericao.pressao_sistolica if ultima_afericao else ''
    }
    return render(request, 'atendimento_prevent.html', context)

@login_required
def realizar_atendimento_medico(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)

    # 1. Busca o último Score PREVENT
    ultima_avaliacao = AvaliacaoPrevent.objects.filter(paciente=paciente).order_by('-data_avaliacao').first()
    score_valor = float(ultima_avaliacao.risco_10_anos) if ultima_avaliacao else 0.0

    if request.method == 'POST':
        form = AtendimentoMedicoForm(request.POST)
        if form.is_valid():
            atendimento = form.save(commit=False)
            atendimento.paciente = paciente
            atendimento.medico = request.user
            atendimento.score_prevent_valor = score_valor
            atendimento.save()

            # --- LÓGICA DE NAVEGAÇÃO DOS BOTÕES ---
            action = request.POST.get('action')

            if action == 'prescricao':
                return redirect('prescricao_medica', atendimento_id=atendimento.id)

            elif action == 'exames':
                return redirect('solicitar_exames', atendimento_id=atendimento.id)

            elif action == 'alta':
                # Redireciona para gerar a alta e o PDF
                return redirect('gerar_alta', id=paciente.id)

            elif action == 'salvar':
                # Salva e mantém na página (recarrega para mostrar feedback)
                messages.success(request, "Atendimento salvo com sucesso.")
                return redirect('atendimento_medico', paciente_id=paciente.id)

    else:
        form = AtendimentoMedicoForm()

    # Definição de Cores de Risco
    if score_valor < 5:
        classe_risco, texto_risco = "bg-success text-white", "Risco Baixo"
    elif 5 <= score_valor < 7.5:
        classe_risco, texto_risco = "bg-warning text-dark", "Risco Limítrofe"
    elif 7.5 <= score_valor < 20:
        classe_risco, texto_risco = "bg-orange text-white", "Risco Intermediário"
    else:
        classe_risco, texto_risco = "bg-danger text-white", "Alto Risco"

    context = {
        'paciente': paciente,
        'form': form,
        'prevent_score': score_valor,
        'risco_css': classe_risco,
        'risco_texto': texto_risco
    }
    return render(request, 'atendimento/ficha_medica.html', context)


@login_required
def solicitar_exames(request, atendimento_id):
    """
    View placeholder para a tela de solicitação de exames.
    Será implementada completamente no próximo passo.
    """
    atendimento = get_object_or_404(AtendimentoMedico, id=atendimento_id)

    # Renderiza um template vazio ou provisório para não dar erro 404
    # Vamos criar este arquivo vazio agora para garantir o fluxo
    return render(request, 'atendimento/req_exames.html', {
        'atendimento': atendimento,
        'paciente': atendimento.paciente
    })

@login_required
def prescricao_medica_view(request, atendimento_id):
    atendimento = get_object_or_404(AtendimentoMedico, id=atendimento_id)
    prescricao, created = PrescricaoMedica.objects.get_or_create(atendimento=atendimento)

    if request.method == 'POST':
        # 1. ADICIONAR ITEM (Lógica isolada)
        if 'adicionar_item' in request.POST:
            med_id = request.POST.get('medicamento_id')
            if med_id:
                medicamento = get_object_or_404(Medicamento, id=med_id)
                ItemPrescricao.objects.create(
                    prescricao=prescricao,
                    medicamento_nome=medicamento.principio_ativo,
                    concentracao=medicamento.dose_padrao,
                    posologia=request.POST.get('posologia'),
                    quantidade=request.POST.get('quantidade'),
                    tipo=request.POST.get('tipo_uso')
                )
                messages.success(request, "Medicamento adicionado.")
            return redirect('prescricao_medica', atendimento_id=atendimento.id)

        # 2. REMOVER ITEM (Lógica isolada)
        elif 'remover_item' in request.POST:
            ItemPrescricao.objects.filter(id=request.POST.get('item_id')).delete()
            return redirect('prescricao_medica', atendimento_id=atendimento.id)

        # 3. BARRA DE NAVEGAÇÃO (Ações Gerais)
        else:
            action = request.POST.get('action')

            # Salva sempre as observações ao clicar em qualquer botão da barra
            prescricao.observacoes_gerais = request.POST.get('observacoes')
            prescricao.save()

            if action == 'imprimir':
                return gerar_receita_pdf_bytes(request, prescricao)

            elif action == 'salvar':
                messages.success(request, "Prescrição salva com sucesso.")
                return redirect('prescricao_medica', atendimento_id=atendimento.id)

            elif action == 'exames':
                return redirect('solicitar_exames', atendimento_id=atendimento.id)

            elif action == 'alta':
                return redirect('gerar_alta', id=atendimento.paciente.id)

            elif action == 'voltar':
                return redirect('atendimento_medico', paciente_id=atendimento.paciente.id)

    # Preparação do Autocomplete (DCB)
    medicamentos_all = Medicamento.objects.filter(ativo=True)
    lista_autocomplete = []
    for med in medicamentos_all:
        lista_autocomplete.append({
            'id': med.id,
            'label': f"{med.principio_ativo} {med.dose_padrao} (Genérico)",
            'dose': med.dose_padrao,
            'tipo': 'DCB'
        })
        if med.nomes_comerciais:
            nomes = [n.strip() for n in med.nomes_comerciais.split(',')]
            for nome in nomes:
                if nome:
                    lista_autocomplete.append({
                        'id': med.id,
                        'label': f"{nome} -> {med.principio_ativo}",
                        'dose': med.dose_padrao,
                        'tipo': 'COMERCIAL'
                    })

    lista_autocomplete.sort(key=lambda x: x['label'])

    context = {
        'atendimento': atendimento,
        'paciente': atendimento.paciente,
        'prescricao': prescricao,
        'itens': prescricao.itens.all(),
        'db_medicamentos': json.dumps(lista_autocomplete)
    }
    return render(request, 'prescricao_form.html', context)


# --- NOVA FUNÇÃO AUXILIAR DE PDF ---
def gerar_receita_pdf_bytes(request, prescricao):
    """Gera o PDF da receita e retorna como HttpResponse"""
    paciente = prescricao.atendimento.paciente
    idade = calcular_idade(paciente.data_nascimento)

    # Separa itens por tipo para o layout
    itens_comuns = prescricao.itens.filter(tipo='CONTINUO') | prescricao.itens.filter(tipo='TEMPORARIO')
    itens_controlados = prescricao.itens.filter(tipo='CONTROLADO')

    context = {
        'paciente': paciente,
        'idade': idade,
        'usuario': request.user,
        'data_hoje': datetime.now(),
        'header_b64': get_base64_image('header.png'),
        'itens_comuns': itens_comuns,
        'itens_controlados': itens_controlados,
        'observacoes': prescricao.observacoes_gerais
    }

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="receita_{paciente.nome}.pdf"'  # 'inline' abre no navegador

    template = get_template('pdf_receita.html')
    html = template.render(context)

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse('Erro ao gerar PDF')

    return response
# --- Monitoramento (MULTI + ADMIN) ---

@login_required
@multi_only
def monitoramento_busca(request):
    erro = None
    if request.method == 'POST':
        termo = request.POST.get('busca_termo')
        pacientes = Paciente.objects.filter(nome__icontains=termo) | Paciente.objects.filter(
            cpf=termo) | Paciente.objects.filter(siresp=termo)
        if pacientes.exists():
            return redirect('monitoramento_painel', paciente_id=pacientes.first().id)
        else:
            erro = "Paciente não encontrado."
    return render(request, 'monitoramento_busca.html', {'erro': erro})


@login_required
@multi_only
def monitoramento_painel(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    qtd_multi = AtendimentoMultidisciplinar.objects.filter(paciente=paciente).count()
    qtd_medico = AtendimentoMedico.objects.filter(paciente=paciente).count()

    exames_lista = []
    erro_api = None
    cpf_limpo = paciente.cpf.replace('.', '').replace('-', '')
    url_api = f"http://172.15.0.152:5897/api/laboratorio/{cpf_limpo}"

    try:
        response = requests.get(url_api, timeout=5)
        if response.status_code == 200:
            dados_brutos = response.json()
            for item in dados_brutos:
                try:
                    data_part = item[2].split('T')[0]
                    status_cor = "bg-success" if item[7] == "LIBERADO" else "bg-danger"
                    exames_lista.append({
                        'data': data_part,
                        'nome_exame': item[5],
                        'status_texto': item[7],
                        'status_cor': status_cor
                    })
                except:
                    pass
        else:
            erro_api = f"Status API: {response.status_code}"
    except:
        erro_api = "API Indisponível"

    return render(request, 'monitoramento_painel.html', {
        'paciente': paciente,
        'qtd_multi': qtd_multi,
        'qtd_medico': qtd_medico,
        'exames': exames_lista,
        'erro_api': erro_api
    })


# --- Gestão Admin (APENAS ADMIN) ---

@login_required
@admin_only
def gestao_usuarios(request):
    if request.method == 'POST':
        # Verifica se veio um ID para edição
        usuario_id = request.POST.get('usuario_id')
        instance = None

        if usuario_id:
            instance = get_object_or_404(Usuario, id=usuario_id)

        # Passa a instância para o form se for edição
        form = UsuarioForm(request.POST, instance=instance)

        if form.is_valid():
            try:
                form.save()
                msg = "Usuário atualizado!" if usuario_id else "Usuário cadastrado!"
                messages.success(request, msg)
                return redirect('gestao_usuarios')
            except Exception as e:
                messages.error(request, f"Erro ao salvar: {e}")
        else:
            for f, err in form.errors.items():
                messages.error(request, f"{f}: {err}")

    users = Usuario.objects.all().order_by('first_name')
    return render(request, 'gestao_usuarios.html', {'users': users})


@login_required
@admin_only
def salvar_usuario(request):
    # Esta view pode ser removida se o form acima já faz o trabalho,
    # ou mantida para edição via AJAX/Modal específico.
    # Mantendo compatibilidade com seu template:
    return redirect('gestao_usuarios')


@login_required
@admin_only
def api_usuario(request, id):
    u = get_object_or_404(Usuario, id=id)
    # Retorna o JSON completo para preencher o Modal de Edição
    return JsonResponse({
        'id': u.id,
        'first_name': u.first_name,
        'last_name': u.last_name,
        'username': u.username,
        'email': u.email,
        'drt': u.drt or "",
        'tipo_profissional': u.tipo_profissional or "",
        'tipo_registro': u.tipo_registro or "",
        'registro_profissional': u.registro_profissional or "",
        'is_active': u.is_active,
        'mudar_senha': u.mudar_senha
    })


@login_required
@admin_only
def gestao_medicamentos(request):
    medicamentos = Medicamento.objects.all().order_by('classe', 'principio_ativo')
    classes = Medicamento.objects.values_list('classe', flat=True).distinct().order_by('classe')
    return render(request, 'gestao_medicamentos.html', {'medicamentos': medicamentos, 'classes_disponiveis': classes})


@login_required
@admin_only
def salvar_medicamento(request):
    if request.method == 'POST':
        med_id = request.POST.get('medicamento_id')
        if med_id:
            m = get_object_or_404(Medicamento, id=med_id)
        else:
            m = Medicamento()
        m.classe = request.POST.get('classe')
        m.principio_ativo = request.POST.get('principio_ativo')
        m.dose_padrao = request.POST.get('dose_padrao')
        m.nomes_comerciais = request.POST.get('nomes_comerciais')
        m.ativo = True if request.POST.get('ativo') else False
        m.save()
        messages.success(request, 'Medicamento salvo!')
    return redirect('gestao_medicamentos')


# --- PDFs (Gerais) ---

@login_required
def gerar_kit_exames(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="kit_{paciente.nome}.pdf"'
    html = get_template('pdf_kit_exames.html').render({
        'paciente': paciente,
        'header_b64': get_base64_image('header.png'),
        'usuario': request.user,
        'idade': calcular_idade(paciente.data_nascimento),
        'data_hoje': date.today()
    })
    pisa.CreatePDF(html, dest=response)
    return response


@login_required
def gerar_contrarreferencia_triagem(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="contra_{paciente.nome}.pdf"'
    html = get_template('pdf_contrarreferencia_triagem.html').render({
        'paciente': paciente,
        'header_b64': get_base64_image('header.png'),
        'footer_b64': get_base64_image('footer.png'),
        'usuario': request.user,
        'hoje': date.today()
    })
    pisa.CreatePDF(html, dest=response)
    return response


@login_required
def gerar_alta(request, id):
    paciente = get_object_or_404(Paciente, id=id)
    paciente.ativo = False
    paciente.data_alta = date.today()
    paciente.save()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="alta_{paciente.nome}.pdf"'
    html = get_template('pdf_alta.html').render({
        'paciente': paciente,
        'header_b64': get_base64_image('header.png'),
        'footer_b64': get_base64_image('footer.png'),
        'usuario': request.user,
        'hoje': date.today()
    })
    pisa.CreatePDF(html, dest=response)
    return response


@login_required
def gerar_pedido_exames(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="pedidos_{paciente.nome}.pdf"'
    html = get_template('pdf_pedidos_exames.html').render({
        'paciente': paciente,
        'header_b64': get_base64_image('header.png'),
        'usuario': request.user,
        'idade': calcular_idade(paciente.data_nascimento),
        'data_hoje': date.today()
    })
    pisa.CreatePDF(html, dest=response)
    return response

@login_required
def reimprimir_receita(request, prescricao_id):
    prescricao = get_object_or_404(PrescricaoMedica, id=prescricao_id)
    return gerar_receita_pdf_bytes(request, prescricao)

@login_required
def detalhe_paciente(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)

    # --- 1. DADOS PARA O GRÁFICO DE PA (Evolução) ---
    # Pegamos todas as aferições ordenadas cronologicamente
    afericoes = Afericao.objects.filter(paciente=paciente).order_by('data_afericao')

    grafico_labels = []
    grafico_pas = []
    grafico_pad = []
    grafico_pam = []  # Pressão Arterial Média

    for a in afericoes:
        # Formata data para o gráfico
        grafico_labels.append(a.data_afericao.strftime("%d/%m/%Y"))

        # Valores
        pas = a.pressao_sistolica
        pad = a.pressao_diastolica

        # Cálculo da PAM: (PAS + 2*PAD) / 3
        pam = round((pas + (2 * pad)) / 3, 1)

        grafico_pas.append(pas)
        grafico_pad.append(pad)
        grafico_pam.append(pam)

    # --- 2. HISTÓRICO DE CONSULTAS (Linha do Tempo) ---
    atendimentos_med = AtendimentoMedico.objects.filter(paciente=paciente)
    atendimentos_multi = AtendimentoMultidisciplinar.objects.filter(paciente=paciente)

    # Unifica as listas e ordena por data decrescente
    # Adicionamos um atributo 'tipo_atendimento' dinamicamente para usar no template
    historico_consultas = []

    for a in atendimentos_med:
        a.tipo_visual = 'MÉDICO'
        a.profissional_nome = a.medico.get_full_name() if a.medico else 'Médico'
        a.data_ref = a.data_atendimento
        historico_consultas.append(a)

    for a in atendimentos_multi:
        a.tipo_visual = 'MULTIDISCIPLINAR'
        a.profissional_nome = a.profissional.get_full_name() if a.profissional else 'Equipe Multi'
        a.data_ref = a.data_atendimento
        historico_consultas.append(a)

    # Ordena: Mais recente primeiro
    historico_consultas.sort(key=lambda x: x.data_ref, reverse=True)

    # --- 3. ESQUEMAS TERAPÊUTICOS (Prescrições Anteriores) ---
    # Busca prescrições ordenadas da mais recente para a mais antiga
    prescricoes = PrescricaoMedica.objects.filter(atendimento__paciente=paciente).order_by('-data_prescricao')

    context = {
        'paciente': paciente,
        'grafico_labels': json.dumps(grafico_labels),
        'grafico_pas': json.dumps(grafico_pas),
        'grafico_pad': json.dumps(grafico_pad),
        'grafico_pam': json.dumps(grafico_pam),
        'historico_consultas': historico_consultas,
        'prescricoes': prescricoes
    }

    return render(request, 'detalhe_paciente.html', context)