from django.core.management.base import BaseCommand
from core.models import Usuario, Medicamento


class Command(BaseCommand):
    help = 'Configura farmácia com milhagens reais das REMUMEs de Caraguá, São Sebastião, Ilhabela, Ubatuba e Paraibuna'

    def handle(self, *args, **kwargs):
        # ---------------------------------------------------------
        # 1. Manutenção do Usuário Admin
        # ---------------------------------------------------------
        email_admin = 'saulo.bastos@amecaragua.org.br'
        if not Usuario.objects.filter(email=email_admin).exists():
            Usuario.objects.create_superuser(
                username=email_admin,
                email=email_admin,
                password='admin',
                drt='00000000',
                mudar_senha=True
            )
            self.stdout.write(self.style.SUCCESS(f'Admin configurado: {email_admin}'))

        # ---------------------------------------------------------
        # 2. Consolidação das REMUMEs Regionais (Litoral Norte/Paraibuna)
        # ---------------------------------------------------------
        # Formato: (Classe, Princípio Ativo, Dosagem Específica, Nomes Comerciais)
        meds_remume = [
            # --- INIBIDORES DA ECA (IECA) ---
            ('IECA', 'Captopril', '25mg', 'Capoten'),  # [cite: 2168, 2691, 3042, 3080]
            ('IECA', 'Enalapril, Maleato', '10mg', 'Renitec'),  # [cite: 2689, 3048]
            ('IECA', 'Enalapril, Maleato', '20mg', 'Renitec'),  # [cite: 2690, 3048, 3080, 3270]

            # --- BLOQUEADORES DO RECEPTOR DE ANGIOTENSINA (BRA) ---
            ('BRA', 'Losartana Potássica', '50mg', 'Aradois, Cozaar'),  # [cite: 2168, 3047, 3080]

            # --- BLOQUEADORES DE CANAIS DE CÁLCIO (BCC) ---
            ('BCC', 'Anlodipino, Besilato', '5mg', 'Norvasc, Pressat'),  # [cite: 2168, 2667, 3042, 3075, 3225]
            ('BCC', 'Anlodipino, Besilato', '10mg', 'Norvasc'),  # [cite: 2168, 2668, 3042]
            ('BCC', 'Nifedipino', '20mg', 'Adalat Retard'),  # [cite: 2168, 2638, 2664, 3048, 3080, 3309]
            ('BCC', 'Diltiazem, Cloridrato', '30mg', 'Cardizem'),  # [cite: 2663, 3046, 3080, 3261]
            ('BCC', 'Diltiazem, Cloridrato', '60mg', 'Cardizem'),  # [cite: 3080]
            ('BCC', 'Verapamil, Cloridrato', '80mg', 'Dilacoron'),  # [cite: 2705, 3080]

            # --- BETABLOQUEADORES ---
            ('Betabloqueador', 'Atenolol', '50mg', 'Atenol'),  # [cite: 2168, 2652, 2698, 3042, 3075, 3225]
            ('Betabloqueador', 'Atenolol', '100mg', 'Atenol'),  # [cite: 2168, 2653, 2699]
            ('Betabloqueador', 'Carvedilol', '3,125mg', 'Coreg'),  # [cite: 2168, 3043]
            ('Betabloqueador', 'Carvedilol', '6,25mg', 'Coreg'),  # [cite: 2168, 2659, 3043, 3080, 3234]
            ('Betabloqueador', 'Carvedilol', '12,5mg', 'Coreg'),  # [cite: 2168, 3043, 3234]
            ('Betabloqueador', 'Carvedilol', '25mg', 'Coreg'),  # [cite: 2168, 2660, 3043, 3080]
            ('Betabloqueador', 'Propranolol, Cloridrato', '40mg', 'Inderal'),  # [cite: 2168, 2636, 2657, 3044, 3080]
            ('Betabloqueador', 'Metoprolol, Succinato', '25mg', 'Selozok'),  # [cite: 3080]
            ('Betabloqueador', 'Metoprolol, Succinato', '50mg', 'Selozok'),  # [cite: 3309]

            # --- DIURÉTICOS ---
            ('Diurético Tiazídico', 'Hidroclorotiazida', '25mg', 'Clorana'),  # [cite: 2168, 2677, 2711, 3046, 3098]
            ('Diurético de Alça', 'Furosemida', '40mg', 'Lasix'),  # [cite: 2168, 2674, 2708, 3046, 3098, 3279]
            ('Diurético Poupador de K+', 'Espironolactona', '25mg', 'Aldactone'),
            # [cite: 2168, 2672, 3045, 3098, 3270]
            ('Betabloqueador', 'Espironolactona', '100mg', 'Aldactone'),  # [cite: 2671, 3045, 3270]

            # --- SIMPATICOLÍTICOS DE AÇÃO CENTRAL ---
            ('Agonista Central', 'Metildopa', '250mg', 'Aldomet'),  # [cite: 2168, 2655, 3048, 3080, 3309]

            # --- VASODILATADORES DIRETOS ---
            ('Vasodilatador Direto', 'Hidralazina, Cloridrato', '25mg', 'Apresolina'),  # [cite: 3044]

            # --- DISLIPIDEMIA (ESTATINAS) ---
            ('Hipolipemiante', 'Sinvastatina', '10mg', 'Zocor'),  # [cite: 2807, 3050]
            ('Hipolipemiante', 'Sinvastatina', '20mg', 'Zocor'),  # [cite: 2174, 2808, 3050, 3098, 3339]
            ('Hipolipemiante', 'Sinvastatina', '40mg', 'Zocor'),  # [cite: 2809]
        ]

        # ---------------------------------------------------------
        # 3. Execução da Carga (Update or Create)
        # ---------------------------------------------------------
        self.stdout.write('Sincronizando medicamentos com REMUMEs regionais...')

        count = 0
        for classe, principio, dose, nomes in meds_remume:
            # Concatenamos a dose ao princípio ativo para o Autocomplete do Prontuário
            nome_exibicao = f"{principio} {dose}"

            Medicamento.objects.update_or_create(
                principio_ativo=nome_exibicao,
                defaults={
                    'classe': classe,
                    'dose_padrao': dose,
                    'nomes_comerciais': nomes,
                    'ativo': True
                }
            )
            count += 1

        self.stdout.write(
            self.style.SUCCESS(f'Concluído! {count} apresentações da REMUME Regional foram configuradas.'))