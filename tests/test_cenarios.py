"""Os cenários da Fase 7 rodam com a IA real (custa dinheiro), mas o FORMATO deles dá
para conferir de graça: uma chave escrita errado seria ignorada e o cenário "passaria"
sem conferir nada."""

from cenarios.executar import carregar_cenarios, contar_perguntas, validar


def test_todos_os_cenarios_tem_formato_valido():
    cenarios = carregar_cenarios()
    assert len(cenarios) >= 15
    erros = [erro for c in cenarios for erro in validar(c)]
    assert erros == []


def test_nomes_dos_cenarios_sao_unicos():
    nomes = [c["nome"] for c in carregar_cenarios()]
    assert len(nomes) == len(set(nomes))


def test_contar_perguntas():
    assert contar_perguntas("Anotado! ~460 kcal. O bife era grande?") == 1
    assert contar_perguntas("Anotado! Era grande? E o arroz, quantas colheres?") == 2
    assert contar_perguntas("Anotado seu almoço 🍽️ ~460 kcal.") == 0
