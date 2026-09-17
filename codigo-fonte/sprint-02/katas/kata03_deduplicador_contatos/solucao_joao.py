def deduplicar_contatos(contatos: list[dict]) -> list[dict]:
    contatos_unicos = {}

    for contato in contatos:
        telefone = ''.join(c for c in contato["telefone"] if c.isdigit())
        telefone = telefone[-11:]

        if telefone not in contatos_unicos:
            contatos_unicos[telefone] = contato
        elif len(contato["nome"]) > len(contatos_unicos[telefone]["nome"]):
            contatos_unicos[telefone] = contato

    return list(contatos_unicos.values())