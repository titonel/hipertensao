def converter_cid10_para_cid11(cid10_codigo):
    """
    Mapeia os principais CIDs-10 usados no AME para CID-11.
    Nota: Em produção, isso pode ser substituído por uma chamada à API da WHO.
    """
    codigo = cid10_codigo.upper().strip()

    mapeamento = {
        # Hipertensão
        'I10': 'BA00',  # Hipertensão essencial
        'I11': 'BA01',  # Doença cardíaca hipertensiva
        'I12': 'GB61',  # Doença renal hipertensiva
        'I15': 'BA04',  # Hipertensão secundária

        # Diabetes (Comorbidade comum)
        'E11': '5A11',  # Diabetes Mellitus Tipo 2
        'E10': '5A10',  # Diabetes Mellitus Tipo 1

        # Dislipidemias
        'E78': '5C80',  # Distúrbios do metabolismo de lipoproteínas

        # Cardiopatias
        'I50': 'BD10',  # Insuficiência cardíaca
        'I20': 'BA40',  # Angina pectoris
        'I21': 'BA41',  # Infarto agudo do miocárdio
        'I25': 'BA42',  # Doença isquêmica crônica do coração

        # Outros
        'R07': 'MB23',  # Dor na garganta e no peito (Dor torácica)
        'Z00': 'QA00',  # Exame geral
    }

    return mapeamento.get(codigo, "Não Mapeado Automaticamente")