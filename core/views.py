import os
import base64  # <--- ADICIONE ESTA LINHA AQUI
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
from datetime import datetime, date
from .models import Paciente, Afericao, Medicamento, Usuario
from .forms import PacienteForm, UsuarioForm


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

# --- Gestão de Usuários e Medicamentos ---
# (Implementação simplificada seguindo a mesma lógica das views acima)
@login_required
def gestao_usuarios(request):
    usuarios = Usuario.objects.all()
    return render(request, 'gestao_usuarios.html', {'usuarios': usuarios})


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