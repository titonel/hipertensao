from django.core.management.base import BaseCommand
from core.models import Usuario, Medicamento


class Command(BaseCommand):
    help = 'Configura admin e carrega a lista completa de medicamentos (DBH 2025)'

    def handle(self, *args, **kwargs):
        # ---------------------------------------------------------
        # 1. Configuração do Admin
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
            self.stdout.write(self.style.SUCCESS(f'Admin criado: {email_admin}'))
        else:
            self.stdout.write(self.style.WARNING('Admin já existe.'))

        # ---------------------------------------------------------
        # 2. Farmacopeia Completa - DBH 2025
        # ---------------------------------------------------------
        # Formato: (Classe, Princípio Ativo, Dose Habitual (mg/dia), Nomes de Referência)

        meds_completo = [
            # --- DIURÉTICOS TIAZÍDICOS E ANÁLOGOS ---
            ('Diurético Tiazídico/Símil', 'Hidroclorotiazida', '12,5-50mg', 'Clorana'),
            ('Diurético Tiazídico/Símil', 'Clortalidona', '12,5-25mg', 'Higroton'),
            ('Diurético Tiazídico/Símil', 'Indapamida', '1,5-2,5mg', 'Natrilix SR, Fludex'),

            # --- DIURÉTICOS DE ALÇA ---
            ('Diurético de Alça', 'Furosemida', '20-320mg', 'Lasix'),  # Dose varia muito (Edema vs HAS)
            ('Diurético de Alça', 'Bumetanida', '0,5-5mg', 'Burinax'),
            ('Diurético de Alça', 'Piretanida', '6-12mg', 'Arelix'),

            # --- DIURÉTICOS POUPADORES DE POTÁSSIO / ANTAGONISTAS MINERALOCORTICOIDES ---
            ('Diurético Poupador de K+', 'Espironolactona', '25-100mg', 'Aldactone, Diactone'),
            ('Diurético Poupador de K+', 'Amilorida', '2,5-20mg', 'Moduretic (assoc.)'),
            ('Diurético Poupador de K+', 'Triantereno', '50-100mg', 'Diurana (assoc.)'),
            ('Diurético Poupador de K+', 'Eplerenona', '25-50mg', 'Inspra'),  # Uso específico

            # --- INIBIDORES DA ECA (IECA) ---
            ('IECA', 'Captopril', '50-150mg', 'Capoten'),
            ('IECA', 'Enalapril', '10-40mg', 'Renitec, Eupressin'),
            ('IECA', 'Lisinopril', '10-40mg', 'Zestril, Prinivil'),
            ('IECA', 'Ramipril', '2,5-20mg', 'Triatec'),
            ('IECA', 'Perindopril', '4-16mg', 'Coversyl'),
            ('IECA', 'Trandolapril', '2-4mg', 'Gopten'),
            ('IECA', 'Benazepril', '10-40mg', 'Lotensin'),
            ('IECA', 'Cilazapril', '2,5-5mg', 'Vascase'),
            ('IECA', 'Fosinopril', '10-40mg', 'Monopril'),

            # --- BLOQUEADORES DO RECEPTOR DE ANGIOTENSINA (BRA) ---
            ('BRA', 'Losartana Potássica', '50-100mg', 'Aradois, Cozaar'),
            ('BRA', 'Valsartana', '80-320mg', 'Diovan, Brasart'),
            ('BRA', 'Candesartana', '8-32mg', 'Atacand, Blopress'),
            ('BRA', 'Olmesartana', '20-40mg', 'Benicar'),
            ('BRA', 'Telmisartana', '40-80mg', 'Micardis'),
            ('BRA', 'Irbesartana', '150-300mg', 'Aprovel'),
            ('BRA', 'Azilsartana', '40-80mg', 'Edarbi'),  # Mais recente

            # --- INIBIDORES DIRETOS DA RENINA ---
            ('Inibidor Direto de Renina', 'Alisquireno', '150-300mg', 'Rasilez'),

            # --- BLOQUEADORES DE CANAIS DE CÁLCIO (BCC) - DIIDROPIRIDÍNICOS ---
            ('BCC (Diidropiridínico)', 'Anlodipino', '2,5-10mg', 'Norvasc, Pressat'),
            ('BCC (Diidropiridínico)', 'Nifedipino Retard', '30-60mg', 'Adalat Retard, Orix'),
            ('BCC (Diidropiridínico)', 'Felodipino', '2,5-20mg', 'Splendil'),
            ('BCC (Diidropiridínico)', 'Lercanidipino', '10-20mg', 'Zanidip'),
            ('BCC (Diidropiridínico)', 'Levanlodipino', '2,5-5mg', 'Novasc, Dartriol'),
            ('BCC (Diidropiridínico)', 'Manidipino', '10-20mg', 'Manivasc'),
            ('BCC (Diidropiridínico)', 'Nitrendipino', '10-40mg', 'Caltren'),
            ('BCC (Diidropiridínico)', 'Lacidipino', '2-4mg', 'Lacipil'),

            # --- BLOQUEADORES DE CANAIS DE CÁLCIO (BCC) - NÃO-DIIDROPIRIDÍNICOS ---
            ('BCC (Não-Diidro)', 'Verapamil', '120-480mg', 'Dilacoron, Vasoton'),
            ('BCC (Não-Diidro)', 'Diltiazem', '180-360mg', 'Balcor, Cardizem'),

            # --- BETABLOQUEADORES ---
            # Cardiosseletivos
            ('Betabloqueador', 'Atenolol', '25-100mg', 'Atenol, Angipress'),
            ('Betabloqueador', 'Bisoprolol', '1,25-10mg', 'Concor'),
            ('Betabloqueador', 'Metoprolol (Succinato)', '50-200mg', 'Selozok'),
            ('Betabloqueador', 'Metoprolol (Tartarato)', '100-400mg', 'Lopressor'),
            ('Betabloqueador', 'Nebivolol', '5-10mg', 'Nebilet'),

            # Não Cardiosseletivos
            ('Betabloqueador', 'Propranolol', '40-240mg', 'Inderal'),
            ('Betabloqueador', 'Nadolol', '40-240mg', 'Corgard'),

            # Ação Vasodilatadora (Alfa + Beta)
            ('Betabloqueador', 'Carvedilol', '12,5-50mg', 'Coreg, Ictus'),  # Até 50mg/dia (HAS) ou mais (IC)
            ('Betabloqueador', 'Labetalol', '200-800mg', 'Trandate'),  # Mais comum via EV, mas existe oral (gestante)

            # --- SIMPATICOLÍTICOS DE AÇÃO CENTRAL ---
            ('Agonista Central', 'Clonidina', '0,100-0,600mg', 'Atensina'),
            ('Agonista Central', 'Metildopa', '250-1500mg', 'Aldomet'),
            ('Agonista Central', 'Moxonidina', '0,2-0,4mg', 'Cynt'),
            ('Agonista Central', 'Rilmenidina', '1-2mg', 'Hyperium'),
            ('Agonista Central', 'Guanfacina', '1-3mg', 'Estulic'),

            # --- VASODILATADORES DIRETOS ---
            ('Vasodilatador Direto', 'Hidralazina', '50-200mg', 'Apresolina'),
            ('Vasodilatador Direto', 'Minoxidil', '2,5-40mg', 'Loniten'),

            # --- ALFA-BLOQUEADORES ---
            ('Alfa-Bloqueador', 'Doxazosina', '1-16mg', 'Carduran'),
            ('Alfa-Bloqueador', 'Prazosina', '2-20mg', 'Minipress'),
            ('Alfa-Bloqueador', 'Terazosina', '1-20mg', 'Hytrin')
        ]

        # ---------------------------------------------------------
        # 3. Execução da Carga (Update or Create)
        # ---------------------------------------------------------
        self.stdout.write('Atualizando base de medicamentos...')

        count_created = 0
        count_updated = 0

        for classe, principio, dose, nomes in meds_completo:
            obj, created = Medicamento.objects.update_or_create(
                principio_ativo=principio,
                defaults={
                    'classe': classe,
                    'dose_padrao': dose,
                    'nomes_comerciais': nomes,
                    'ativo': True
                }
            )
            if created:
                count_created += 1
            else:
                count_updated += 1

        self.stdout.write(self.style.SUCCESS(f'Processo concluído!'))
        self.stdout.write(f'- Novos inseridos: {count_created}')
        self.stdout.write(f'- Atualizados: {count_updated}')
        self.stdout.write(f'- Total na base: {Medicamento.objects.count()}')