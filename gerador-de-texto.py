from fpdf import FPDF


class PDF(FPDF):
    def header(self):
        # Fonte Arial bold 12
        self.set_font('Arial', 'B', 12)
        # Título
        self.cell(0, 10, 'ATA DE REUNIÃO - COMISSÃO DE REPROCESSAMENTO (CME)', 0, 1, 'C')
        self.set_font('Arial', 'B', 10)
        self.cell(0, 10, 'AME CARAGUATATUBA - SECONCI-SP OSS', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        # Posição a 1.5 cm do fim
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, 'Página ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')


def create_ata_pdf():
    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font('Arial', '', 11)

    # Cabeçalho da Ata
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 8, 'Data: 26/11/2025', 0, 1)
    pdf.cell(0, 8, 'Local: Sala da Coordenação de Enfermagem', 0, 1)
    pdf.ln(5)

    # Texto do corpo (Codificação Latin-1 para acentos funcionarem no FPDF padrão)
    body_text = (
        "PARTICIPANTES:\n"
        "- Fernando Macedo Lebrão (Enfermeiro - COREN-SP 483.582-ENF)\n"
        "- Bruna Cristina Dias (Enfermeira Coord. - COREN-SP 5733-15)\n"
        "- Jane Lúcia Carneiro da Cunha (Téc. Enfermagem/Relatora)\n\n"

        "PAUTA:\n"
        "Alinhamento de processos e Comissão Interna de Reprocessamento – CME.\n\n"

        "DELIBERAÇÕES:\n\n"
        "1. CONTROLE DE VALIDADE E REPROCESSAMENTO\n"
        "Discutido o alinhamento das rotinas de monitoramento dos prazos de validade. "
        "Reforçado o protocolo de segregação imediata e reprocessamento obrigatório de quaisquer "
        "materiais com prazo expirado, garantindo que não haja dispensação de produtos fora da validade, "
        "em conformidade com a RDC 15/2012.\n\n"

        "2. INDICADORES\n"
        "Apresentados os indicadores de produtividade referentes a setembro e outubro.\n\n"

        "3. AQUISIÇÃO DE MATERIAIS E USO DA STATIM\n"
        "Enfatizada a necessidade de compra de novos materiais para fortalecer o arsenal cirúrgico. "
        "O objetivo é garantir rotatividade suficiente para restringir a esterilização de uso imediato "
        "(ciclo flash/STATIM) estritamente a casos de urgência e emergência, conforme preconiza a "
        "legislação vigente, eliminando seu uso por insuficiência de instrumentais.\n\n"

        "4. COMPOSIÇÃO DA COMISSÃO\n"
        "Solicitado apoio para formalizar convite à Direção Técnica para integrar a Comissão na próxima "
        "reunião trimestral (Fevereiro).\n\n"
    )

    # Escrevendo o corpo
    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 7, body_text)

    pdf.ln(20)

    # Assinaturas
    pdf.cell(0, 10, "_" * 50, 0, 1, 'C')
    pdf.cell(0, 5, "Fernanda Macedo Lebrão", 0, 1, 'C')
    pdf.ln(10)

    pdf.cell(0, 10, "_" * 50, 0, 1, 'C')
    pdf.cell(0, 5, "Bruna Cristina Dias", 0, 1, 'C')
    pdf.ln(10)

    pdf.cell(0, 10, "_" * 50, 0, 1, 'C')
    pdf.cell(0, 5, "Jane Lúcia Carneiro da Cunha", 0, 1, 'C')

    pdf.output('Ata_CME_26_11_2025.pdf', 'F')
    print("PDF gerado com sucesso!")


if __name__ == '__main__':
    create_ata_pdf()