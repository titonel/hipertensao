from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from datetime import datetime, date
from .models import Paciente, Afericao, Medicamento, Usuario
from .forms import PacienteForm, UsuarioForm


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
def api_dashboard(request):
    total_pacientes = Paciente.objects.filter(ativo=True).count()
    hoje = datetime.now()
    total_afericoes = Afericao.objects.filter(data_afericao__month=hoje.month, data_afericao__year=hoje.year).count()

    # Lógica simplificada para o gráfico
    controlados = 0
    nao_controlados = 0
    sem_dados = 0
    for p in Paciente.objects.filter(ativo=True):
        ultima = p.afericoes.first()
        if not ultima:
            sem_dados += 1
        elif ultima.pressao_sistolica < 140 and ultima.pressao_diastolica < 90:
            controlados += 1
        else:
            nao_controlados += 1

    return JsonResponse({
        'kpi_pacientes': total_pacientes,
        'kpi_afericoes': total_afericoes,
        'controle_pa': [controlados, nao_controlados, sem_dados],
        'grafico_meds': {'labels': [], 'data': []}  # Implementar contagem se necessário
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

    # Agrupamento de medicamentos
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
        historico = paciente.afericoes.all()[:10]

    return render(request, 'atendimento.html', {
        'paciente': paciente,
        'historico': historico,
        'meds_agrupados': meds_agrupados,
        'ordem_classes': ordem_classes
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